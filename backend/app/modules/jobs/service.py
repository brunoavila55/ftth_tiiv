import logging
import threading
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import and_, insert, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppException
from app.core.logging import job_id_ctx
from app.core.metrics import metrics_collector
from app.core.storage import resolve_storage_path
from app.db.session import get_session_factory
from app.modules.audit.service import record_audit_event
from app.modules.cables.service import create_cable, create_cable_segment
from app.modules.exports.service import execute_export_job
from app.modules.gis.service import bump_topology_revision
from app.modules.identity.models import User
from app.modules.imports.models import AsyncJob, ImportPreview
from app.modules.imports.service import (
    parse_csv,
    parse_geojson,
    parse_kml,
    resolve_cable_endpoints,
)
from app.modules.inventory.models import Site, Structure
from app.modules.jobs.errors import GENERIC_JOB_ERROR, JobValidationError
from app.schemas.cables import CableCreate, CableSegmentCreate
from app.schemas.geojson import LineStringGeometry
from app.schemas.imports_exports import JobRead, JobStatus, JobType

logger = logging.getLogger("ftth.jobs")

# Linhas por INSERT em lote na importação (1 statement) + 1 refresh de cancelamento por lote
IMPORT_BATCH_SIZE = 500


def get_job_by_id(db: Session, job_id: str) -> JobRead:
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' não encontrado.",
        ) from None

    job = db.get(AsyncJob, uid)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' não encontrado.",
        )

    result_url = None
    if job.type.startswith("export_") and job.status == "succeeded":
        result_url = f"/api/v1/exports/{job.id}/download"

    return JobRead(
        id=str(job.id),
        type=JobType(job.type),
        status=JobStatus(job.status),
        progress_percentage=job.progress_percentage,
        error_message=job.error_message,
        result_url=result_url,
        created_at=job.created_at,
        updated_at=job.updated_at,
        finished_at=job.finished_at,
    )


def cancel_job_by_id(db: Session, job_id: str, user: User | None = None) -> JobRead:
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' não encontrado.",
        ) from None

    job = db.get(AsyncJob, uid)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' não encontrado.",
        )

    # Se já finalizado, não altera
    if job.status in ("succeeded", "failed", "cancelled"):
        return get_job_by_id(db, job_id)

    # Se estiver queued ou running, marca como cancelled
    job.status = "cancelled"
    job.error_message = "Execução cancelada a pedido do operador."
    job.finished_at = datetime.now(UTC)
    db.commit()
    db.refresh(job)

    return get_job_by_id(db, job_id)


def claim_next_job(
    db: Session, worker_id: str, lease_seconds: float | None = None
) -> AsyncJob | None:
    if lease_seconds is None:
        lease_seconds = get_settings().JOB_LEASE_SECONDS
    now = datetime.now(UTC)

    stmt = (
        select(AsyncJob)
        .where(
            or_(
                AsyncJob.status == "queued",
                and_(
                    AsyncJob.status == "running",
                    AsyncJob.lease_expires_at < now,
                    AsyncJob.retry_count < AsyncJob.max_retries,
                ),
            )
        )
        .order_by(AsyncJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )

    job = db.scalars(stmt).first()
    if not job:
        return None

    if job.status == "running":
        # Lease expirou e está sendo recuperado após crash/timeout do worker anterior
        job.retry_count += 1
        if job.retry_count >= job.max_retries:
            job.status = "failed"
            job.error_message = (
                f"Lease expirou após o número máximo de {job.max_retries} tentativas."
            )
            job.finished_at = now
            db.commit()
            return None

    job.status = "running"
    job.lease_owner = worker_id
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.heartbeat_at = now
    db.commit()
    db.refresh(job)
    return job


def heartbeat(
    db: Session, job_id: uuid.UUID, worker_id: str, lease_seconds: float | None = None
) -> bool:
    if lease_seconds is None:
        lease_seconds = get_settings().JOB_LEASE_SECONDS
    job = db.get(AsyncJob, job_id)
    if not job:
        return False
    if job.status == "cancelled":
        return False

    now = datetime.now(UTC)
    job.heartbeat_at = now
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    db.commit()
    return True


class LeaseLostError(Exception):
    """O job foi reivindicado por outro worker (lease expirou/perdida) durante a execução."""


class LeaseKeeper:
    """Renova a lease do job em segundo plano (thread + sessão própria) enquanto ele executa.

    Usa uma conexão separada: renovar via a sessão do job cometeria a transação all-or-nothing
    da importação. Se a renovação afeta 0 linhas (outro worker assumiu), marca `lost`.
    """

    def __init__(
        self,
        job_id: uuid.UUID,
        worker_id: str,
        lease_seconds: float,
        on_beat: Callable[[], None] | None = None,
    ) -> None:
        self.job_id = job_id
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.on_beat = on_beat
        self.lost = False
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=f"lease-{job_id}", daemon=True)

    def __enter__(self) -> "LeaseKeeper":
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=10)

    def _run(self) -> None:
        interval = max(self.lease_seconds / 3, 0.05)
        factory = get_session_factory()
        while not self._stop.wait(interval):
            try:
                with factory() as session:
                    now = datetime.now(UTC)
                    result = session.execute(
                        update(AsyncJob)
                        .where(
                            AsyncJob.id == self.job_id,
                            AsyncJob.lease_owner == self.worker_id,
                            AsyncJob.status == "running",
                        )
                        .values(
                            heartbeat_at=now,
                            lease_expires_at=now + timedelta(seconds=self.lease_seconds),
                        )
                    )
                    session.commit()
                    if getattr(result, "rowcount", 1) == 0:
                        self.lost = True
                        logger.warning("Lease do job '%s' perdida para outro worker.", self.job_id)
                        return
                if self.on_beat:
                    self.on_beat()
            except Exception:
                logger.exception("Falha ao renovar a lease do job '%s'.", self.job_id)


