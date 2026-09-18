import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission, validate_csrf
from app.core.privacy import require_customer_access, user_can
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.modules.attachments.service import (
    build_attachment_read,
    get_attachment_by_id,
    list_attachments_paginated,
    reconcile_storage_orphans,
    resolve_attachment_file_path,
    save_attachment,
)
from app.modules.attachments.service import (
    delete_attachment as delete_attachment_service,
)
from app.modules.identity.models import User
from app.schemas.attachments import AttachmentRead, AttachmentReconciliationResponse
from app.schemas.common import PaginatedResponse, PaginationParams

attachments_router = APIRouter(prefix="/attachments", tags=["Anexos e Fotos"])


@attachments_router.post(
    "",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload de anexo ou foto de campo",
    description="Armazena arquivo de imagem ou PDF com verificação de tipo de conteúdo e isolamento de path traversal.",
    dependencies=[
        Depends(validate_csrf),
        Depends(rate_limit("upload", "RATE_LIMIT_UPLOAD_PER_MINUTE")),
    ],
)
async def upload_attachment(
    entity_id: str = Form(
        ..., description="UUID da entidade associada (ex: estrutura, site, cliente)"
    ),
    entity_type: str = Form(
        ...,
        max_length=50,
        description="Tipo da entidade (structure, site, customer, device, etc.)",
    ),
    caption: str | None = Form(
        default=None, max_length=255, description="Legenda opcional ou anotação do anexo"
    ),
    file: UploadFile = File(..., description="Arquivo binário (JPEG, PNG, WebP ou PDF)"),
    current_user: User = Depends(require_permission("attachments:write")),
    db: Session = Depends(get_db),
) -> AttachmentRead:
    require_customer_access(current_user, entity_type, write=True)
    try:
        e_uuid = uuid.UUID(entity_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"entity_id inválido: '{entity_id}' não é um UUID válido",
        ) from err

    raw_content = await file.read()
    filename = file.filename or "anexo"

    return save_attachment(
        db,
        entity_id=e_uuid,
        entity_type=entity_type,
        raw_content=raw_content,
        original_filename=filename,
        caption=caption,
        user_id=current_user.id,
        user_name=current_user.name,
    )


@attachments_router.get(
    "",
    response_model=PaginatedResponse[AttachmentRead],
    summary="Listar anexos com paginação e filtros",
    description="Retorna lista paginada de anexos cadastrados com filtro opcional por entidade.",
)
def list_attachments_endpoint(
    pagination: PaginationParams = Depends(),
    entity_type: str | None = Query(default=None, description="Filtrar por tipo de entidade"),
    entity_id: str | None = Query(default=None, description="Filtrar por UUID da entidade"),
    current_user: User = Depends(require_permission("attachments:read")),
    db: Session = Depends(get_db),
) -> PaginatedResponse[AttachmentRead]:
    if entity_type:
        require_customer_access(current_user, entity_type)
    e_uuid: uuid.UUID | None = None
    if entity_id:
        try:
            e_uuid = uuid.UUID(entity_id)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"entity_id inválido: '{entity_id}'",
            ) from err

    items, total = list_attachments_paginated(
        db,
        entity_type=entity_type,
        entity_id=e_uuid,
        limit=pagination.page_size,
        offset=(pagination.page - 1) * pagination.page_size,
        include_customer_pii=user_can(current_user, "customers:read"),
    )

    results = [build_attachment_read(a) for a in items]

    return PaginatedResponse[AttachmentRead](
        items=results,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@attachments_router.get(
    "/{attachment_id}",
    response_model=AttachmentRead,
    summary="Obter metadados de anexo",
)
def get_attachment_metadata(
    attachment_id: str,
    current_user: User = Depends(require_permission("attachments:read")),
    db: Session = Depends(get_db),
) -> AttachmentRead:
    try:
        att_uuid = uuid.UUID(attachment_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"attachment_id inválido: '{attachment_id}'",
        ) from err

    attachment = get_attachment_by_id(db, att_uuid)
    require_customer_access(current_user, attachment.entity_type)
    return build_attachment_read(attachment)


@attachments_router.get(
    "/{attachment_id}/download",
    summary="Download de anexo autorizado",
    description="Faz o download seguro de arquivo após validação das credenciais e permissões do usuário.",
)
def download_attachment(
    attachment_id: str,
    current_user: User = Depends(require_permission("attachments:read")),
    db: Session = Depends(get_db),
) -> Response:
    try:
        att_uuid = uuid.UUID(attachment_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"attachment_id inválido: '{attachment_id}'",
        ) from err

    attachment = get_attachment_by_id(db, att_uuid)
    require_customer_access(current_user, attachment.entity_type)
    file_path = resolve_attachment_file_path(attachment, is_thumbnail=False)

    return FileResponse(
        path=str(file_path),
        media_type=attachment.content_type,
        filename=attachment.file_name,
        content_disposition_type="attachment",
    )


@attachments_router.get(
    "/{attachment_id}/thumbnail",
    summary="Obter miniatura de anexo",
    description="Retorna imagem otimizada em miniatura gerada com segurança.",
)
def get_attachment_thumbnail(
    attachment_id: str,
    current_user: User = Depends(require_permission("attachments:read")),
    db: Session = Depends(get_db),
) -> Response:
    try:
        att_uuid = uuid.UUID(attachment_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"attachment_id inválido: '{attachment_id}'",
        ) from err

    attachment = get_attachment_by_id(db, att_uuid)
    require_customer_access(current_user, attachment.entity_type)
    file_path = resolve_attachment_file_path(attachment, is_thumbnail=True)

    return FileResponse(
        path=str(file_path),
        media_type="image/webp",
    )


@attachments_router.delete(
    "/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir anexo",
    description="Remove anexo e seus metadados. Exige cabeçalho If-Match.",
    dependencies=[Depends(validate_csrf)],
)
def delete_attachment(
    attachment_id: str,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
    current_user: User = Depends(require_permission("attachments:write")),
    db: Session = Depends(get_db),
) -> Response:
    try:
        att_uuid = uuid.UUID(attachment_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"attachment_id inválido: '{attachment_id}'",
        ) from err

    try:
        expected_version = int(if_match.strip('"').strip())
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Header If-Match inválido: '{if_match}'. Deve ser um número inteiro.",
        ) from err

    existing = get_attachment_by_id(db, att_uuid)
    require_customer_access(current_user, existing.entity_type, write=True)
    delete_attachment_service(
        db,
        attachment_id=att_uuid,
        expected_version=expected_version,
        user_id=current_user.id,
        user_name=current_user.name,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@attachments_router.post(
    "/reconcile-orphans",
    response_model=AttachmentReconciliationResponse,
    summary="Reconciliar arquivos órfãos no armazenamento",
    description="Identifica e remove arquivos físicos no disco não associados a registros no banco sem excluir anexos válidos.",
    dependencies=[Depends(validate_csrf)],
)
def reconcile_orphans_endpoint(
    dry_run: bool = Query(default=False, description="Se verdadeiro, apenas simula sem deletar"),
    current_user: User = Depends(require_permission("settings:write")),
    db: Session = Depends(get_db),
) -> AttachmentReconciliationResponse:
    return reconcile_storage_orphans(db, dry_run=dry_run)
