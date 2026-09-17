from typing import Any

from fastapi import APIRouter, File, Form, Header, Response, UploadFile, status

from app.core.contracts import pending_endpoint
from app.schemas.attachments import AttachmentRead

attachments_router = APIRouter(prefix="/attachments", tags=["Anexos e Fotos"])


@attachments_router.post(
    "",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload de anexo ou foto de campo",
    description="Armazena arquivo de imagem ou PDF com verificação de tipo de conteúdo e isolamento de path traversal.",
)
def upload_attachment(
    entity_id: str = Form(
        ..., description="UUID da entidade associada (ex: estrutura, site, cliente)"
    ),
    entity_type: str = Form(
        ..., description="Tipo da entidade (structure, site, customer, device)"
    ),
    file: UploadFile = File(..., description="Arquivo binário (JPEG, PNG, WebP ou PDF)"),
) -> Any:
    pending_endpoint("B13")


@attachments_router.get(
    "/{attachment_id}/download",
    summary="Download de anexo",
    description="Faz o download seguro de arquivo após validação das credenciais e permissões do usuário.",
)
def download_attachment(attachment_id: str) -> Response:
    pending_endpoint("B13")


@attachments_router.delete(
    "/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir anexo",
    description="Remove anexo e seus metadados. Exige cabeçalho If-Match.",
)
def delete_attachment(
    attachment_id: str,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> None:
    pending_endpoint("B13")