def assert_lease_owner(db: Session, job_id: uuid.UUID, worker_id: str) -> None:
    """Trava a linha do job e confere dono/estado ANTES de gravar o resultado final.

    Cancelado → InterruptedError (o handler marca `cancelled`); dono diferente → LeaseLostError.
    O FOR UPDATE segura a linha até o commit, então o resultado só é gravado por quem ainda é dono.
    """
    row = db.execute(
        select(AsyncJob.lease_owner, AsyncJob.status).where(AsyncJob.id == job_id).with_for_update()
    ).one_or_none()
    if row is None:
        raise LeaseLostError("job removido")
    if row.status == "cancelled":
        raise InterruptedError("Job cancelado pelo operador")
    if row.lease_owner != worker_id or row.status != "running":
        raise LeaseLostError(f"lease pertence a {row.lease_owner!r} (status {row.status})")


def execute_import_commit(db: Session, job: AsyncJob) -> dict[str, Any]:
    payload = job.payload or {}
    file_path = payload.get("file_storage_path")
    fmt = payload.get("format")

    resolved_path = resolve_storage_path(file_path) if file_path else None
    if resolved_path is None or not resolved_path.exists():
        raise JobValidationError(
            "O arquivo de importação não está mais disponível no servidor. Gere uma nova prévia."
        )

    with open(resolved_path, "rb") as f:
        content = f.read()

    if fmt == "geojson":
        parsed_items, _ = parse_geojson(content)
    elif fmt == "kml":
        parsed_items, _ = parse_kml(content)
    elif fmt == "csv":
        parsed_items, _ = parse_csv(content)
    else:
        raise JobValidationError(f"Formato de importação desconhecido: {fmt}")

    max_features = get_settings().MAX_IMPORT_FEATURES
    if len(parsed_items) > max_features:
        raise JobValidationError(
            f"O arquivo contém {len(parsed_items)} entidades; o máximo permitido é {max_features}."
        )

    # Validação All-or-Nothing prévia
    codes = [it["code"] for it in parsed_items if it.get("code")]
    if len(codes) != len(set(codes)):
        raise JobValidationError(
            "O arquivo contém códigos duplicados entre suas próprias entidades."
        )

    # Uma única transação atômica; sites e estruturas entram em LOTES (INSERT em lote), com a
    # verificação de cancelamento a cada lote — ≤ 2 statements por lote de IMPORT_BATCH_SIZE linhas.
    site_map: dict[str, uuid.UUID] = {}
    created_sites = 0
    created_structs = 0
    created_cables = 0

    def check_cancelled() -> None:
        db.refresh(job)
        if job.status == "cancelled":
            raise InterruptedError("Job cancelado pelo operador")

    def batches(items: list[dict[str, Any]]) -> Iterator[list[dict[str, Any]]]:
        for start in range(0, len(items), IMPORT_BATCH_SIZE):
            yield items[start : start + IMPORT_BATCH_SIZE]

    # 1. Sites
    site_items = [it for it in parsed_items if it["entity_type"] == "site"]
    for chunk in batches(site_items):
        check_cancelled()
        rows = []
        for s_it in chunk:
            lon, lat = s_it["coords"][0], s_it["coords"][1]
            site_id = uuid.uuid4()
            site_map[s_it["code"]] = site_id
            rows.append(
                {
                    "id": site_id,
                    "code": s_it["code"],
                    "name": s_it["name"],
                    "kind": s_it["props"].get("kind") or s_it["props"].get("type") or "pop",
                    "status": s_it["props"].get("status", "installed"),
                    "location": from_shape(Point(lon, lat), srid=4326),
                    "version": 1,
                }
            )
        db.execute(insert(Site), rows)
        created_sites += len(rows)

    # 2. Estruturas (Postes, Caixas CEO/CTO)
    struct_items = [
        it for it in parsed_items if it["entity_type"] in ("structure", "pole", "cto", "ceo")
    ]
    for chunk in batches(struct_items):
        check_cancelled()
        rows = []
        for st_it in chunk:
            lon, lat = st_it["coords"][0], st_it["coords"][1]
            st_kind = (
                st_it["props"].get("kind") or st_it["props"].get("type") or st_it["entity_type"]
            )
            if st_kind not in ("pole", "manhole", "ceo", "cto"):
                st_kind = "pole"
            site_code = st_it["props"].get("site_code")
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "code": st_it["code"],
                    "kind": st_kind,
                    "status": st_it["props"].get("status", "installed"),
                    "condition": "ok",
                    "capacity": 0,
                    "location": from_shape(Point(lon, lat), srid=4326),
                    "site_id": site_map.get(site_code) if site_code else None,
                    "version": 1,
                }
            )
        db.execute(insert(Structure), rows)
        created_structs += len(rows)

    # 3. Inserir Cabos: cabo + trecho (CableSegment) com a geometria do arquivo, pontas resolvidas
    # por código explícito ou proximidade (as estruturas do arquivo já foram gravadas acima)
    cable_items = [it for it in parsed_items if it["entity_type"] == "cable"]
    for c_it in cable_items:
        db.refresh(job)
        if job.status == "cancelled":
            raise InterruptedError("Job cancelado pelo operador")

        coords = c_it["coords"]
        if not coords or len(coords) < 2:
            raise JobValidationError(f"Cabo '{c_it['code']}': geometria ausente.")

        origin, _, destination, _, error = resolve_cable_endpoints(db, c_it, pending={})
        if error or origin is None or destination is None:
            raise JobValidationError(error or f"Cabo '{c_it['code']}': estruturas não resolvidas.")

        cable = create_cable(
            db,
            CableCreate(
                code=c_it["code"],
                model=c_it.get("name") or "Standard Cable",
                fiber_count=int(c_it["props"].get("fiber_count") or 12),
                tube_count=int(c_it["props"].get("tube_count") or 2),
                status=c_it["props"].get("status", "installed"),
            ),
            commit=False,
        )
        create_cable_segment(
            db,
            CableSegmentCreate(
                cable_id=str(cable.id),
                origin_structure_id=str(origin.id),
                destination_structure_id=str(destination.id),
                geometry=LineStringGeometry(
                    coordinates=[(float(pt[0]), float(pt[1])) for pt in coords]
                ),
                slack_length_m=float(c_it["props"].get("slack_length_m") or 0.0),
            ),
            commit=False,
            bump_revision=False,
        )
        created_cables += 1

    # 4. Auditoria atômica
    record_audit_event(
        db,
        actor_id=job.user_id,
        actor_name="Import Worker",
        action="import_commit",
        entity_type="async_job",
        entity_id=job.id,
        changes={
            "created_sites": created_sites,
            "created_structures": created_structs,
            "created_cables": created_cables,
            "format": fmt,
        },
        reason="Execução bem-sucedida de importação de rede física",
    )

    # 5. Incrementar a revisão monotônica de topologia como ÚLTIMO passo antes do commit: o UPDATE
    # trava a linha de estado até o commit e não deve segurar outras mutações durante o import.
    bump_topology_revision(db)

    return {
        "created_sites": created_sites,
        "created_structures": created_structs,
        "created_cables": created_cables,
        "total_imported": created_sites + created_structs + created_cables,
        "message": "Importação concluída com sucesso.",
    }


