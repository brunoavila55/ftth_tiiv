from typing import Any

from fastapi import APIRouter, Depends, Header, Query, status

from app.core.contracts import pending_endpoint
from app.schemas.common import PaginatedResponse, PaginationParams
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
# CUSTOMERS (Clientes)
# ==============================================================================
@customers_router.get(
    "/customers", response_model=PaginatedResponse[CustomerRead], summary="Listar clientes"
)
def list_customers(
    pagination: PaginationParams = Depends(),
    q: str | None = Query(default=None, description="Busca por código ou nome do cliente"),
) -> Any:
    pending_endpoint("B08")


@customers_router.post(
    "/customers",
    response_model=CustomerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar cliente",
)
def create_customer(payload: CustomerCreate) -> Any:
    pending_endpoint("B08")


@customers_router.get(
    "/customers/{customer_id}", response_model=CustomerRead, summary="Detalhes do cliente"
)
def get_customer(customer_id: str) -> Any:
    pending_endpoint("B08")


@customers_router.patch(
    "/customers/{customer_id}", response_model=CustomerRead, summary="Atualizar cliente"
)
def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> Any:
    pending_endpoint("B08")


@customers_router.delete(
    "/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Desativar cliente"
)
def delete_customer(
    customer_id: str,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> None:
    pending_endpoint("B08")


# ==============================================================================
# SERVICE LINKS (Atendimentos / Vínculo Cliente <-> ONU <-> Porta CTO)
# ==============================================================================
@customers_router.get(
    "/service-links",
    response_model=PaginatedResponse[ServiceLinkRead],
    summary="Listar atendimentos ópticos",
)
def list_service_links(
    pagination: PaginationParams = Depends(),
    customer_id: str | None = Query(default=None),
    port_id: str | None = Query(default=None),
) -> Any:
    pending_endpoint("B08")


@customers_router.post(
    "/service-links",
    response_model=ServiceLinkRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ativar atendimento de cliente",
)
def create_service_link(payload: ServiceLinkCreate) -> Any:
    pending_endpoint("B08")


@customers_router.get(
    "/service-links/{link_id}", response_model=ServiceLinkRead, summary="Detalhes do atendimento"
)
def get_service_link(link_id: str) -> Any:
    pending_endpoint("B08")


@customers_router.patch(
    "/service-links/{link_id}",
    response_model=ServiceLinkRead,
    summary="Atualizar status do atendimento",
)
def update_service_link(
    link_id: str,
    payload: ServiceLinkUpdate,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> Any:
    pending_endpoint("B08")


@customers_router.delete(
    "/service-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar atendimento",
)
def delete_service_link(
    link_id: str,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> None:
    pending_endpoint("B08")
