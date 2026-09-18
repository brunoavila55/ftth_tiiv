import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission, validate_csrf
from app.db.session import get_db
from app.modules.connectivity import service
from app.modules.identity.models import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.connectivity import (
    ConnectionBatchRequest,
    ConnectionBatchResponse,
    ConnectionCreate,
    ConnectionRead,
)

connectivity_router = APIRouter(prefix="/connections", tags=["Conectividade e Fusões"])


@connectivity_router.get(
    "", response_model=PaginatedResponse[ConnectionRead], summary="Listar conexões ópticas"
)
def list_connections(
    pagination: PaginationParams = Depends(),
    structure_id: str | None = Query(
        default=None, description="Filtrar por estrutura física (CEO/CTO)"
    ),
    is_active: bool | None = Query(
        default=True, description="Filtrar por conexões ativas ou inativas"
    ),
    current_user: User = Depends(require_permission("network:read")),
    db: Session = Depends(get_db),
) -> Any:
    struct_uuid = uuid.UUID(structure_id) if structure_id else None
    items, total = service.list_connections(
        db,
        structure_id=struct_uuid,
        is_active=is_active,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return PaginatedResponse[ConnectionRead](
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@connectivity_router.post(
    "",
    response_model=ConnectionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar conexão óptica unitária",
    dependencies=[Depends(validate_csrf)],
)
def create_connection(
    payload: ConnectionCreate,
    request: Request,
    current_user: User = Depends(require_permission("network:write")),
    db: Session = Depends(get_db),
) -> Any:
    request_id = getattr(request.state, "request_id", None)
    return service.create_connection(
        db,
        actor_id=current_user.id,
        actor_name=current_user.name,
        payload=payload,
        request_id=request_id,
    )


@connectivity_router.get(
    "/{connection_id}", response_model=ConnectionRead, summary="Detalhes da conexão óptica"
)
def get_connection(
    connection_id: str,
    current_user: User = Depends(require_permission("network:read")),
    db: Session = Depends(get_db),
) -> Any:
    return service.get_connection_by_id(db, uuid.UUID(connection_id))


@connectivity_router.delete(
    "/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desfazer conexão óptica",
    dependencies=[Depends(validate_csrf)],
)
def delete_connection(
    connection_id: str,
    request: Request,
    if_match: str | None = Header(default=None, description="Versão atual do recurso (If-Match)"),
    current_user: User = Depends(require_permission("network:write")),
    db: Session = Depends(get_db),
) -> None:
    request_id = getattr(request.state, "request_id", None)
    service.deactivate_connection(
        db,
        actor_id=current_user.id,
        actor_name=current_user.name,
        connection_id=uuid.UUID(connection_id),
        if_match=if_match,
        request_id=request_id,
    )


@connectivity_router.post(
    "/batch",
    response_model=ConnectionBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Operações de fusão e conexão em lote (Editor de Fusão)",
    description=(
        "Aplica conjunto transacional de conexões, desconexões e reservas em uma caixa CEO/CTO. "
        "Exige expected_topology_revision e incrementa atomicamente a revisão topológica."
    ),
    dependencies=[Depends(validate_csrf)],
)
def batch_connections(
    payload: ConnectionBatchRequest,
    request: Request,
    current_user: User = Depends(require_permission("network:write")),
    db: Session = Depends(get_db),
) -> Any:
    request_id = getattr(request.state, "request_id", None)
    return service.execute_batch_connections(
        db,
        actor_id=current_user.id,
        actor_name=current_user.name,
        payload=payload,
        request_id=request_id,
    )