def process_claimed_job(
    db: Session,
    job: AsyncJob,
    worker_id: str = "worker-default",
    on_heartbeat: Callable[[], None] | None = None,
) -> bool:
    """Executa um job já reivindicado (`claim_next_job`). Retorna True se concluiu com sucesso.

    Enquanto executa, uma thread renova a lease (`LeaseKeeper`); antes de gravar o resultado
    confere que este worker ainda é o dono (`assert_lease_owner`), senão descarta tudo.
    """
    job_id = job.id
    job_type = job.type
    final_status = "failed"
    token = job_id_ctx.set(str(job_id))
    lease_seconds = get_settings().JOB_LEASE_SECONDS
    try:
        with LeaseKeeper(job_id, worker_id, lease_seconds, on_beat=on_heartbeat):
            try:
                if job_type == "import_commit":
                    result = execute_import_commit(db, job)
                    assert_lease_owner(db, job_id, worker_id)
                    job.result = result
                    job.progress_percentage = 100
                    job.status = "succeeded"
                    job.finished_at = datetime.now(UTC)
                    db.commit()
                elif job_type.startswith("export_"):
                    stored_path = execute_export_job(db, job)
                    assert_lease_owner(db, job_id, worker_id)
                    job.result_path = stored_path
                    job.result = {
                        "download_url": f"/api/v1/exports/{job.id}/download",
                        "file_size_bytes": resolve_storage_path(stored_path).stat().st_size,
                        "generated_at": datetime.now(UTC).isoformat(),
                    }
                    job.progress_percentage = 100
                    job.status = "succeeded"
                    job.finished_at = datetime.now(UTC)
                    db.commit()
                else:
                    job.status = "failed"
                    job.error_message = f"Tipo de job '{job_type}' não suportado pelo worker."
                    job.finished_at = datetime.now(UTC)
                    db.commit()
            except LeaseLostError as e:
                # Outro worker é o dono: nada deste worker pode ser gravado (nem entidades importadas)
                db.rollback()
                logger.warning("Job '%s' descartado: lease perdida (%s).", job_id, e)
                final_status = "lease_lost"
            except InterruptedError:
                # Cancelado durante a execução: rollback transacional imediato
                db.rollback()
                reloaded = db.get(AsyncJob, job_id)
                if reloaded:
                    reloaded.status = "cancelled"
                    reloaded.finished_at = datetime.now(UTC)
                    db.commit()
            except Exception as e:
                # O detalhe técnico (SQL, caminhos, traceback) fica só no log, com o job_id no contexto
                logger.exception(
                    "Job '%s' [%s] falhou no worker '%s'.", job_id, job_type, worker_id
                )
                db.rollback()
                # Mensagens de negócio (JobValidationError/AppException) são seguras; o resto é genérico
                safe = isinstance(e, JobValidationError | AppException)
                client_message = str(e) if safe else GENERIC_JOB_ERROR
                reloaded = db.get(AsyncJob, job_id)
                if reloaded:
                    reloaded.status = "failed"
                    reloaded.error_message = client_message
                    reloaded.finished_at = datetime.now(UTC)
                    db.commit()

        if final_status != "lease_lost":
            persisted = db.get(AsyncJob, job_id)
            if persisted is not None:
                db.refresh(persisted)
                final_status = persisted.status
    finally:
        job_id_ctx.reset(token)

    metrics_collector.record_job(job_type, final_status)
    return final_status == "succeeded"


