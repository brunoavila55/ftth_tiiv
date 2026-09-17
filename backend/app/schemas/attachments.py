from datetime import datetime

from pydantic import BaseModel, Field


class AttachmentRead(BaseModel):
    id: str = Field(..., description="UUID do anexo armazenado")
    entity_id: str = Field(
        ..., description="UUID da entidade proprietária (site, structure, device, customer)"
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
    version: int
    created_at: datetime
