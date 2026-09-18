import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    PreconditionRequiredError,
    UnprocessableEntityError,
)
from app.modules.audit.service import record_audit_event
from app.modules.connectivity.models import Connection, Terminal, TerminalReservation
from app.modules.customers.models import Customer, ServiceLink
from app.modules.inventory.models import Device, Port, Structure
from app.schemas.customers import (
    CustomerCreate,
    CustomerRead,
    CustomerUpdate,
    ServiceLinkCreate,
    ServiceLinkRead,
    ServiceLinkStatus,
    ServiceLinkUpdate,
)


def _validate_if_match(if_match: str | None, current_version: int) -> None:
    if not if_match or not if_match.strip():
        raise PreconditionRequiredError()
    try:
        expected = int(if_match.strip('"'))
    except ValueError:
        raise PreconditionFailedError() from None
    if current_version != expected:
        raise PreconditionFailedError()


def customer_to_customer_read(customer: Customer) -> CustomerRead:
    return CustomerRead(
        id=str(customer.id),
        code=customer.code,
        name=customer.name,
        phone=customer.phone,
        email=customer.email,
        address=customer.address,
        notes=customer.notes,
        version=customer.version,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


def service_link_to_service_link_read(link: ServiceLink) -> ServiceLinkRead:
    return ServiceLinkRead(
        id=str(link.id),
        customer_id=str(link.customer_id),
        onu_device_id=str(link.onu_device_id),
        port_id=str(link.port_id),
        status=ServiceLinkStatus(link.status),
        activated_at=link.activated_at,
        deactivated_at=link.deactivated_at,
        notes=link.notes,
        version=link.version,
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


# ==============================================================================
# CUSTOMERS (Clientes / Assinantes)
# ==============================================================================
def list_customers(
    db: Session,
    *,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[CustomerRead], int]:
    stmt = select(Customer)
    if q and q.strip():
        search = f"%{q.strip()}%"
        stmt = stmt.where(Customer.code.ilike(search) | Customer.name.ilike(search))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    stmt = stmt.order_by(Customer.name.asc()).offset((page - 1) * page_size).limit(page_size)
    results = db.scalars(stmt).all()
    return [customer_to_customer_read(c) for c in results], total


def get_customer_by_id(db: Session, customer_id: uuid.UUID) -> CustomerRead:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise NotFoundError(f"Cliente {customer_id} não existe.")
    return customer_to_customer_read(customer)


def create_customer(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    actor_name: str,
    payload: CustomerCreate,
    request_id: str | None = None,
) -> CustomerRead:
    existing = db.scalar(select(Customer).where(Customer.code == payload.code.strip()))
    if existing:
        raise ConflictError(f"O código '{payload.code}' já está cadastrado para outro cliente.")

    customer = Customer(
        code=payload.code.strip(),
        name=payload.name.strip(),
        phone=payload.phone.strip() if payload.phone else None,
        email=payload.email.strip() if payload.email else None,
        address=payload.address.strip() if payload.address else None,
        notes=payload.notes,
        version=1,
    )
    db.add(customer)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Conflito de integridade ao criar cliente.") from exc

    record_audit_event(
        db,
        actor_id=actor_id,
        actor_name=actor_name,
        action="customer:created",
        entity_type="customer",
        entity_id=customer.id,
        changes={"code": customer.code, "name": customer.name},
        request_id=request_id,
    )
    db.commit()
    db.refresh(customer)
    return customer_to_customer_read(customer)


def update_customer(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    actor_name: str,
    customer_id: uuid.UUID,
    payload: CustomerUpdate,
    if_match: str | None,
    request_id: str | None = None,
) -> CustomerRead:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise NotFoundError(f"Cliente {customer_id} não existe.")

    _validate_if_match(if_match, customer.version)

    changes: dict[str, str | None] = {}
    if payload.name is not None:
        customer.name = payload.name.strip()
        changes["name"] = customer.name
    if payload.phone is not None:
        customer.phone = payload.phone.strip() if payload.phone else None
        changes["phone"] = customer.phone
    if payload.email is not None:
        customer.email = payload.email.strip() if payload.email else None
        changes["email"] = customer.email
    if payload.address is not None:
        customer.address = payload.address.strip() if payload.address else None
        changes["address"] = customer.address
    if payload.notes is not None:
        customer.notes = payload.notes
        changes["notes"] = customer.notes

    customer.version += 1
    record_audit_event(
        db,
        actor_id=actor_id,
        actor_name=actor_name,
        action="customer:updated",
        entity_type="customer",
        entity_id=customer.id,
        changes=changes,
        request_id=request_id,
    )
    db.commit()
    db.refresh(customer)
    return customer_to_customer_read(customer)


def delete_customer(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    actor_name: str,
    customer_id: uuid.UUID,
    if_match: str | None,
    request_id: str | None = None,
) -> None:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise NotFoundError(f"Cliente {customer_id} não existe.")

    _validate_if_match(if_match, customer.version)

    # Verifica se há service_links vinculados ao cliente
    active_links = db.scalar(
        select(func.count()).select_from(ServiceLink).where(
            ServiceLink.customer_id == customer_id,
            ServiceLink.status == "active",
        )
    ) or 0
    if active_links > 0:
        raise ConflictError(
            f"Não é possível excluir o cliente '{customer.name}' pois ele possui {active_links} atendimento(s) óptico(s) ativo(s). Desative os atendimentos primeiro."
        )

    record_audit_event(
        db,
        actor_id=actor_id,
        actor_name=actor_name,
        action="customer:deleted",
        entity_type="customer",
        entity_id=customer.id,
        changes={"code": customer.code, "name": customer.name},
        request_id=request_id,
    )
    db.delete(customer)
    db.commit()


# ==============================================================================
# SERVICE LINKS (Atendimento / Provisionamento Óptico)
# ==============================================================================
def list_service_links(
    db: Session,
    *,
    customer_id: uuid.UUID | None = None,
    port_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ServiceLinkRead], int]:
    stmt = select(ServiceLink)
    if customer_id:
        stmt = stmt.where(ServiceLink.customer_id == customer_id)
    if port_id:
        stmt = stmt.where(ServiceLink.port_id == port_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    stmt = stmt.order_by(ServiceLink.activated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    results = db.scalars(stmt).all()
    return [service_link_to_service_link_read(link) for link in results], total


def get_service_link_by_id(db: Session, link_id: uuid.UUID) -> ServiceLinkRead:
    link = db.get(ServiceLink, link_id)
    if not link:
        raise NotFoundError(f"Atendimento {link_id} não existe.")
    return service_link_to_service_link_read(link)


def create_service_link(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    actor_name: str,
    payload: ServiceLinkCreate,
    request_id: str | None = None,
) -> ServiceLinkRead:
    customer_uuid = uuid.UUID(payload.customer_id)
    onu_uuid = uuid.UUID(payload.onu_device_id)
    port_uuid = uuid.UUID(payload.port_id)

    # 1. Valida cliente
    customer = db.get(Customer, customer_uuid)
    if not customer:
        raise NotFoundError(f"Cliente {customer_uuid} não existe.")

    # 2. Valida dispositivo ONU
    onu = db.get(Device, onu_uuid)
    if not onu:
        raise NotFoundError(f"Dispositivo {onu_uuid} não existe.")
    if onu.kind != "onu":
        raise UnprocessableEntityError(
            f"O equipamento selecionado é do tipo '{onu.kind}'. O atendimento de cliente requer um dispositivo do tipo 'onu'."
        )

    # 3. Valida porta
    port = db.get(Port, port_uuid)
    if not port:
        raise NotFoundError(f"Porta {port_uuid} não existe.")

    # 4. Verifica unicidade de atendimento ativo na mesma porta
    active_port_link = db.scalar(
        select(ServiceLink).where(
            ServiceLink.port_id == port_uuid,
            ServiceLink.status == "active",
        )
    )
    if active_port_link:
        raise ConflictError(
            f"A porta '{port.name}' já está associada a um atendimento ativo (ID: {active_port_link.id}). Desative o atendimento anterior antes de vincular novo assinante."
        )

    # 5. Verifica unicidade de atendimento ativo na mesma ONU
    active_onu_link = db.scalar(
        select(ServiceLink).where(
            ServiceLink.onu_device_id == onu_uuid,
            ServiceLink.status == "active",
        )
    )
    if active_onu_link:
        raise ConflictError(
            f"O equipamento ONU '{onu.code}' já está associado a outro atendimento ativo (ID: {active_onu_link.id})."
        )

    now = datetime.now(UTC)
    link = ServiceLink(
        customer_id=customer_uuid,
        onu_device_id=onu_uuid,
        port_id=port_uuid,
        status="active",
        activated_at=now,
        notes=payload.notes,
        version=1,
    )
    db.add(link)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Conflito de unicidade ao provisionar atendimento.") from exc

    record_audit_event(
        db,
        actor_id=actor_id,
        actor_name=actor_name,
        action="service_link:activated",
        entity_type="service_link",
        entity_id=link.id,
        changes={
            "customer_id": str(customer_uuid),
            "onu_device_id": str(onu_uuid),
            "port_id": str(port_uuid),
            "status": "active",
        },
        request_id=request_id,
    )
    db.commit()
    db.refresh(link)
    return service_link_to_service_link_read(link)


def update_service_link(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    actor_name: str,
    link_id: uuid.UUID,
    payload: ServiceLinkUpdate,
    if_match: str | None,
    request_id: str | None = None,
) -> ServiceLinkRead:
    link = db.get(ServiceLink, link_id)
    if not link:
        raise NotFoundError(f"Atendimento {link_id} não existe.")

    _validate_if_match(if_match, link.version)

    changes: dict[str, str | None] = {}
    if payload.status is not None and payload.status.value != link.status:
        link.status = payload.status.value
        changes["status"] = link.status
        if link.status == "deactivated":
            link.deactivated_at = datetime.now(UTC)
            changes["deactivated_at"] = link.deactivated_at.isoformat()
    if payload.notes is not None:
        link.notes = payload.notes
        changes["notes"] = link.notes

    link.version += 1
    record_audit_event(
        db,
        actor_id=actor_id,
        actor_name=actor_name,
        action="service_link:updated",
        entity_type="service_link",
        entity_id=link.id,
        changes=changes,
        request_id=request_id,
    )
    db.commit()
    db.refresh(link)
    return service_link_to_service_link_read(link)


def deactivate_service_link(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    actor_name: str,
    link_id: uuid.UUID,
    if_match: str | None,
    request_id: str | None = None,
) -> None:
    link = db.get(ServiceLink, link_id)
    if not link:
        raise NotFoundError(f"Atendimento {link_id} não existe.")

    _validate_if_match(if_match, link.version)

    now = datetime.now(UTC)
    link.status = "deactivated"
    link.deactivated_at = now
    link.version += 1

    record_audit_event(
        db,
        actor_id=actor_id,
        actor_name=actor_name,
        action="service_link:deactivated",
        entity_type="service_link",
        entity_id=link.id,
        changes={"status": "deactivated", "deactivated_at": now.isoformat()},
        request_id=request_id,
    )
    db.commit()


# ==============================================================================
# OCUPAÇÃO REAL DE CTO
# ==============================================================================
def get_cto_port_occupancy(
    db: Session,
    structure_id: uuid.UUID,
) -> dict[str, Any]:
    """Calcula a ocupação exata das portas da CTO considerando conexões, reservas e atendimentos."""
    structure = db.get(Structure, structure_id)
    if not structure:
        raise NotFoundError(f"Estrutura {structure_id} não existe.")

    # Busca portas pertencentes a esta estrutura ordenadas por nome
    ports = db.scalars(
        select(Port).where(Port.structure_id == structure_id).order_by(Port.name.asc())
    ).all()
    total_ports = len(ports)

    # Busca atendimentos ativos nessas portas
    port_ids = [p.id for p in ports]
    active_service_links: dict[uuid.UUID, ServiceLink] = {}
    customers_map: dict[uuid.UUID, Customer] = {}
    onus_map: dict[uuid.UUID, Device] = {}

    if port_ids:
        active_links = db.scalars(
            select(ServiceLink).where(
                ServiceLink.port_id.in_(port_ids),
                ServiceLink.status == "active",
            )
        ).all()
        for link in active_links:
            active_service_links[link.port_id] = link
            if link.customer_id:
                cust = db.get(Customer, link.customer_id)
                if cust:
                    customers_map[link.customer_id] = cust
            if link.onu_device_id:
                onu = db.get(Device, link.onu_device_id)
                if onu:
                    onus_map[link.onu_device_id] = onu

    # Busca terminais correspondentes a essas portas
    terminals_by_port: dict[uuid.UUID, Terminal] = {}
    term_ids: list[uuid.UUID] = []
    if port_ids:
        terms = db.scalars(
            select(Terminal).where(
                Terminal.entity_id.in_(port_ids),
                Terminal.entity_type == "port",
            )
        ).all()
        for t in terms:
            if t.entity_id:
                terminals_by_port[t.entity_id] = t
            term_ids.append(t.id)

    # Busca reservas ativas nesses terminais
    active_reservations: dict[uuid.UUID, TerminalReservation] = {}
    if term_ids:
        res_list = db.scalars(
            select(TerminalReservation).where(
                TerminalReservation.terminal_id.in_(term_ids),
                TerminalReservation.is_active.is_(True),
            )
        ).all()
        for r in res_list:
            active_reservations[r.terminal_id] = r

    # Busca conexões ativas nesses terminais
    active_connections: set[uuid.UUID] = set()
    if term_ids:
        conns = db.scalars(
            select(Connection).where(
                Connection.is_active.is_(True),
                or_(
                    Connection.terminal_a_id.in_(term_ids),
                    Connection.terminal_b_id.in_(term_ids),
                ),
            )
        ).all()
        for c in conns:
            if c.terminal_a_id in term_ids:
                active_connections.add(c.terminal_a_id)
            if c.terminal_b_id in term_ids:
                active_connections.add(c.terminal_b_id)

    occupied_count = 0
    reserved_count = 0
    connected_without_customer_count = 0
    port_details: list[dict[str, Any]] = []

    for port in ports:
        term = terminals_by_port.get(port.id)
        has_active_link = port.id in active_service_links
        is_reserved = (term is not None and term.id in active_reservations) or (
            term is not None and term.occupancy == "reserved"
        )
        is_connected = (term is not None and term.id in active_connections) or (
            term is not None and term.occupancy == "connected"
        )

        notes_str = (port.notes or "").lower()
        is_damaged = any(k in notes_str for k in ["danificad", "defeito", "damaged", "quebrad", "broken"])

        if has_active_link:
            port_status = "customer_connected"
            occupied_count += 1
        elif is_connected:
            port_status = "connected_no_customer"
            connected_without_customer_count += 1
            occupied_count += 1
        elif is_reserved:
            port_status = "reserved"
            reserved_count += 1
        else:
            port_status = "free"

        srv_link: ServiceLink | None = active_service_links.get(port.id)
        cust = customers_map.get(srv_link.customer_id) if srv_link and srv_link.customer_id else None
        onu = onus_map.get(srv_link.onu_device_id) if srv_link and srv_link.onu_device_id else None
        res = active_reservations.get(term.id) if term and term.id in active_reservations else None

        port_details.append(
            {
                "id": str(port.id),
                "name": port.name,
                "role": port.role,
                "connector_type": port.connector_type,
                "status": port_status,
                "is_damaged": is_damaged,
                "terminal_id": str(term.id) if term else None,
                "notes": port.notes,
                "service_link": {
                    "id": str(link.id),
                    "status": link.status,
                    "activated_at": link.activated_at.isoformat(),
                    "version": link.version,
                    "notes": link.notes,
                }
                if link
                else None,
                "customer": {
                    "id": str(cust.id),
                    "code": cust.code,
                    "name": cust.name,
                    "phone": cust.phone,
                    "email": cust.email,
                }
                if cust
                else None,
                "onu": {
                    "id": str(onu.id),
                    "code": onu.code,
                    "serial_number": onu.serial_number,
                    "model": onu.model,
                }
                if onu
                else None,
                "reservation": {
                    "id": str(res.id),
                    "reason": res.reason,
                    "reserved_by": res.reserved_by.name if res and res.reserved_by else None,
                    "expires_at": res.expires_at.isoformat() if res and res.expires_at else None,
                }
                if res
                else None,
            }
        )

    free_count = max(0, total_ports - occupied_count - reserved_count)

    return {
        "structure_id": str(structure_id),
        "total_ports": total_ports,
        "occupied_ports": occupied_count,
        "reserved_ports": reserved_count,
        "free_ports": free_count,
        "connected_without_customer": connected_without_customer_count,
        "ports": port_details,
    }
