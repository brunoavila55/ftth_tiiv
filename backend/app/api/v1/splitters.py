from typing import Any

from fastapi import APIRouter, Depends, Header, Query, status

from app.core.contracts import pending_endpoint
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.splitters import SplitterCreate, SplitterRead, SplitterUpdate

splitters_router = APIRouter(prefix="/splitters", tags=["Splitters"])


@splitters_router.get(
    "", response_model=PaginatedResponse[SplitterRead], summary="Listar splitters"
)
def list_splitters(
    pagination: PaginationParams = Depends(),
    structure_id: str | None = Query(
        default=None, description="Filtrar por estrutura alojadora (CTO/CEO)"
    ),
) -> Any:
    pending_endpoint("B08")


@splitters_router.post(
    "",
    response_model=SplitterRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar splitter",
)
def create_splitter(payload: SplitterCreate) -> Any:
    pending_endpoint("B08")


@splitters_router.get("/{splitter_id}", response_model=SplitterRead, summary="Detalhes do splitter")
def get_splitter(splitter_id: str) -> Any:
    pending_endpoint("B08")


@splitters_router.patch("/{splitter_id}", response_model=SplitterRead, summary="Atualizar splitter")
def update_splitter(
    splitter_id: str,
    payload: SplitterUpdate,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> Any:
    pending_endpoint("B08")


@splitters_router.delete(
    "/{splitter_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Desativar splitter"
)
def delete_splitter(
    splitter_id: str,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> None:
    pending_endpoint("B08")