def process_next_job(db: Session, worker_id: str = "worker-default") -> bool:
    job = claim_next_job(db, worker_id)
    if not job:
        return False

    process_claimed_job(db, job, worker_id=worker_id)
    return True


def clean_expired_previews_and_exports(db: Session) -> dict[str, int]:
    """Rotina de retenção: remove rascunhos de importação expirados (>24h) e exportações vencidas.

    Arquivos de exportação vivem `EXPORT_TTL_DAYS` (padrão 7) após o término do job; o registro do
    job permanece (histórico) e o download passa a responder 410.
    """
    now = datetime.now(UTC)
    expired_previews = db.scalars(select(ImportPreview).where(ImportPreview.expires_at < now)).all()

    removed_files = 0
    for p in expired_previews:
        preview_file = resolve_storage_path(p.file_storage_path) if p.file_storage_path else None
        if preview_file is not None and preview_file.exists():
            try:
                preview_file.unlink()
                removed_files += 1
            except OSError:
                pass
        db.delete(p)

    export_cutoff = now - timedelta(days=get_settings().EXPORT_TTL_DAYS)
    expired_exports = 0
    export_jobs = db.scalars(
        select(AsyncJob).where(
            AsyncJob.type.like("export_%"),
            AsyncJob.status == "succeeded",
            AsyncJob.result_path.is_not(None),
            AsyncJob.finished_at < export_cutoff,
        )
    ).all()
    for job in export_jobs:
        export_file = resolve_storage_path(job.result_path) if job.result_path else None
        if export_file is not None and export_file.exists():
            try:
                export_file.unlink()
            except OSError:
                logger.warning("Não foi possível remover a exportação vencida do job '%s'.", job.id)
                continue
            expired_exports += 1

    db.commit()
    return {
        "cleaned_previews": len(expired_previews),
        "removed_files": removed_files,
        "expired_exports": expired_exports,
    }
