import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission, validate_csrf
from app.core.permissions import has_permission
from app.db.session import get_db
from app.modules.customers import service
from app.modules.identity.models import User
from app.schemas.common import PaginatedResponse, PaginationParams, UserRole, UuidStr
from app.schemas.customers import (
    CustomerCreate,
    CustomerRead,
    CustomerUpdate,
    ServiceLinkCreate,
    ServiceLinkRead,
    ServiceLinkUpdate,
)

customers_router = APIRouter(tags=["Clientes e Atendimentos"])


# ==============================================================================
# CUSTOMERS (Clientes / Assinantes)
# ==============================================================================
@customers_router.get(
    "/customers",
    response_model=PaginatedResponse[CustomerRead],
    summary="Listar clientes",
    dependencies=[Depends(require_permission("customers:read"))],
)
def list_customers(
    pagination: PaginationParams = Depends(),
    q: str | None = Query(default=None, description="Busca por código ou nome do cliente"),
    db: Session = Depends(get_db),
) -> Any:
    items, total = service.list_customers(
        db, q=q, page=pagination.page, page_size=pagination.page_size
    )
    return PaginatedResponse[CustomerRead](
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@customers_router.post(
    "/customers",
    response_model=CustomerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar cliente",
    dependencies=[Depends(require_permission("customers:write")), Depends(validate_csrf)],
)
def create_customer(
    payload: CustomerCreate,
    request: Request,
    current_user: User = Depends(require_permission("customers:write")),
    db: Session = Depends(get_db),
) -> Any:
    request_id = getattr(request.state, "request_id", None)
    return service.create_customer(
        db,
        actor_id=current_user.id,
        actor_name=current_user.name,
        payload=payload,
        request_id=request_id,
    )


@customers_router.get(
    "/customers/{customer_id}",
    response_model=CustomerRead,
    summary="Detalhes do cliente",
    dependencies=[Depends(require_permission("customers:read"))],
)
def get_customer(
    customer_id: UuidStr,
    db: Session = Depends(get_db),
) -> Any:
    return service.get_customer_by_id(db, uuid.UUID(customer_id))


@customers_router.patch(
    "/customers/{customer_id}",
    response_model=CustomerRead,
    summary="Atualizar cliente",
    dependencies=[Depends(require_permission("customers:write")), Depends(validate_csrf)],
)
def update_customer(
    customer_id: UuidStr,
    payload: CustomerUpdate,
    request: Request,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
    current_user: User = Depends(require_permission("customers:write")),
    db: Session = Depends(get_db),
) -> Any:
    request_id = getattr(request.state, "request_id", None)
    return service.update_customer(
        db,
        actor_id=current_user.id,
        actor_name=current_user.name,
        customer_id=uuid.UUID(customer_id),
        payload=payload,
        if_match=if_match,
        request_id=request_id,
    )


@customers_router.delete(
    "/customers/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar cliente",
    dependencies=[Depends(require_permission("customers:write")), Depends(validate_csrf)],
)
def delete_customer(
    customer_id: UuidStr,
    request: Request,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
    current_user: User = Depends(require_permission("customers:write")),
    db: Session = Depends(get_db),
) -> None:
    request_id = getattr(request.state, "request_id", None)
    service.delete_customer(
        db,
        actor_id=current_user.id,
        actor_name=current_user.name,
        customer_id=uuid.UUID(customer_id),
        if_match=if_match,
        request_id=request_id,
    )


# ==============================================================================
# SERVICE LINKS (Atendimentos / Vínculo Cliente <-> ONU <-> Porta CTO)
# ==============================================================================
@customers_router.get(
    "/service-links",
    response_model=PaginatedResponse[ServiceLinkRead],
    summary="Listar atendimentos ópticos",
    dependencies=[Depends(require_permission("customers:read"))],
)
def list_service_links(
    pagination: PaginationParams = Depends(),
    customer_id: UuidStr | None = Query(default=None),
    port_id: UuidStr | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Any:
    cust_uuid = uuid.UUID(customer_id) if customer_id else None
    port_uuid = uuid.UUID(port_id) if port_id else None
    items, total = service.list_service_links(
        db,
        customer_id=cust_uuid,
        port_id=port_uuid,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return PaginatedResponse[ServiceLinkRead](
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@customers_router.post(
    "/service-links",
    response_model=ServiceLinkRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ativar atendimento de cliente",
    dependencies=[Depends(require_permission("customers:write")), Depends(validate_csrf)],
)
def create_service_link(
    payload: ServiceLinkCreate,
    request: Request,
    current_user: User = Depends(require_permission("customers:write")),
    db: Session = Depends(get_db),
) -> Any:
    request_id = getattr(request.state, "request_id", None)
    return service.create_service_link(
        db,
        actor_id=current_user.id,
        actor_name=current_user.name,
        payload=payload,
        request_id=request_id,
    )


@customers_router.get(
    "/service-links/{link_id}",
    response_model=ServiceLinkRead,
    summary="Detalhes do atendimento",
    dependencies=[Depends(require_permission("customers:read"))],
)
def get_service_link(
    link_id: UuidStr,
    db: Session = Depends(get_db),
) -> Any:
    return service.get_service_link_by_id(db, uuid.UUID(link_id))


@customers_router.patch(
    "/service-links/{link_id}",
    response_model=ServiceLinkRead,
    summary="Atualizar status do atendimento",
    dependencies=[Depends(require_permission("customers:write")), Depends(validate_csrf)],
)
def update_service_link(
    link_id: UuidStr,
    payload: ServiceLinkUpdate,
    request: Request,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
    current_user: User = Depends(require_permission("customers:write")),
    db: Session = Depends(get_db),
) -> Any:
    request_id = getattr(request.state, "request_id", None)
    return service.update_service_link(
        db,
        actor_id=current_user.id,
        actor_name=current_user.name,
        link_id=uuid.UUID(link_id),
        payload=payload,
        if_match=if_match,
        request_id=request_id,
    )


@customers_router.delete(
    "/service-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar atendimento",
    dependencies=[Depends(require_permission("customers:write")), Depends(validate_csrf)],
)
def delete_service_link(
    link_id: UuidStr,
    request: Request,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
    current_user: User = Depends(require_permission("customers:write")),
    db: Session = Depends(get_db),
) -> None:
    request_id = getattr(request.state, "request_id", None)
    service.deactivate_service_link(
        db,
        actor_id=current_user.id,
        actor_name=current_user.name,
        link_id=uuid.UUID(link_id),
        if_match=if_match,
        request_id=request_id,
    )


@customers_router.get(
    "/structures/{structure_id}/cto-occupancy",
    summary="Ocupação das portas da CTO",
    description="Estado das portas (network:read). Dados pessoais do cliente só com customers:read.",
)
def get_cto_occupancy(
    structure_id: UuidStr,
    current_user: User = Depends(require_permission("network:read")),
    db: Session = Depends(get_db),
) -> Any:
    return service.get_cto_port_occupancy(
        db,
        uuid.UUID(structure_id),
        include_customer_details=has_permission(UserRole(current_user.role), "customers:read"),
    )
