import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.concurrency import check_if_match
from app.core.errors import (
    ConflictError,
    NotFoundError,
    UnprocessableEntityError,
)
from app.core.search import contains
from app.modules.connectivity.models import Connection, Splitter, Terminal, TerminalReservation
from app.modules.customers.models import ServiceLink
from app.modules.gis.helpers import point_geometry_to_wkb, wkb_to_point_geometry
from app.modules.inventory.models import Device, Port, Site, Structure
from app.schemas.common import AdministrativeStatus, PhysicalCondition
from app.schemas.inventory import (
    DeviceCreate,
    DeviceKind,
    DeviceRead,
    DeviceUpdate,
    PortCreate,
    PortRead,
    PortRole,
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

# ==============================================================================
# SITES (POPs / Locais Técnicos)
# ==============================================================================


def site_to_site_read(site: Site) -> SiteRead:
    return SiteRead(
        id=str(site.id),
        code=site.code,
        name=site.name,
        kind=SiteKind(site.kind),
        location=wkb_to_point_geometry(site.location),
        status=AdministrativeStatus(site.status),
        address=site.address,
        notes=site.notes,
        version=site.version,
        created_at=site.created_at,
        updated_at=site.updated_at,
    )


def list_sites_paginated(
    session: Session,
    page: int = 1,
    page_size: int = 50,
    kind: SiteKind | None = None,
    q: str | None = None,
) -> tuple[list[Site], int]:
    query = select(Site)
    count_query = select(func.count(Site.id))

    if kind:
        query = query.where(Site.kind == kind.value)
        count_query = count_query.where(Site.kind == kind.value)

    if q and q.strip():
        filter_clause = contains(Site.code, q) | contains(Site.name, q)
        query = query.where(filter_clause)
        count_query = count_query.where(filter_clause)

    total = session.scalar(count_query) or 0
    offset = (page - 1) * page_size
    items = list(
        session.scalars(
            query.order_by(Site.created_at.desc(), Site.id).offset(offset).limit(page_size)
        ).all()
    )
    return items, total


def get_site_by_id(session: Session, site_id: str) -> Site:
    try:
        site_uuid = uuid.UUID(site_id)
    except ValueError:
        raise NotFoundError("Site não encontrado.", code="site_not_found") from None

    site = session.scalar(select(Site).where(Site.id == site_uuid))
    if not site:
        raise NotFoundError("Site não encontrado.", code="site_not_found")
    return site


def create_site(session: Session, payload: SiteCreate) -> Site:
    clean_code = payload.code.strip().upper()
    existing = session.scalar(select(Site).where(Site.code == clean_code))
    if existing:
        raise ConflictError(
            f"Já existe um site com o código '{clean_code}'.",
            code="code_already_exists",
        )

    wkb_location = point_geometry_to_wkb(payload.location)
    site = Site(
        code=clean_code,
        name=payload.name.strip(),
        kind=payload.kind.value,
        location=wkb_location,
        status=payload.status.value,
        address=payload.address.strip() if payload.address else None,
        notes=payload.notes,
        version=1,
    )
    session.add(site)
    session.commit()
    session.refresh(site)
    return site


def update_site(
    session: Session,
    site_id: str,
    payload: SiteUpdate,
    if_match: str | None,
) -> Site:
    site = get_site_by_id(session, site_id)
    check_if_match(if_match, site.version)

    if payload.name is not None:
        site.name = payload.name.strip()
    if payload.kind is not None:
        site.kind = payload.kind.value
    if payload.location is not None:
        site.location = point_geometry_to_wkb(payload.location)
    if payload.status is not None:
        site.status = payload.status.value
    if payload.address is not None:
        site.address = payload.address.strip() if payload.address else None
    if payload.notes is not None:
        site.notes = payload.notes

    site.version += 1
    site.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(site)
    return site


def delete_site(session: Session, site_id: str, if_match: str | None) -> None:
    site = get_site_by_id(session, site_id)
    check_if_match(if_match, site.version)

    # Verifica integridade referencial antes de excluir
    has_structures = (
        session.scalar(select(func.count(Structure.id)).where(Structure.site_id == site.id)) or 0
    )
    has_devices = (
        session.scalar(select(func.count(Device.id)).where(Device.site_id == site.id)) or 0
    )
    if has_structures > 0 or has_devices > 0:
        raise ConflictError(
            "Não é possível excluir o site pois existem estruturas ou dispositivos vinculados a ele.",
            code="referenced_entity_conflict",
        )

    try:
        session.delete(site)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ConflictError(
            "Não é possível excluir o site pois ele é referenciado por outros elementos da rede.",
            code="referenced_entity_conflict",
        ) from None


# ==============================================================================
# STRUCTURES (Postes, CEOs, CTOs, Caixas)
# ==============================================================================


def structure_to_structure_read(structure: Structure) -> StructureRead:
    return StructureRead(
        id=str(structure.id),
        code=structure.code,
        kind=StructureKind(structure.kind),
        location=wkb_to_point_geometry(structure.location),
        site_id=str(structure.site_id) if structure.site_id else None,
        capacity=structure.capacity,
        status=AdministrativeStatus(structure.status),
        condition=PhysicalCondition(structure.condition),
        notes=structure.notes,
        version=structure.version,
        created_at=structure.created_at,
        updated_at=structure.updated_at,
    )


def list_structures_paginated(
    session: Session,
    page: int = 1,
    page_size: int = 50,
    kind: StructureKind | None = None,
    q: str | None = None,
) -> tuple[list[Structure], int]:
    query = select(Structure)
    count_query = select(func.count(Structure.id))

    if kind:
        query = query.where(Structure.kind == kind.value)
        count_query = count_query.where(Structure.kind == kind.value)

    if q and q.strip():
        code_clause = contains(Structure.code, q)
        query = query.where(code_clause)
        count_query = count_query.where(code_clause)

    total = session.scalar(count_query) or 0
    offset = (page - 1) * page_size
    items = list(
        session.scalars(
            query.order_by(Structure.created_at.desc(), Structure.id)
            .offset(offset)
            .limit(page_size)
        ).all()
    )
    return items, total


def get_structure_by_id(session: Session, structure_id: str) -> Structure:
    try:
        structure_uuid = uuid.UUID(structure_id)
    except ValueError:
        raise NotFoundError("Estrutura não encontrada.", code="structure_not_found") from None

    structure = session.scalar(select(Structure).where(Structure.id == structure_uuid))
    if not structure:
        raise NotFoundError("Estrutura não encontrada.", code="structure_not_found")
    return structure


def get_structure_occupancy(session: Session, structure_id: str) -> StructureOccupancyResponse:
    """Resume a ocupação das portas diretas e dos dispositivos alojados na estrutura."""
    structure = get_structure_by_id(session, structure_id)
    device_ids = select(Device.id).where(Device.structure_id == structure.id)
    ports = list(
        session.scalars(
            select(Port)
            .where(
                or_(
                    Port.structure_id == structure.id,
                    Port.device_id.in_(device_ids),
                )
            )
            .order_by(Port.name, Port.id)
        ).all()
    )
    port_ids = [port.id for port in ports]
    terminals = (
        list(
            session.scalars(
                select(Terminal).where(
                    Terminal.entity_type == "port", Terminal.entity_id.in_(port_ids)
                )
            ).all()
        )
        if port_ids
        else []
    )
    terminal_ids = [terminal.id for terminal in terminals]
    terminals_by_port = {
        terminal.entity_id: terminal for terminal in terminals if terminal.entity_id is not None
    }

    connected_terminal_ids: set[uuid.UUID] = set()
    reserved_terminal_ids: set[uuid.UUID] = set()
    active_service_port_ids = (
        set(
            session.scalars(
                select(ServiceLink.port_id).where(
                    ServiceLink.port_id.in_(port_ids), ServiceLink.status == "active"
                )
            ).all()
        )
        if port_ids
        else set()
    )
    if terminal_ids:
        for connection in session.scalars(
            select(Connection).where(
                Connection.is_active.is_(True),
                or_(
                    Connection.terminal_a_id.in_(terminal_ids),
                    Connection.terminal_b_id.in_(terminal_ids),
                ),
            )
        ):
            if connection.terminal_a_id in terminal_ids:
                connected_terminal_ids.add(connection.terminal_a_id)
            if connection.terminal_b_id in terminal_ids:
                connected_terminal_ids.add(connection.terminal_b_id)
        reserved_terminal_ids = set(
            session.scalars(
                select(TerminalReservation.terminal_id).where(
                    TerminalReservation.terminal_id.in_(terminal_ids),
                    TerminalReservation.is_active.is_(True),
                )
            ).all()
        )

    connected = reserved = free = damaged = 0
    for port in ports:
        terminal = terminals_by_port.get(port.id)
        notes = (port.notes or "").lower()
        is_damaged = any(
            marker in notes for marker in ("danificad", "defeito", "damaged", "quebrad", "broken")
        )
        if is_damaged:
            damaged += 1

        is_connected = port.id in active_service_port_ids or (
            terminal is not None
            and (
                terminal.id in connected_terminal_ids
                or terminal.is_occupied
                or terminal.occupancy in ("connected", "customer_connected")
            )
        )
        is_reserved = terminal is not None and (
            terminal.id in reserved_terminal_ids or terminal.occupancy == "reserved"
        )
        if is_connected:
            connected += 1
        elif is_reserved:
            reserved += 1
        elif not is_damaged:
            free += 1

    return StructureOccupancyResponse(
        structure_id=str(structure.id),
        code=structure.code,
        kind=StructureKind(structure.kind),
        total_ports=len(ports),
        connected_ports=connected,
        reserved_ports=reserved,
        free_ports=free,
        damaged_ports=damaged,
    )


def create_structure(session: Session, payload: StructureCreate) -> Structure:
    clean_code = payload.code.strip().upper()
    existing = session.scalar(select(Structure).where(Structure.code == clean_code))
    if existing:
        raise ConflictError(
            f"Já existe uma estrutura com o código '{clean_code}'.",
            code="code_already_exists",
        )

    site_uuid: uuid.UUID | None = None
    if payload.site_id:
        try:
            site_uuid = uuid.UUID(payload.site_id)
        except ValueError:
            raise NotFoundError("Site informado não encontrado.", code="site_not_found") from None
        if not session.scalar(select(Site.id).where(Site.id == site_uuid)):
            raise NotFoundError("Site informado não encontrado.", code="site_not_found")

    wkb_location = point_geometry_to_wkb(payload.location)
    structure = Structure(
        code=clean_code,
        kind=payload.kind.value,
        location=wkb_location,
        site_id=site_uuid,
        capacity=payload.capacity,
        status=payload.status.value,
        condition=payload.condition.value,
        notes=payload.notes,
        version=1,
    )
    session.add(structure)
    session.commit()
    session.refresh(structure)
    return structure


def update_structure(
    session: Session,
    structure_id: str,
    payload: StructureUpdate,
    if_match: str | None,
) -> Structure:
    structure = get_structure_by_id(session, structure_id)
    check_if_match(if_match, structure.version)

    if payload.location is not None:
        structure.location = point_geometry_to_wkb(payload.location)
    if payload.site_id is not None:
        try:
            site_uuid = uuid.UUID(payload.site_id)
        except ValueError:
            raise NotFoundError("Site informado não encontrado.", code="site_not_found") from None
        if not session.scalar(select(Site.id).where(Site.id == site_uuid)):
            raise NotFoundError("Site informado não encontrado.", code="site_not_found")
        structure.site_id = site_uuid
    if payload.capacity is not None:
        structure.capacity = payload.capacity
    if payload.status is not None:
        structure.status = payload.status.value
    if payload.condition is not None:
        structure.condition = payload.condition.value
    if payload.notes is not None:
        structure.notes = payload.notes

    structure.version += 1
    structure.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(structure)
    return structure


def delete_structure(session: Session, structure_id: str, if_match: str | None) -> None:
    structure = get_structure_by_id(session, structure_id)
    check_if_match(if_match, structure.version)

    has_devices = (
        session.scalar(select(func.count(Device.id)).where(Device.structure_id == structure.id))
        or 0
    )
    has_ports = (
        session.scalar(select(func.count(Port.id)).where(Port.structure_id == structure.id)) or 0
    )
    if has_devices > 0 or has_ports > 0:
        raise ConflictError(
            "Não é possível excluir a estrutura pois há dispositivos ou portas vinculados a ela.",
            code="referenced_entity_conflict",
        )

    try:
        session.delete(structure)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ConflictError(
            "Não é possível excluir a estrutura pois ela é referenciada por outros elementos da rede.",
            code="referenced_entity_conflict",
        ) from None


# ==============================================================================
# DEVICES (OLT, DIO, ONU, Switch)
# ==============================================================================


def device_to_device_read(device: Device) -> DeviceRead:
    return DeviceRead(
        id=str(device.id),
        code=device.code,
        kind=DeviceKind(device.kind),
        manufacturer=device.manufacturer,
        model=device.model,
        serial_number=device.serial_number,
        site_id=str(device.site_id) if device.site_id else None,
        structure_id=str(device.structure_id) if device.structure_id else None,
        status=AdministrativeStatus(device.status),
        condition=PhysicalCondition(device.condition),
        notes=device.notes,
        version=device.version,
        created_at=device.created_at,
        updated_at=device.updated_at,
    )


def list_devices_paginated(
    session: Session,
    page: int = 1,
    page_size: int = 50,
    kind: DeviceKind | None = None,
    q: str | None = None,
) -> tuple[list[Device], int]:
    query = select(Device)
    count_query = select(func.count(Device.id))

    if kind:
        query = query.where(Device.kind == kind.value)
        count_query = count_query.where(Device.kind == kind.value)

    if q and q.strip():
        filter_clause = (
            contains(Device.code, q)
            | contains(Device.manufacturer, q)
            | contains(Device.model, q)
            | contains(Device.serial_number, q)
        )
        query = query.where(filter_clause)
        count_query = count_query.where(filter_clause)

    total = session.scalar(count_query) or 0
    offset = (page - 1) * page_size
    items = list(
        session.scalars(
            query.order_by(Device.created_at.desc(), Device.id).offset(offset).limit(page_size)
        ).all()
    )
    return items, total


def get_device_by_id(session: Session, device_id: str) -> Device:
    try:
        device_uuid = uuid.UUID(device_id)
    except ValueError:
        raise NotFoundError("Dispositivo não encontrado.", code="device_not_found") from None

    device = session.scalar(select(Device).where(Device.id == device_uuid))
    if not device:
        raise NotFoundError("Dispositivo não encontrado.", code="device_not_found")
    return device


def create_device(session: Session, payload: DeviceCreate) -> Device:
    # Validação de exclusividade de localização (Site XOR Structure)
    if (payload.site_id and payload.structure_id) or (
        not payload.site_id and not payload.structure_id
    ):
        raise UnprocessableEntityError(
            "O dispositivo deve estar alocado exclusivamente em um site OU em uma estrutura.",
            field="location",
        )

    clean_code = payload.code.strip().upper()
    existing = session.scalar(select(Device).where(Device.code == clean_code))
    if existing:
        raise ConflictError(
            f"Já existe um dispositivo com o código '{clean_code}'.",
            code="code_already_exists",
        )

    site_uuid: uuid.UUID | None = None
    structure_uuid: uuid.UUID | None = None

    if payload.site_id:
        try:
            site_uuid = uuid.UUID(payload.site_id)
        except ValueError:
            raise NotFoundError("Site informado não encontrado.", code="site_not_found") from None
        if not session.scalar(select(Site.id).where(Site.id == site_uuid)):
            raise NotFoundError("Site informado não encontrado.", code="site_not_found")

    if payload.structure_id:
        try:
            structure_uuid = uuid.UUID(payload.structure_id)
        except ValueError:
            raise NotFoundError(
                "Estrutura informada não encontrada.", code="structure_not_found"
            ) from None
        if not session.scalar(select(Structure.id).where(Structure.id == structure_uuid)):
            raise NotFoundError("Estrutura informada não encontrada.", code="structure_not_found")

    device = Device(
        code=clean_code,
        kind=payload.kind.value,
        manufacturer=payload.manufacturer.strip(),
        model=payload.model.strip(),
        serial_number=payload.serial_number.strip() if payload.serial_number else None,
        site_id=site_uuid,
        structure_id=structure_uuid,
        status=payload.status.value,
        condition=payload.condition.value,
        notes=payload.notes,
        version=1,
    )
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


def update_device(
    session: Session,
    device_id: str,
    payload: DeviceUpdate,
    if_match: str | None,
) -> Device:
    device = get_device_by_id(session, device_id)
    check_if_match(if_match, device.version)

    if payload.manufacturer is not None:
        device.manufacturer = payload.manufacturer.strip()
    if payload.model is not None:
        device.model = payload.model.strip()
    if payload.serial_number is not None:
        device.serial_number = payload.serial_number.strip() if payload.serial_number else None

    # Se alterar localidade, valida a exclusividade
    new_site_id = (
        payload.site_id
        if payload.site_id is not None
        else (str(device.site_id) if device.site_id else None)
    )
    new_struct_id = (
        payload.structure_id
        if payload.structure_id is not None
        else (str(device.structure_id) if device.structure_id else None)
    )

    if payload.site_id is not None or payload.structure_id is not None:
        location_changed = (new_site_id or None) != (
            str(device.site_id) if device.site_id else None
        ) or (new_struct_id or None) != (str(device.structure_id) if device.structure_id else None)
        has_splitters = (
            session.scalar(select(func.count(Splitter.id)).where(Splitter.device_id == device.id))
            or 0
        )
        if location_changed and has_splitters:
            raise ConflictError(
                "Desvincule ou remova os splitters alojados antes de mover o dispositivo.",
                code="device_has_splitters",
            )
        if (new_site_id and new_struct_id) or (not new_site_id and not new_struct_id):
            raise UnprocessableEntityError(
                "O dispositivo deve estar alocado exclusivamente em um site OU em uma estrutura.",
                field="location",
            )
        if payload.site_id is not None:
            if payload.site_id:
                try:
                    s_uuid = uuid.UUID(payload.site_id)
                except ValueError:
                    raise NotFoundError(
                        "Site informado não encontrado.", code="site_not_found"
                    ) from None
                if not session.scalar(select(Site.id).where(Site.id == s_uuid)):
                    raise NotFoundError("Site informado não encontrado.", code="site_not_found")
                device.site_id = s_uuid
                device.structure_id = None
            else:
                device.site_id = None

        if payload.structure_id is not None:
            if payload.structure_id:
                try:
                    st_uuid = uuid.UUID(payload.structure_id)
                except ValueError:
                    raise NotFoundError(
                        "Estrutura informada não encontrada.", code="structure_not_found"
                    ) from None
                if not session.scalar(select(Structure.id).where(Structure.id == st_uuid)):
                    raise NotFoundError(
                        "Estrutura informada não encontrada.", code="structure_not_found"
                    )
                device.structure_id = st_uuid
                device.site_id = None
            else:
                device.structure_id = None

    if payload.status is not None:
        device.status = payload.status.value
    if payload.condition is not None:
        device.condition = payload.condition.value
    if payload.notes is not None:
        device.notes = payload.notes

    device.version += 1
    device.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(device)
    return device


def delete_device(session: Session, device_id: str, if_match: str | None) -> None:
    device = get_device_by_id(session, device_id)
    check_if_match(if_match, device.version)

    has_ports = session.scalar(select(func.count(Port.id)).where(Port.device_id == device.id)) or 0
    if has_ports > 0:
        raise ConflictError(
            "Não é possível excluir o dispositivo pois ele possui portas cadastradas.",
            code="referenced_entity_conflict",
        )

    try:
        session.delete(device)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ConflictError(
            "Não é possível excluir o dispositivo pois ele é referenciado por outros elementos da rede.",
            code="referenced_entity_conflict",
        ) from None


# ==============================================================================
# PORTS (Portas de Dispositivos ou Estruturas)
# ==============================================================================


def port_to_port_read(port: Port) -> PortRead:
    return PortRead(
        id=str(port.id),
        name=port.name,
        role=PortRole(port.role),
        device_id=str(port.device_id) if port.device_id else None,
        structure_id=str(port.structure_id) if port.structure_id else None,
        has_internal_pass_through=port.has_internal_pass_through,
        connector_type=port.connector_type,
        notes=port.notes,
        version=port.version,
        created_at=port.created_at,
        updated_at=port.updated_at,
    )


def list_ports_paginated(
    session: Session,
    page: int = 1,
    page_size: int = 50,
    device_id: str | None = None,
    structure_id: str | None = None,
) -> tuple[list[Port], int]:
    query = select(Port)
    count_query = select(func.count(Port.id))

    if device_id:
        try:
            d_uuid = uuid.UUID(device_id)
            query = query.where(Port.device_id == d_uuid)
            count_query = count_query.where(Port.device_id == d_uuid)
        except ValueError:
            return [], 0

    if structure_id:
        try:
            s_uuid = uuid.UUID(structure_id)
            query = query.where(Port.structure_id == s_uuid)
            count_query = count_query.where(Port.structure_id == s_uuid)
        except ValueError:
            return [], 0

    total = session.scalar(count_query) or 0
    offset = (page - 1) * page_size
    items = list(
        session.scalars(
            query.order_by(Port.created_at.desc(), Port.id).offset(offset).limit(page_size)
        ).all()
    )
    return items, total


def get_port_by_id(session: Session, port_id: str) -> Port:
    try:
        port_uuid = uuid.UUID(port_id)
    except ValueError:
        raise NotFoundError("Porta não encontrada.", code="port_not_found") from None

    port = session.scalar(select(Port).where(Port.id == port_uuid))
    if not port:
        raise NotFoundError("Porta não encontrada.", code="port_not_found")
    return port


def create_port(session: Session, payload: PortCreate) -> Port:
    # Validação de proprietário exclusivo (Device XOR Structure)
    if (payload.device_id and payload.structure_id) or (
        not payload.device_id and not payload.structure_id
    ):
        raise UnprocessableEntityError(
            "A porta deve pertencer exclusivamente a um dispositivo OU a uma estrutura.",
            field="owner",
        )

    clean_name = payload.name.strip()
    device_uuid: uuid.UUID | None = None
    structure_uuid: uuid.UUID | None = None

    if payload.device_id:
        try:
            device_uuid = uuid.UUID(payload.device_id)
        except ValueError:
            raise NotFoundError(
                "Dispositivo informado não encontrado.", code="device_not_found"
            ) from None
        if not session.scalar(select(Device.id).where(Device.id == device_uuid)):
            raise NotFoundError("Dispositivo informado não encontrado.", code="device_not_found")

        # Unicidade do nome da porta no dispositivo
        existing = session.scalar(
            select(Port).where(Port.device_id == device_uuid, Port.name == clean_name)
        )
        if existing:
            raise ConflictError(
                f"Já existe uma porta com o nome '{clean_name}' neste dispositivo.",
                code="port_name_already_exists",
            )

    if payload.structure_id:
        try:
            structure_uuid = uuid.UUID(payload.structure_id)
        except ValueError:
            raise NotFoundError(
                "Estrutura informada não encontrada.", code="structure_not_found"
            ) from None
        if not session.scalar(select(Structure.id).where(Structure.id == structure_uuid)):
            raise NotFoundError("Estrutura informada não encontrada.", code="structure_not_found")

        # Unicidade do nome da porta na estrutura
        existing = session.scalar(
            select(Port).where(Port.structure_id == structure_uuid, Port.name == clean_name)
        )
        if existing:
            raise ConflictError(
                f"Já existe uma porta com o nome '{clean_name}' nesta estrutura.",
                code="port_name_already_exists",
            )

    port = Port(
        name=clean_name,
        role=payload.role.value,
        device_id=device_uuid,
        structure_id=structure_uuid,
        has_internal_pass_through=payload.has_internal_pass_through,
        connector_type=payload.connector_type.strip(),
        notes=payload.notes,
        version=1,
    )
    session.add(port)
    session.commit()
    session.refresh(port)
    return port


def update_port(
    session: Session,
    port_id: str,
    payload: PortUpdate,
    if_match: str | None,
) -> Port:
    port = get_port_by_id(session, port_id)
    check_if_match(if_match, port.version)

    if payload.name is not None:
        clean_name = payload.name.strip()
        if clean_name != port.name:
            if port.device_id:
                existing = session.scalar(
                    select(Port).where(
                        Port.device_id == port.device_id,
                        Port.name == clean_name,
                        Port.id != port.id,
                    )
                )
                if existing:
                    raise ConflictError(
                        f"Já existe uma porta com o nome '{clean_name}' neste dispositivo.",
                        code="port_name_already_exists",
                    )
            elif port.structure_id:
                existing = session.scalar(
                    select(Port).where(
                        Port.structure_id == port.structure_id,
                        Port.name == clean_name,
                        Port.id != port.id,
                    )
                )
                if existing:
                    raise ConflictError(
                        f"Já existe uma porta com o nome '{clean_name}' nesta estrutura.",
                        code="port_name_already_exists",
                    )
            port.name = clean_name

    if payload.role is not None:
        port.role = payload.role.value
    if payload.connector_type is not None:
        port.connector_type = payload.connector_type.strip()
    if payload.notes is not None:
        port.notes = payload.notes

    port.version += 1
    port.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(port)
    return port


def delete_port(session: Session, port_id: str, if_match: str | None) -> None:
    port = get_port_by_id(session, port_id)
    check_if_match(if_match, port.version)

    try:
        session.delete(port)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ConflictError(
            "Não é possível excluir a porta pois ela possui conexões ou terminais ópticos ativos.",
            code="referenced_entity_conflict",
        ) from None
