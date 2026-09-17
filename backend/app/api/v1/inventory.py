from typing import Any

from fastapi import APIRouter, Depends, Header, Query, status

from app.core.contracts import pending_endpoint
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.inventory import (
    DeviceCreate,
    DeviceKind,
    DeviceRead,
    DeviceUpdate,
    PortCreate,
    PortRead,
    PortUpdate,
    SiteCreate,
    SiteKind,
    SiteRead,
    SiteUpdate,
    StructureCreate,
    StructureKind,
    StructureOccupancyResponse,
    StructureRead,
    StructureUpdate,
)

inventory_router = APIRouter(tags=["Inventário"])


# ==============================================================================
# SITES (POPs / Locais Técnicos)
# ==============================================================================
@inventory_router.get(
    "/sites", response_model=PaginatedResponse[SiteRead], summary="Listar sites / POPs"
)
def list_sites(
    pagination: PaginationParams = Depends(),
    kind: SiteKind | None = Query(default=None),
    q: str | None = Query(default=None, description="Busca por código ou nome"),
) -> Any:
    pending_endpoint("B04")


@inventory_router.post(
    "/sites", response_model=SiteRead, status_code=status.HTTP_201_CREATED, summary="Criar site"
)
def create_site(payload: SiteCreate) -> Any:
    pending_endpoint("B04")


@inventory_router.get("/sites/{site_id}", response_model=SiteRead, summary="Detalhes do site")
def get_site(site_id: str) -> Any:
    pending_endpoint("B04")


@inventory_router.patch("/sites/{site_id}", response_model=SiteRead, summary="Atualizar site")
def update_site(
    site_id: str,
    payload: SiteUpdate,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> Any:
    pending_endpoint("B04")


@inventory_router.delete(
    "/sites/{site_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Desativar site"
)
def delete_site(
    site_id: str,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> None:
    pending_endpoint("B04")


# ==============================================================================
# STRUCTURES (Postes, CEOs, CTOs, Caixas)
# ==============================================================================
@inventory_router.get(
    "/structures", response_model=PaginatedResponse[StructureRead], summary="Listar estruturas"
)
def list_structures(
    pagination: PaginationParams = Depends(),
    kind: StructureKind | None = Query(
        default=None, description="Filtrar por tipo (ex: cto, ceo, pole)"
    ),
    q: str | None = Query(default=None, description="Busca por código"),
) -> Any:
    pending_endpoint("B04")


@inventory_router.post(
    "/structures",
    response_model=StructureRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar estrutura",
)
def create_structure(payload: StructureCreate) -> Any:
    pending_endpoint("B04")


@inventory_router.get(
    "/structures/{structure_id}", response_model=StructureRead, summary="Detalhes da estrutura"
)
def get_structure(structure_id: str) -> Any:
    pending_endpoint("B04")


@inventory_router.patch(
    "/structures/{structure_id}", response_model=StructureRead, summary="Atualizar estrutura"
)
def update_structure(
    structure_id: str,
    payload: StructureUpdate,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> Any:
    pending_endpoint("B04")


@inventory_router.delete(
    "/structures/{structure_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar estrutura",
)
def delete_structure(
    structure_id: str,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> None:
    pending_endpoint("B04")


@inventory_router.get(
    "/structures/{structure_id}/occupancy",
    response_model=StructureOccupancyResponse,
    summary="Ocupação de portas da estrutura / CTO",
)
def get_structure_occupancy(structure_id: str) -> Any:
    pending_endpoint("B08")


@inventory_router.get(
    "/structures/{structure_id}/connectivity", summary="Conectividade interna da caixa CEO"
)
def get_structure_connectivity(structure_id: str) -> Any:
    pending_endpoint("B07")


# ==============================================================================
# DEVICES (OLT, DIO, ONU, Switch)
# ==============================================================================
@inventory_router.get(
    "/devices", response_model=PaginatedResponse[DeviceRead], summary="Listar dispositivos"
)
def list_devices(
    pagination: PaginationParams = Depends(),
    kind: DeviceKind | None = Query(default=None),
    q: str | None = Query(default=None, description="Busca por código, serial ou fabricante"),
) -> Any:
    pending_endpoint("B04")


@inventory_router.post(
    "/devices",
    response_model=DeviceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar dispositivo",
)
def create_device(payload: DeviceCreate) -> Any:
    pending_endpoint("B04")


@inventory_router.get(
    "/devices/{device_id}", response_model=DeviceRead, summary="Detalhes do dispositivo"
)
def get_device(device_id: str) -> Any:
    pending_endpoint("B04")


@inventory_router.patch(
    "/devices/{device_id}", response_model=DeviceRead, summary="Atualizar dispositivo"
)
def update_device(
    device_id: str,
    payload: DeviceUpdate,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> Any:
    pending_endpoint("B04")


@inventory_router.delete(
    "/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Desativar dispositivo"
)
def delete_device(
    device_id: str,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> None:
    pending_endpoint("B04")


# ==============================================================================
# PORTS (Portas de dispositivos ou estruturas)
# ==============================================================================
@inventory_router.get("/ports", response_model=PaginatedResponse[PortRead], summary="Listar portas")
def list_ports(
    pagination: PaginationParams = Depends(),
    device_id: str | None = Query(default=None),
    structure_id: str | None = Query(default=None),
) -> Any:
    pending_endpoint("B04")


@inventory_router.post(
    "/ports", response_model=PortRead, status_code=status.HTTP_201_CREATED, summary="Criar porta"
)
def create_port(payload: PortCreate) -> Any:
    pending_endpoint("B04")


@inventory_router.get("/ports/{port_id}", response_model=PortRead, summary="Detalhes da porta")
def get_port(port_id: str) -> Any:
    pending_endpoint("B04")


@inventory_router.patch("/ports/{port_id}", response_model=PortRead, summary="Atualizar porta")
def update_port(
    port_id: str,
    payload: PortUpdate,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> Any:
    pending_endpoint("B04")


@inventory_router.delete(
    "/ports/{port_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Desativar porta"
)
def delete_port(
    port_id: str,
    if_match: str = Header(..., description="Versão atual do recurso (If-Match)"),
) -> None:
    pending_endpoint("B04")
