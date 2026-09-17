from typing import Any

from fastapi import APIRouter, Depends, Header, Query, status

from app.core.contracts import pending_endpoint
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
) -> Any:
    pending_endpoint("B07")


@connectivity_router.post(
    "",
    response_model=ConnectionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar conexão óptica unitária",
)
def create_connection(payload: ConnectionCreate) -> Any:
    pending_endpoint("B07")


@connectivity_router.get(
    "/{connection_id}", response_model=ConnectionRead, summary="Detalhes da conexão óptica"
)
def get_connection(connection_id: str) -> Any:
    pending_endpoint("B07")


@connectivity_router.delete(
    "/{connection_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Desfazer conexão óptica"
)
def delete_connection(
    connection_id: str,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> None:
    pending_endpoint("B07")


@connectivity_router.post(
    "/batch",
    response_model=ConnectionBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Operações de fusão e conexão em lote (Editor de Fusão)",
    description=(
        "Aplica conjunto transacional de conexões, desconexões e reservas em uma caixa CEO/CTO. "
        "Exige expected_topology_revision e incrementa atomicamente a revisão topológica."
    ),
)
def batch_connections(payload: ConnectionBatchRequest) -> Any:
    pending_endpoint("B07")
