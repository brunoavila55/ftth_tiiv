from typing import Any

from fastapi import APIRouter, Depends, Header, Query, status

from app.core.contracts import pending_endpoint
from app.schemas.cables import (
    CableCreate,
    CableRead,
    CableSegmentCreate,
    CableSegmentRead,
    CableSegmentUpdate,
    CableUpdate,
    FiberSegmentRead,
)
from app.schemas.common import PaginatedResponse, PaginationParams

cables_router = APIRouter(tags=["Cabos e Fibras"])


# ==============================================================================
# CABLES (Cabos ópticos)
# ==============================================================================
@cables_router.get(
    "/cables", response_model=PaginatedResponse[CableRead], summary="Listar cabos ópticos"
)
def list_cables(
    pagination: PaginationParams = Depends(),
    q: str | None = Query(default=None, description="Busca por código do cabo"),
) -> Any:
    pending_endpoint("B06")


@cables_router.post(
    "/cables",
    response_model=CableRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar cabo óptico",
)
def create_cable(payload: CableCreate) -> Any:
    pending_endpoint("B06")


@cables_router.get(
    "/cables/{cable_id}", response_model=CableRead, summary="Detalhes do cabo óptico"
)
def get_cable(cable_id: str) -> Any:
    pending_endpoint("B06")


@cables_router.patch(
    "/cables/{cable_id}", response_model=CableRead, summary="Atualizar cabo óptico"
)
def update_cable(
    cable_id: str,
    payload: CableUpdate,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> Any:
    pending_endpoint("B06")


@cables_router.delete(
    "/cables/{cable_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Desativar cabo óptico"
)
def delete_cable(
    cable_id: str,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> None:
    pending_endpoint("B06")


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
    cable_id: str | None = Query(default=None, description="Filtrar por UUID do cabo"),
) -> Any:
    pending_endpoint("B06")


@cables_router.post(
    "/cable-segments",
    response_model=CableSegmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar trecho de cabo",
)
def create_cable_segment(payload: CableSegmentCreate) -> Any:
    pending_endpoint("B06")


@cables_router.get(
    "/cable-segments/{segment_id}",
    response_model=CableSegmentRead,
    summary="Detalhes do trecho de cabo",
)
def get_cable_segment(segment_id: str) -> Any:
    pending_endpoint("B06")


@cables_router.patch(
    "/cable-segments/{segment_id}",
    response_model=CableSegmentRead,
    summary="Atualizar trecho de cabo",
)
def update_cable_segment(
    segment_id: str,
    payload: CableSegmentUpdate,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> Any:
    pending_endpoint("B06")


@cables_router.delete(
    "/cable-segments/{segment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar trecho de cabo",
)
def delete_cable_segment(
    segment_id: str,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> None:
    pending_endpoint("B06")


@cables_router.get(
    "/cable-segments/{segment_id}/fibers",
    response_model=PaginatedResponse[FiberSegmentRead],
    summary="Listar fibras de um trecho",
)
def list_segment_fibers(
    segment_id: str,
    pagination: PaginationParams = Depends(),
) -> Any:
    pending_endpoint("B06")
