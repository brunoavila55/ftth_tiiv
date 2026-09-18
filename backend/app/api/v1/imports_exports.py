import os
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, File, Header, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_current_user, require_permission, validate_csrf
from app.core.errors import ForbiddenError
from app.core.privacy import user_can
from app.core.rate_limit import rate_limit
from app.core.uploads import read_upload_limited
from app.db.session import get_db
from app.modules.audit.service import record_audit_event
from app.modules.exports.service import create_export_request
from app.modules.identity.models import User
from app.modules.imports.models import AsyncJob
from app.modules.imports.service import (
    commit_import_job,
    create_import_preview,
    get_preview_by_id,
)
from app.modules.jobs.service import cancel_job_by_id, get_job_by_id
from app.schemas.imports_exports import (
    ExportRequest,
    ExportResponse,
    ImportCommitRequest,
    ImportCommitResponse,
    ImportPreviewResponse,
    JobRead,
)

imports_exports_router = APIRouter(tags=["Importação, Exportação e Jobs"])


# ==============================================================================
# IMPORTS (GeoJSON, KML, CSV)
# ==============================================================================
@imports_exports_router.post(
    "/imports/preview",
    response_model=ImportPreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Pré-visualizar arquivo de importação",
    description="Analisa sintaxe, valida entidades, detecta colisões e gera resumo sem alterar a rede.",
    dependencies=[
        Depends(require_permission("imports:write")),
        Depends(validate_csrf),
        Depends(rate_limit("upload", "RATE_LIMIT_UPLOAD_PER_MINUTE")),
    ],
)
async def preview_import(
    file: UploadFile = File(..., description="Arquivo GeoJSON, KML ou CSV"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportPreviewResponse:
    content = await read_upload_limited(file, get_settings().MAX_IMPORT_SIZE_BYTES)
    filename = file.filename or "import.geojson"
    return create_import_preview(
        db=db,
        content=content,
        filename=filename,
        user=current_user,
    )


@imports_exports_router.get(
    "/imports/{import_id}",
    response_model=ImportPreviewResponse,
    summary="Consultar resultado de prévia de importação",
    dependencies=[Depends(require_permission("imports:read"))],
)
def get_import_preview(
    import_id: str,
    db: Session = Depends(get_db),
) -> ImportPreviewResponse:
    return get_preview_by_id(db=db, import_id=import_id)


@imports_exports_router.post(
    "/imports/{import_id}/commit",
    response_model=ImportCommitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Confirmar importação de dados",
    description="Dispara processamento em lote transacional e idempotente com Idempotency-Key.",
    dependencies=[Depends(require_permission("imports:write")), Depends(validate_csrf)],
)
def commit_import(
    import_id: str,
    payload: ImportCommitRequest,
    idempotency_key: str = Header(..., description="Chave de idempotência única da operação"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportCommitResponse:
    return commit_import_job(
        db=db,
        import_id=import_id,
        payload=payload,
        idempotency_key=idempotency_key,
        user=current_user,
    )


# ==============================================================================
# EXPORTS (GeoJSON, KML, CSV)
# ==============================================================================
@imports_exports_router.post(
    "/exports",
    response_model=ExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Solicitar exportação de dados",
    dependencies=[
        Depends(require_permission("exports:write")),
        Depends(validate_csrf),
        Depends(rate_limit("export", "RATE_LIMIT_EXPORT_PER_MINUTE")),
    ],
)
def request_export(
    payload: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExportResponse:
    return create_export_request(
        db=db,
        payload=payload,
        user=current_user,
    )


@imports_exports_router.get(
    "/exports/{export_id}",
    response_model=JobRead,
    summary="Status da exportação",
    dependencies=[Depends(require_permission("exports:read"))],
)
def get_export_status(
    export_id: str,
    db: Session = Depends(get_db),
) -> JobRead:
    return get_job_by_id(db=db, job_id=export_id)


@imports_exports_router.get(
    "/exports/{export_id}/download",
    summary="Download do arquivo exportado",
    dependencies=[Depends(require_permission("exports:read"))],
)
def download_export(
    export_id: str,
    current_user: User = Depends(require_permission("exports:read")),
    db: Session = Depends(get_db),
) -> Response:
    try:
        uid = uuid.UUID(export_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exportação '{export_id}' não encontrada.",
        ) from None

    job = db.get(AsyncJob, uid)
    if not job or not job.type.startswith("export_"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exportação '{export_id}' não encontrada.",
        )

    if job.status != "succeeded" or not job.result_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"O arquivo de exportação ainda não está pronto. Status atual: {job.status}.",
        )

    # Dados pessoais (LGPD): a camada de clientes só é baixável por admin — revalidado AQUI, não só
    # na criação (exports:read + job_id não basta)
    layers = (job.payload or {}).get("layers", [])
    if "customers" in layers and current_user.role != "admin":
        raise ForbiddenError(
            "Exportações com dados pessoais de clientes só podem ser baixadas por administradores.",
            code="insufficient_permissions",
        )

    expired = job.finished_at is not None and job.finished_at < datetime.now(UTC) - timedelta(
        days=get_settings().EXPORT_TTL_DAYS
    )
    if expired or not os.path.exists(job.result_path):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="O arquivo exportado expirou ou foi removido do servidor.",
        )

    record_audit_event(
        db,
        actor_id=current_user.id,
        actor_name=current_user.name,
        action="export_downloaded",
        entity_type="async_job",
        entity_id=job.id,
        changes={"format": (job.payload or {}).get("format"), "layers": layers},
    )
    db.commit()

    filename = os.path.basename(job.result_path)
    content_type = "application/octet-stream"
    if filename.endswith(".geojson") or filename.endswith(".json"):
        content_type = "application/geo+json"
    elif filename.endswith(".kml"):
        content_type = "application/vnd.google-earth.kml+xml"
    elif filename.endswith(".csv"):
        content_type = "text/csv; charset=utf-8"

    return FileResponse(
        path=job.result_path,
        media_type=content_type,
        filename=filename,
    )


# ==============================================================================
# JOBS (Fila de Tarefas Assíncronas)
# ==============================================================================
@imports_exports_router.get(
    "/jobs/{job_id}",
    response_model=JobRead,
    summary="Consultar status de job assíncrono",
    dependencies=[Depends(get_current_user)],
)
def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobRead:
    job = get_job_by_id(db=db, job_id=job_id)
    # Leitura conforme o tipo: exportações exigem exports:read; importações, imports:read
    permission = "exports:read" if job.type.value.startswith("export_") else "imports:read"
    if not user_can(current_user, permission):
        raise ForbiddenError(
            f"Acesso negado. Requer a permissão '{permission}'.", code="insufficient_permissions"
        )
    return job


@imports_exports_router.post(
    "/jobs/{job_id}/cancel",
    response_model=JobRead,
    summary="Cancelar execução de job",
    dependencies=[Depends(require_permission("imports:write")), Depends(validate_csrf)],
)
def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobRead:
    return cancel_job_by_id(db=db, job_id=job_id, user=current_user)
