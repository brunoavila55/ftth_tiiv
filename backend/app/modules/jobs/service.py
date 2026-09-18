import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.logging import job_id_ctx
from app.core.metrics import metrics_collector
from app.modules.audit.service import record_audit_event
from app.modules.cables.models import Cable
from app.modules.exports.service import execute_export_job
from app.modules.gis.service import bump_topology_revision
from app.modules.identity.models import User
from app.modules.imports.models import AsyncJob, ImportPreview
from app.modules.imports.service import parse_csv, parse_geojson, parse_kml
from app.modules.inventory.models import Site, Structure
from app.schemas.imports_exports import JobRead, JobStatus, JobType

logger = logging.getLogger("ftth.jobs")


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


def claim_next_job(db: Session, worker_id: str, lease_seconds: int = 60) -> AsyncJob | None:
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


def heartbeat(db: Session, job_id: uuid.UUID, worker_id: str, lease_seconds: int = 60) -> bool:
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


def execute_import_commit(db: Session, job: AsyncJob) -> dict[str, Any]:
    payload = job.payload or {}
    file_path = payload.get("file_storage_path")
    fmt = payload.get("format")

    if not file_path or not os.path.exists(file_path):
        raise FileNotFoundError(f"Arquivo de importação não encontrado no disco: {file_path}")

    with open(file_path, "rb") as f:
        content = f.read()

    if fmt == "geojson":
        parsed_items, _ = parse_geojson(content)
    elif fmt == "kml":
        parsed_items, _ = parse_kml(content)
    elif fmt == "csv":
        parsed_items, _ = parse_csv(content)
    else:
        raise ValueError(f"Formato de importação desconhecido: {fmt}")

    # Validação All-or-Nothing prévia
    codes = [it["code"] for it in parsed_items if it.get("code")]
    if len(codes) != len(set(codes)):
        raise ValueError("O arquivo contém códigos duplicados entre suas próprias entidades.")

    # Iniciar transação atômica
    site_map: dict[str, uuid.UUID] = {}
    struct_map: dict[str, uuid.UUID] = {}
    created_sites = 0
    created_structs = 0
    created_cables = 0

    # 1. Inserir Sites
    site_items = [it for it in parsed_items if it["entity_type"] == "site"]
    for s_it in site_items:
        # Verificar se já foi cancelado
        db.refresh(job)
        if job.status == "cancelled":
            raise InterruptedError("Job cancelado pelo operador")

        coords = s_it["coords"]
        lon, lat = coords[0], coords[1]
        geom_point = from_shape(Point(lon, lat), srid=4326)
        site = Site(
            code=s_it["code"],
            name=s_it["name"],
            kind=s_it["props"].get("kind") or s_it["props"].get("type") or "pop",
            status=s_it["props"].get("status", "installed"),
            location=geom_point,
        )
        db.add(site)
        db.flush()
        site_map[s_it["code"]] = site.id
        created_sites += 1

    # 2. Inserir Estruturas (Postes, Caixas CEO/CTO)
    struct_items = [
        it for it in parsed_items if it["entity_type"] in ("structure", "pole", "cto", "ceo")
    ]
    for st_it in struct_items:
        db.refresh(job)
        if job.status == "cancelled":
            raise InterruptedError("Job cancelado pelo operador")

        coords = st_it["coords"]
        lon, lat = coords[0], coords[1]
        geom_point = from_shape(Point(lon, lat), srid=4326)
        st_kind = st_it["props"].get("kind") or st_it["props"].get("type") or st_it["entity_type"]
        if st_kind not in ("pole", "manhole", "ceo", "cto"):
            st_kind = "pole"

        site_code = st_it["props"].get("site_code")
        site_id = site_map.get(site_code) if site_code else None

        struct = Structure(
            code=st_it["code"],
            kind=st_kind,
            status=st_it["props"].get("status", "installed"),
            condition="ok",
            location=geom_point,
            site_id=site_id,
        )
        db.add(struct)
        db.flush()
        struct_map[st_it["code"]] = struct.id
        created_structs += 1

    # 3. Inserir Cabos
    cable_items = [it for it in parsed_items if it["entity_type"] == "cable"]
    for c_it in cable_items:
        db.refresh(job)
        if job.status == "cancelled":
            raise InterruptedError("Job cancelado pelo operador")

        coords = c_it["coords"]
        if coords and len(coords) >= 2:
            cable = Cable(
                code=c_it["code"],
                model=c_it.get("name") or "Standard Cable",
                fiber_count=int(c_it["props"].get("fiber_count") or 12),
                tube_count=int(c_it["props"].get("tube_count") or 2),
                status=c_it["props"].get("status", "installed"),
            )
            db.add(cable)
            db.flush()
            created_cables += 1

    # 4. Incrementar revisão monotônica de topologia
    bump_topology_revision(db)

    # 5. Auditoria atômica
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

    return {
        "created_sites": created_sites,
        "created_structures": created_structs,
        "created_cables": created_cables,
        "total_imported": created_sites + created_structs + created_cables,
        "message": "Importação concluída com sucesso.",
    }


def process_claimed_job(db: Session, job: AsyncJob, worker_id: str = "worker-default") -> bool:
    """Executa um job já reivindicado (`claim_next_job`). Retorna True se concluiu com sucesso."""
    job_id = job.id
    job_type = job.type
    final_status = "failed"
    token = job_id_ctx.set(str(job_id))
    try:
        try:
            if job_type == "import_commit":
                result = execute_import_commit(db, job)
                job.result = result
                job.progress_percentage = 100
                job.status = "succeeded"
                job.finished_at = datetime.now(UTC)
                db.commit()
            elif job_type.startswith("export_"):
                file_path = execute_export_job(db, job)
                job.result_path = file_path
                job.result = {
                    "download_url": f"/api/v1/exports/{job.id}/download",
                    "file_size_bytes": os.path.getsize(file_path),
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
        except InterruptedError:
            # Cancelado durante a execução: rollback transacional imediato
            db.rollback()
            reloaded = db.get(AsyncJob, job_id)
            if reloaded:
                reloaded.status = "cancelled"
                reloaded.finished_at = datetime.now(UTC)
                db.commit()
        except Exception as e:
            logger.exception("Job '%s' [%s] falhou no worker '%s'.", job_id, job_type, worker_id)
            db.rollback()
            # Atualizar job com falha
            reloaded = db.get(AsyncJob, job_id)
            if reloaded:
                reloaded.status = "failed"
                reloaded.error_message = str(e)
                reloaded.finished_at = datetime.now(UTC)
                db.commit()

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
    """Rotina de retenção: remove rascunhos de importação expirados (>24h) e arquivos temporários."""
    now = datetime.now(UTC)
    expired_previews = db.scalars(select(ImportPreview).where(ImportPreview.expires_at < now)).all()

    removed_files = 0
    for p in expired_previews:
        if p.file_storage_path and os.path.exists(p.file_storage_path):
            try:
                os.remove(p.file_storage_path)
                removed_files += 1
            except OSError:
                pass
        db.delete(p)

    db.commit()
    return {"cleaned_previews": len(expired_previews), "removed_files": removed_files}
