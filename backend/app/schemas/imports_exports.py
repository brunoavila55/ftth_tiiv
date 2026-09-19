from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

from app.schemas.common import UuidStr


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(StrEnum):
    IMPORT_COMMIT = "import_commit"
    EXPORT_GEOJSON = "export_geojson"
    EXPORT_KML = "export_kml"
    EXPORT_CSV = "export_csv"


class ImportFormat(StrEnum):
    GEOJSON = "geojson"
    KML = "kml"
    CSV = "csv"


class JobRead(BaseModel):
    id: str
    type: JobType
    status: JobStatus
    progress_percentage: int = Field(default=0, ge=0, le=100)
    error_message: str | None = None
    result_url: str | None = None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None


class ImportPreviewItem(BaseModel):
    line_number: int = Field(..., ge=1, description="Número da linha ou índice da feature")
    entity_code: str | None = Field(default=None, description="Código extraído da entidade")
    entity_type: str = Field(..., description="Tipo proposto (structure, cable, etc.)")
    validation_status: str = Field(..., description="'valid', 'error', 'collision'")
    message: str | None = Field(default=None, description="Diagnóstico detalhado da linha")


class ImportPreviewResponse(BaseModel):
    import_id: str = Field(..., description="UUID do rascunho de importação gerado")
    file_hash: str = Field(
        ..., description="Hash SHA-256 do arquivo original para garantia de integridade"
    )
    format: ImportFormat
    total_records: int
    valid_records: int
    error_records: int
    collision_records: int
    sample_preview: list[ImportPreviewItem]


class ImportCommitRequest(BaseModel):
    import_id: UuidStr = Field(..., description="UUID do preview aprovado pelo operador")
    file_hash: str = Field(
        ...,
        description="Hash que deve corresponder exatamente ao arquivo pré-visualizado",
        max_length=64,
    )


class ImportCommitResponse(BaseModel):
    job_id: str = Field(
        ..., description="UUID do job em segundo plano gerado para o processamento atômico"
    )
    message: str = "Importação colocada na fila com sucesso"


class ExportRequest(BaseModel):
    format: ImportFormat = Field(default=ImportFormat.GEOJSON)
    layers: list[Annotated[str, Field(max_length=50)]] = Field(
        default=["sites", "structures", "cables"],
        description="Camadas a exportar (ex: sites, structures, cables, ctos, ceos)",
        max_length=20,
    )


class ExportResponse(BaseModel):
    job_id: str
    message: str = "Solicitação de exportação registrada com sucesso"
