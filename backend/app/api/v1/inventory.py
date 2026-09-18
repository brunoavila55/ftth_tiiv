import uuid

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from app.core.contracts import pending_endpoint
from app.core.dependencies import require_permission, validate_csrf
from app.db.session import get_db
from app.modules.connectivity.service import (
    get_structure_connectivity as fetch_structure_connectivity,
)
from app.modules.inventory.service import (
    create_device,
    create_port,
    create_site,
    create_structure,
    delete_device,
    delete_port,
    delete_site,
    delete_structure,
    device_to_device_read,
    get_device_by_id,
    get_port_by_id,
    get_site_by_id,
    get_structure_by_id,
    list_devices_paginated,
    list_ports_paginated,
    list_sites_paginated,
    list_structures_paginated,
    port_to_port_read,
    site_to_site_read,
    structure_to_structure_read,
    update_device,
    update_port,
    update_site,
    update_structure,
)
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.connectivity import StructureConnectivityResponse
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
    "/sites",
    response_model=PaginatedResponse[SiteRead],
    summary="Listar sites / POPs",
    dependencies=[Depends(require_permission("network:read"))],
)
def list_sites(
    pagination: PaginationParams = Depends(),
    kind: SiteKind | None = Query(default=None),
    q: str | None = Query(default=None, description="Busca por código ou nome"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SiteRead]:
    items, total = list_sites_paginated(
        session=db,
        page=pagination.page,
        page_size=pagination.page_size,
        kind=kind,
        q=q,
    )
    return PaginatedResponse[SiteRead](
        items=[site_to_site_read(s) for s in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@inventory_router.post(
    "/sites",
    response_model=SiteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar site",
    dependencies=[Depends(require_permission("network:write")), Depends(validate_csrf)],
)
def create_site_endpoint(
    payload: SiteCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> SiteRead:
    site = create_site(session=db, payload=payload)
    response.headers["ETag"] = f'"{site.version}"'
    return site_to_site_read(site)


@inventory_router.get(
    "/sites/{site_id}",
    response_model=SiteRead,
    summary="Detalhes do site",
    dependencies=[Depends(require_permission("network:read"))],
)
def get_site_endpoint(
    site_id: str,
    response: Response,
    db: Session = Depends(get_db),
) -> SiteRead:
    site = get_site_by_id(session=db, site_id=site_id)
    response.headers["ETag"] = f'"{site.version}"'
    return site_to_site_read(site)


@inventory_router.patch(
    "/sites/{site_id}",
    response_model=SiteRead,
    summary="Atualizar site",
    dependencies=[Depends(require_permission("network:write")), Depends(validate_csrf)],
)
def update_site_endpoint(
    site_id: str,
    payload: SiteUpdate,
    response: Response,
    if_match: str | None = Header(
        default=None, description="Versão atual do recurso para concorrência otimista"
    ),
    db: Session = Depends(get_db),
) -> SiteRead:
    site = update_site(session=db, site_id=site_id, payload=payload, if_match=if_match)
    response.headers["ETag"] = f'"{site.version}"'
    return site_to_site_read(site)


@inventory_router.delete(
    "/sites/{site_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar site",
    dependencies=[Depends(require_permission("network:write")), Depends(validate_csrf)],
)
def delete_site_endpoint(
    site_id: str,
    if_match: str | None = Header(
        default=None, description="Versão atual do recurso para concorrência otimista"
    ),
    db: Session = Depends(get_db),
) -> None:
    delete_site(session=db, site_id=site_id, if_match=if_match)


# ==============================================================================
# STRUCTURES (Postes, CEOs, CTOs, Caixas)
# ==============================================================================
@inventory_router.get(
    "/structures",
    response_model=PaginatedResponse[StructureRead],
    summary="Listar estruturas",
    dependencies=[Depends(require_permission("network:read"))],
)
def list_structures(
    pagination: PaginationParams = Depends(),
    kind: StructureKind | None = Query(
        default=None, description="Filtrar por tipo (ex: cto, ceo, pole)"
    ),
    q: str | None = Query(default=None, description="Busca por código"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[StructureRead]:
    items, total = list_structures_paginated(
        session=db,
        page=pagination.page,
        page_size=pagination.page_size,
        kind=kind,
        q=q,
    )
    return PaginatedResponse[StructureRead](
        items=[structure_to_structure_read(s) for s in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@inventory_router.post(
    "/structures",
    response_model=StructureRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar estrutura",
    dependencies=[Depends(require_permission("network:write")), Depends(validate_csrf)],
)
def create_structure_endpoint(
    payload: StructureCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> StructureRead:
    structure = create_structure(session=db, payload=payload)
    response.headers["ETag"] = f'"{structure.version}"'
    return structure_to_structure_read(structure)


@inventory_router.get(
    "/structures/{structure_id}",
    response_model=StructureRead,
    summary="Detalhes da estrutura",
    dependencies=[Depends(require_permission("network:read"))],
)
def get_structure_endpoint(
    structure_id: str,
    response: Response,
    db: Session = Depends(get_db),
) -> StructureRead:
    structure = get_structure_by_id(session=db, structure_id=structure_id)
    response.headers["ETag"] = f'"{structure.version}"'
    return structure_to_structure_read(structure)


@inventory_router.patch(
    "/structures/{structure_id}",
    response_model=StructureRead,
    summary="Atualizar estrutura",
    dependencies=[Depends(require_permission("network:write")), Depends(validate_csrf)],
)
def update_structure_endpoint(
    structure_id: str,
    payload: StructureUpdate,
    response: Response,
    if_match: str | None = Header(
        default=None, description="Versão atual do recurso para concorrência otimista"
    ),
    db: Session = Depends(get_db),
) -> StructureRead:
    structure = update_structure(
        session=db, structure_id=structure_id, payload=payload, if_match=if_match
    )
    response.headers["ETag"] = f'"{structure.version}"'
    return structure_to_structure_read(structure)


@inventory_router.delete(
    "/structures/{structure_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar estrutura",
    dependencies=[Depends(require_permission("network:write")), Depends(validate_csrf)],
)
def delete_structure_endpoint(
    structure_id: str,
    if_match: str | None = Header(
        default=None, description="Versão atual do recurso para concorrência otimista"
    ),
    db: Session = Depends(get_db),
) -> None:
    delete_structure(session=db, structure_id=structure_id, if_match=if_match)


@inventory_router.get(
    "/structures/{structure_id}/occupancy",
    response_model=StructureOccupancyResponse,
    summary="Ocupação de portas da estrutura / CTO",
    dependencies=[Depends(require_permission("network:read"))],
)
def get_structure_occupancy(structure_id: str) -> StructureOccupancyResponse:
    pending_endpoint("B08")


@inventory_router.get(
    "/structures/{structure_id}/connectivity",
    response_model=StructureConnectivityResponse,
    summary="Conectividade interna da caixa CEO",
    dependencies=[Depends(require_permission("network:read"))],
)
def get_structure_connectivity(
    structure_id: str,
    db: Session = Depends(get_db),
) -> StructureConnectivityResponse:
    return fetch_structure_connectivity(db, uuid.UUID(structure_id))


# ==============================================================================
# DEVICES (OLT, DIO, ONU, Switch)
# ==============================================================================
@inventory_router.get(
    "/devices",
    response_model=PaginatedResponse[DeviceRead],
    summary="Listar dispositivos",
    dependencies=[Depends(require_permission("network:read"))],
)
def list_devices(
    pagination: PaginationParams = Depends(),
    kind: DeviceKind | None = Query(default=None),
    q: str | None = Query(default=None, description="Busca por código, serial ou fabricante"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[DeviceRead]:
    items, total = list_devices_paginated(
        session=db,
        page=pagination.page,
        page_size=pagination.page_size,
        kind=kind,
        q=q,
    )
    return PaginatedResponse[DeviceRead](
        items=[device_to_device_read(d) for d in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@inventory_router.post(
    "/devices",
    response_model=DeviceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar dispositivo",
    dependencies=[Depends(require_permission("network:write")), Depends(validate_csrf)],
)
def create_device_endpoint(
    payload: DeviceCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> DeviceRead:
    device = create_device(session=db, payload=payload)
    response.headers["ETag"] = f'"{device.version}"'
    return device_to_device_read(device)


@inventory_router.get(
    "/devices/{device_id}",
    response_model=DeviceRead,
    summary="Detalhes do dispositivo",
    dependencies=[Depends(require_permission("network:read"))],
)
def get_device_endpoint(
    device_id: str,
    response: Response,
    db: Session = Depends(get_db),
) -> DeviceRead:
    device = get_device_by_id(session=db, device_id=device_id)
    response.headers["ETag"] = f'"{device.version}"'
    return device_to_device_read(device)


@inventory_router.patch(
    "/devices/{device_id}",
    response_model=DeviceRead,
    summary="Atualizar dispositivo",
    dependencies=[Depends(require_permission("network:write")), Depends(validate_csrf)],
)
def update_device_endpoint(
    device_id: str,
    payload: DeviceUpdate,
    response: Response,
    if_match: str | None = Header(
        default=None, description="Versão atual do recurso para concorrência otimista"
    ),
    db: Session = Depends(get_db),
) -> DeviceRead:
    device = update_device(session=db, device_id=device_id, payload=payload, if_match=if_match)
    response.headers["ETag"] = f'"{device.version}"'
    return device_to_device_read(device)


@inventory_router.delete(
    "/devices/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar dispositivo",
    dependencies=[Depends(require_permission("network:write")), Depends(validate_csrf)],
)
def delete_device_endpoint(
    device_id: str,
    if_match: str | None = Header(
        default=None, description="Versão atual do recurso para concorrência otimista"
    ),
    db: Session = Depends(get_db),
) -> None:
    delete_device(session=db, device_id=device_id, if_match=if_match)


# ==============================================================================
# PORTS (Portas de dispositivos ou estruturas)
# ==============================================================================
@inventory_router.get(
    "/ports",
    response_model=PaginatedResponse[PortRead],
    summary="Listar portas",
    dependencies=[Depends(require_permission("network:read"))],
)
def list_ports(
    pagination: PaginationParams = Depends(),
    device_id: str | None = Query(default=None),
    structure_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> PaginatedResponse[PortRead]:
    items, total = list_ports_paginated(
        session=db,
        page=pagination.page,
        page_size=pagination.page_size,
        device_id=device_id,
        structure_id=structure_id,
    )
    return PaginatedResponse[PortRead](
        items=[port_to_port_read(p) for p in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@inventory_router.post(
    "/ports",
    response_model=PortRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar porta",
    dependencies=[Depends(require_permission("network:write")), Depends(validate_csrf)],
)
def create_port_endpoint(
    payload: PortCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> PortRead:
    port = create_port(session=db, payload=payload)
    response.headers["ETag"] = f'"{port.version}"'
    return port_to_port_read(port)


@inventory_router.get(
    "/ports/{port_id}",
    response_model=PortRead,
    summary="Detalhes da porta",
    dependencies=[Depends(require_permission("network:read"))],
)
def get_port_endpoint(
    port_id: str,
    response: Response,
    db: Session = Depends(get_db),
) -> PortRead:
    port = get_port_by_id(session=db, port_id=port_id)
    response.headers["ETag"] = f'"{port.version}"'
    return port_to_port_read(port)


@inventory_router.patch(
    "/ports/{port_id}",
    response_model=PortRead,
    summary="Atualizar porta",
    dependencies=[Depends(require_permission("network:write")), Depends(validate_csrf)],
)
def update_port_endpoint(
    port_id: str,
    payload: PortUpdate,
    response: Response,
    if_match: str | None = Header(
        default=None, description="Versão atual do recurso para concorrência otimista"
    ),
    db: Session = Depends(get_db),
) -> PortRead:
    port = update_port(session=db, port_id=port_id, payload=payload, if_match=if_match)
    response.headers["ETag"] = f'"{port.version}"'
    return port_to_port_read(port)


@inventory_router.delete(
    "/ports/{port_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar porta",
    dependencies=[Depends(require_permission("network:write")), Depends(validate_csrf)],
)
def delete_port_endpoint(
    port_id: str,
    if_match: str | None = Header(
        default=None, description="Versão atual do recurso para concorrência otimista"
    ),
    db: Session = Depends(get_db),
) -> None:
    delete_port(session=db, port_id=port_id, if_match=if_match)
