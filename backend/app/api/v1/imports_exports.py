from typing import Any

from fastapi import APIRouter, File, Header, Response, UploadFile, status

from app.core.contracts import pending_endpoint
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
)
def preview_import(file: UploadFile = File(..., description="Arquivo GeoJSON, KML ou CSV")) -> Any:
    pending_endpoint("B14")


@imports_exports_router.get(
    "/imports/{import_id}",
    response_model=ImportPreviewResponse,
    summary="Consultar resultado de prévia de importação",
)
def get_import_preview(import_id: str) -> Any:
    pending_endpoint("B14")


@imports_exports_router.post(
    "/imports/{import_id}/commit",
    response_model=ImportCommitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Confirmar importação de dados",
    description="Dispara processamento em lote transacional e idempotente com Idempotency-Key.",
)
def commit_import(
    import_id: str,
    payload: ImportCommitRequest,
    idempotency_key: str = Header(..., description="Chave de idempotência única da operação"),
) -> Any:
    pending_endpoint("B14")


# ==============================================================================
# EXPORTS (GeoJSON, KML, CSV)
# ==============================================================================
@imports_exports_router.post(
    "/exports",
    response_model=ExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Solicitar exportação de dados",
)
def request_export(payload: ExportRequest) -> Any:
    pending_endpoint("B14")


@imports_exports_router.get(
    "/exports/{export_id}",
    response_model=JobRead,
    summary="Status da exportação",
)
def get_export_status(export_id: str) -> Any:
    pending_endpoint("B14")


@imports_exports_router.get(
    "/exports/{export_id}/download",
    summary="Download do arquivo exportado",
)
def download_export(export_id: str) -> Response:
    pending_endpoint("B14")


# ==============================================================================
# JOBS (Fila de Tarefas Assíncronas)
# ==============================================================================
@imports_exports_router.get(
    "/jobs/{job_id}",
    response_model=JobRead,
    summary="Consultar status de job assíncrono",
)
def get_job(job_id: str) -> Any:
    pending_endpoint("B14")


@imports_exports_router.post(
    "/jobs/{job_id}/cancel",
    response_model=JobRead,
    summary="Cancelar execução de job",
)
def cancel_job(job_id: str) -> Any:
    pending_endpoint("B14")
