from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="UUID do anexo armazenado")
    entity_id: str = Field(
        ..., description="UUID da entidade proprietária (site, structure, device, customer, etc.)"
    )
    entity_type: str = Field(..., description="Tipo da entidade vinculada")
    file_name: str = Field(..., description="Nome de arquivo seguro sanitizado")
    mime_type: str = Field(..., description="MIME type validado por inspeção de cabeçalho")
    file_size_bytes: int = Field(..., ge=0, description="Tamanho do arquivo em bytes")
    download_url: str = Field(
        ..., description="URL autorizada de download da API (/attachments/{id}/download)"
    )
    thumbnail_url: str | None = Field(
        default=None, description="URL da miniatura otimizada se o arquivo for imagem suportada"
    )
    caption: str | None = Field(default=None, description="Legenda ou anotação do anexo")
    checksum_sha256: str | None = Field(default=None, description="Hash SHA-256 do arquivo")
    user_id: str | None = Field(default=None, description="UUID do usuário autor do upload")
    version: int = Field(..., description="Versão do registro para concorrência otimista")
    created_at: datetime


class AttachmentUpdate(BaseModel):
    caption: str | None = Field(
        default=None, max_length=255, description="Legenda ou anotação do anexo"
    )


class AttachmentReconciliationResponse(BaseModel):
    total_disk_files: int = Field(..., description="Total de arquivos encontrados em disco")
    total_db_records: int = Field(..., description="Total de registros no banco de dados")
    orphans_removed: list[str] = Field(
        default_factory=list, description="Arquivos órfãos sem registro que foram excluídos"
    )
    missing_disk_files: list[str] = Field(
        default_factory=list,
        description="Registros no banco cujos arquivos físicos estão ausentes",
    )
