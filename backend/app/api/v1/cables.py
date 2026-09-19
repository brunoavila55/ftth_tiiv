from typing import Any

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission, validate_csrf
from app.db.session import get_db
from app.modules.cables import service
from app.modules.identity.models import User
from app.schemas.cables import (
    CableCreate,
    CableRead,
    CableSegmentCreate,
    CableSegmentRead,
    CableSegmentUpdate,
    CableUpdate,
    FiberSegmentRead,
    SegmentSplitPreviewResponse,
    SegmentSplitRequest,
    SegmentSplitResponse,
)
from app.schemas.common import PaginatedResponse, PaginationParams, UuidStr

cables_router = APIRouter(tags=["Cabos e Fibras"])


# ==============================================================================
# CABLES (Cabos ópticos)
# ==============================================================================
@cables_router.get(
    "/cables",
    response_model=PaginatedResponse[CableRead],
    summary="Listar cabos ópticos",
)
def list_cables(
    pagination: PaginationParams = Depends(),
    q: str | None = Query(default=None, description="Busca por código ou modelo do cabo"),
    current_user: User = Depends(require_permission("network:read")),
    db: Session = Depends(get_db),
) -> Any:
    offset = (pagination.page - 1) * pagination.page_size
    items, total = service.list_cables(db=db, limit=pagination.page_size, offset=offset, q=q)
    return PaginatedResponse[CableRead](
        items=[service.cable_to_schema(c) for c in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@cables_router.post(
    "/cables",
    response_model=CableRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar cabo óptico",
    dependencies=[Depends(validate_csrf)],
)
def create_cable(
    payload: CableCreate,
    current_user: User = Depends(require_permission("network:write")),
    db: Session = Depends(get_db),
) -> Any:
    cable = service.create_cable(db=db, payload=payload)
    return service.cable_to_schema(cable)


@cables_router.get(
    "/cables/{cable_id}",
    response_model=CableRead,
    summary="Detalhes do cabo óptico",
)
def get_cable(
    cable_id: UuidStr,
    current_user: User = Depends(require_permission("network:read")),
    db: Session = Depends(get_db),
) -> Any:
    cable = service.get_cable_by_id(db=db, cable_id=cable_id)
    return service.cable_to_schema(cable)


@cables_router.patch(
    "/cables/{cable_id}",
    response_model=CableRead,
    summary="Atualizar cabo óptico",
    dependencies=[Depends(validate_csrf)],
)
def update_cable(
    cable_id: UuidStr,
    payload: CableUpdate,
    if_match: str | None = Header(default=None, description="Versão atual do recurso (If-Match)"),
    current_user: User = Depends(require_permission("network:write")),
    db: Session = Depends(get_db),
) -> Any:
    cable = service.update_cable(db=db, cable_id=cable_id, payload=payload, if_match=if_match)
    return service.cable_to_schema(cable)


@cables_router.delete(
    "/cables/{cable_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar cabo óptico",
    dependencies=[Depends(validate_csrf)],
)
def delete_cable(
    cable_id: UuidStr,
    if_match: str | None = Header(default=None, description="Versão atual do recurso (If-Match)"),
    current_user: User = Depends(require_permission("network:write")),
    db: Session = Depends(get_db),
) -> None:
    service.delete_cable(db=db, cable_id=cable_id, if_match=if_match)


# ==============================================================================
# CABLE SEGMENTS (Trechos de cabos entre estruturas)
# ==============================================================================
@cables_router.get(
    "/cable-segments",
    response_model=PaginatedResponse[CableSegmentRead],
    summary="Listar trechos de cabos",
)
def list_cable_segments(
    pagination: PaginationParams = Depends(),
    cable_id: UuidStr | None = Query(default=None, description="Filtrar por UUID do cabo"),
    current_user: User = Depends(require_permission("network:read")),
    db: Session = Depends(get_db),
) -> Any:
    offset = (pagination.page - 1) * pagination.page_size
    items, total = service.list_cable_segments(
        db=db, limit=pagination.page_size, offset=offset, cable_id=cable_id
    )
    return PaginatedResponse[CableSegmentRead](
        items=[service.cable_segment_to_schema(s) for s in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@cables_router.post(
    "/cable-segments",
    response_model=CableSegmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar trecho de cabo",
    dependencies=[Depends(validate_csrf)],
)
def create_cable_segment(
    payload: CableSegmentCreate,
    current_user: User = Depends(require_permission("network:write")),
    db: Session = Depends(get_db),
) -> Any:
    segment = service.create_cable_segment(db=db, payload=payload)
    return service.cable_segment_to_schema(segment)


@cables_router.get(
    "/cable-segments/{segment_id}",
    response_model=CableSegmentRead,
    summary="Detalhes do trecho de cabo",
)
def get_cable_segment(
    segment_id: UuidStr,
    current_user: User = Depends(require_permission("network:read")),
    db: Session = Depends(get_db),
) -> Any:
    segment = service.get_cable_segment_by_id(db=db, segment_id=segment_id)
    return service.cable_segment_to_schema(segment)


@cables_router.patch(
    "/cable-segments/{segment_id}",
    response_model=CableSegmentRead,
    summary="Atualizar trecho de cabo",
    dependencies=[Depends(validate_csrf)],
)
def update_cable_segment(
    segment_id: UuidStr,
    payload: CableSegmentUpdate,
    if_match: str | None = Header(default=None, description="Versão atual do recurso (If-Match)"),
    current_user: User = Depends(require_permission("network:write")),
    db: Session = Depends(get_db),
) -> Any:
    segment = service.update_cable_segment(
        db=db, segment_id=segment_id, payload=payload, if_match=if_match
    )
    return service.cable_segment_to_schema(segment)


@cables_router.delete(
    "/cable-segments/{segment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar trecho de cabo",
    dependencies=[Depends(validate_csrf)],
)
def delete_cable_segment(
    segment_id: UuidStr,
    if_match: str | None = Header(default=None, description="Versão atual do recurso (If-Match)"),
    current_user: User = Depends(require_permission("network:write")),
    db: Session = Depends(get_db),
) -> None:
    service.delete_cable_segment(db=db, segment_id=segment_id, if_match=if_match)


@cables_router.get(
    "/cable-segments/{segment_id}/fibers",
    response_model=PaginatedResponse[FiberSegmentRead],
    summary="Listar fibras de um trecho",
)
def list_segment_fibers(
    segment_id: UuidStr,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(require_permission("network:read")),
    db: Session = Depends(get_db),
) -> Any:
    offset = (pagination.page - 1) * pagination.page_size
    items, total = service.list_segment_fibers(
        db=db, segment_id=segment_id, limit=pagination.page_size, offset=offset
    )
    return PaginatedResponse[FiberSegmentRead](
        items=[service.fiber_segment_to_schema(fs) for fs in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@cables_router.post(
    "/cable-segments/{segment_id}/split/preview",
    response_model=SegmentSplitPreviewResponse,
    summary="Pré-visualizar divisão de trecho de cabo",
)
def preview_segment_split(
    segment_id: UuidStr,
    payload: SegmentSplitRequest,
    current_user: User = Depends(require_permission("network:read")),
    db: Session = Depends(get_db),
) -> Any:
    return service.preview_split_segment(db=db, segment_id=segment_id, payload=payload)


@cables_router.post(
    "/cable-segments/{segment_id}/split",
    response_model=SegmentSplitResponse,
    summary="Dividir trecho de cabo em local de acesso",
    dependencies=[Depends(validate_csrf)],
)
def split_segment(
    segment_id: UuidStr,
    payload: SegmentSplitRequest,
    if_match: str | None = Header(
        default=None,
        description="Versão do trecho (If-Match). Obrigatório se expected_topology_revision faltar.",
    ),
    current_user: User = Depends(require_permission("network:write")),
    db: Session = Depends(get_db),
) -> Any:
    return service.split_cable_segment(
        db=db, segment_id=segment_id, payload=payload, if_match=if_match
    )
