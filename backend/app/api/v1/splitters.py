import uuid

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission, validate_csrf
from app.db.session import get_db
from app.modules.splitters import service
from app.schemas.common import PaginatedResponse, PaginationParams, UuidStr
from app.schemas.splitters import SplitterCreate, SplitterRead, SplitterUpdate

splitters_router = APIRouter(prefix="/splitters", tags=["Splitters"])


@splitters_router.get(
    "",
    response_model=PaginatedResponse[SplitterRead],
    summary="Listar splitters",
    dependencies=[Depends(require_permission("splitters:read"))],
)
def list_splitters(
    pagination: PaginationParams = Depends(),
    structure_id: UuidStr | None = Query(
        default=None, description="Filtrar por estrutura alojadora (CTO/CEO)"
    ),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SplitterRead]:
    items, total = service.list_splitters(
        db,
        structure_id=uuid.UUID(structure_id) if structure_id else None,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return PaginatedResponse[SplitterRead](
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@splitters_router.post(
    "",
    response_model=SplitterRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar splitter",
    dependencies=[Depends(require_permission("splitters:write")), Depends(validate_csrf)],
)
def create_splitter(
    payload: SplitterCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> SplitterRead:
    result = service.create_splitter(db, payload)
    response.headers["ETag"] = f'"{result.version}"'
    return result


@splitters_router.get(
    "/{splitter_id}",
    response_model=SplitterRead,
    summary="Detalhes do splitter",
    dependencies=[Depends(require_permission("splitters:read"))],
)
def get_splitter(
    splitter_id: UuidStr,
    response: Response,
    db: Session = Depends(get_db),
) -> SplitterRead:
    result = service.get_splitter(db, uuid.UUID(splitter_id))
    response.headers["ETag"] = f'"{result.version}"'
    return result


@splitters_router.patch(
    "/{splitter_id}",
    response_model=SplitterRead,
    summary="Atualizar splitter",
    dependencies=[Depends(require_permission("splitters:write")), Depends(validate_csrf)],
)
def update_splitter(
    splitter_id: UuidStr,
    payload: SplitterUpdate,
    response: Response,
    if_match: str | None = Header(default=None, description="Versão atual do recurso (If-Match)"),
    db: Session = Depends(get_db),
) -> SplitterRead:
    result = service.update_splitter(
        db,
        splitter_id=uuid.UUID(splitter_id),
        payload=payload,
        if_match=if_match,
    )
    response.headers["ETag"] = f'"{result.version}"'
    return result


@splitters_router.delete(
    "/{splitter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir splitter",
    dependencies=[Depends(require_permission("splitters:write")), Depends(validate_csrf)],
)
def delete_splitter(
    splitter_id: UuidStr,
    if_match: str | None = Header(default=None, description="Versão atual do recurso (If-Match)"),
    db: Session = Depends(get_db),
) -> None:
    service.delete_splitter(db, splitter_id=uuid.UUID(splitter_id), if_match=if_match)
