import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.permissions import has_permission
from app.modules.cables.models import Cable, CableSegment, Fiber, Tube
from app.modules.connectivity.models import Connection, Terminal, TerminalReservation
from app.modules.customers.models import Customer, ServiceLink
from app.modules.gis.service import get_topology_revision
from app.modules.identity.models import User
from app.modules.inventory.models import Device, Port, Site, Structure
from app.schemas.common import UserRole
from app.schemas.reports import (
    CableCapacityReportItem,
    CTOOccupancyBuckets,
    CTOOccupancyReportItem,
    DashboardSummaryResponse,
    GlobalSearchResponse,
    InconsistencyReportItem,
    SearchGroup,
    SearchResultItem,
)


def calculate_dashboard_summary(db: Session) -> DashboardSummaryResponse:
    """Calcula indicadores consolidados, buckets de ocupação de CTOs e alertas técnicos sem inventar dados."""
    total_sites = db.scalar(select(func.count(Site.id)).where(Site.status != "retired")) or 0
    total_structures = (
        db.scalar(select(func.count(Structure.id)).where(Structure.status != "retired")) or 0
    )
    total_cables = db.scalar(select(func.count(Cable.id)).where(Cable.status != "retired")) or 0
    total_customers = db.scalar(select(func.count(Customer.id))) or 0
    total_active_links = (
        db.scalar(select(func.count(ServiceLink.id)).where(ServiceLink.status == "active")) or 0
    )

    # Busca todas as CTOs não aposentadas
    ctos = db.scalars(
        select(Structure).where(Structure.kind == "cto", Structure.status != "retired")
    ).all()

    empty_0 = 0
    low_1_to_50 = 0
    high_51_to_99 = 0
    full_100 = 0

    for cto in ctos:
        ports = db.scalars(select(Port).where(Port.structure_id == cto.id)).all()
        total_p = len(ports)
        if total_p == 0:
            empty_0 += 1
            continue

        port_ids = [p.id for p in ports]
        # Atendimentos ativos nessas portas
        active_links = db.scalars(
            select(ServiceLink.port_id).where(
                ServiceLink.port_id.in_(port_ids),
                ServiceLink.status == "active",
            )
        ).all()
        active_link_port_ids = set(active_links)

        # Terminais dessas portas
        terminals = db.scalars(
            select(Terminal).where(
                Terminal.entity_id.in_(port_ids),
                Terminal.entity_type == "port",
            )
        ).all()
        term_ids = [t.id for t in terminals]
        term_map = {t.entity_id: t for t in terminals if t.entity_id}

        # Conexões ativas
        active_conns = set()
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
                    active_conns.add(c.terminal_a_id)
                if c.terminal_b_id in term_ids:
                    active_conns.add(c.terminal_b_id)

        # Reservas ativas
        active_res = set()
        if term_ids:
            res_list = db.scalars(
                select(TerminalReservation.terminal_id).where(
                    TerminalReservation.terminal_id.in_(term_ids),
                    TerminalReservation.is_active.is_(True),
                )
            ).all()
            active_res = set(res_list)

        occupied_count = 0
        for p in ports:
            term = term_map.get(p.id)
            if (
                p.id in active_link_port_ids
                or (
                    term
                    and (
                        term.id in active_conns
                        or term.occupancy in ("connected", "customer_connected")
                    )
                )
                or (term and (term.id in active_res or term.occupancy == "reserved"))
            ):
                occupied_count += 1

        occupancy_pct = (occupied_count / total_p) * 100.0 if total_p > 0 else 0.0

        if occupancy_pct == 0:
            empty_0 += 1
        elif 0 < occupancy_pct <= 50:
            low_1_to_50 += 1
        elif 50 < occupancy_pct < 100:
            high_51_to_99 += 1
        else:
            full_100 += 1

    ctos_occupancy = CTOOccupancyBuckets(
        empty_0_pct=empty_0,
        low_1_to_50_pct=low_1_to_50,
        high_51_to_99_pct=high_51_to_99,
        full_100_pct=full_100,
    )

    # Alertas de documentação incompleta
    alerts: list[str] = []

    cables_without_segments = (
        db.query(Cable).filter(Cable.status != "retired", ~Cable.segments.any()).count()
    )
    if cables_without_segments > 0:
        alerts.append(
            f"{cables_without_segments} cabo(s) cadastrado(s) sem nenhum segmento georreferenciado"
        )

    structs_without_site = (
        db.scalar(
            select(func.count(Structure.id)).where(
                Structure.status != "retired", Structure.site_id.is_(None)
            )
        )
        or 0
    )
    if structs_without_site > 0:
        alerts.append(f"{structs_without_site} estrutura(s) sem POP / Site de referência associado")

    damaged_ports = (
        db.scalar(
            select(func.count(Port.id)).where(
                or_(
                    Port.notes.ilike("%danificad%"),
                    Port.notes.ilike("%defeito%"),
                    Port.notes.ilike("%quebrad%"),
                )
            )
        )
        or 0
    )
    if damaged_ports > 0:
        alerts.append(f"{damaged_ports} porta(s) física(s) com anotação de dano ou defeito")

    current_rev = get_topology_revision(db)

    return DashboardSummaryResponse(
        total_sites=total_sites,
        total_structures=total_structures,
        total_cables=total_cables,
        total_customers=total_customers,
        total_active_service_links=total_active_links,
        ctos_occupancy=ctos_occupancy,
        incomplete_documentation_alerts=alerts,
        topology_revision=current_rev,
    )


def execute_global_search(
    db: Session,
    q: str,
    limit: int = 20,
    current_user: User | None = None,
) -> GlobalSearchResponse:
    """Busca global textual por código, nome ou serial com agrupamento e proteção de escopo."""
    clean_q = q.strip()
    groups: list[SearchGroup] = []
    total_results = 0

    # Sites
    site_matches = (
        db.query(Site)
        .filter(
            Site.status != "retired",
            or_(Site.code.ilike(f"%{clean_q}%"), Site.name.ilike(f"%{clean_q}%")),
        )
        .limit(limit)
        .all()
    )
    if site_matches:
        site_items = [
            SearchResultItem(
                id=str(s.id),
                entity_type="site",
                code=s.code,
                name=s.name,
                status=s.status,
            )
            for s in site_matches
        ]
        groups.append(SearchGroup(entity_type="site", items=site_items))
        total_results += len(site_items)

    # Structures (Postes, Caixas CEO/CTO)
    structure_matches = (
        db.query(Structure)
        .filter(
            Structure.status != "retired",
            Structure.code.ilike(f"%{clean_q}%"),
        )
        .limit(limit)
        .all()
    )
    if structure_matches:
        structure_items = [
            SearchResultItem(
                id=str(st.id),
                entity_type=st.kind,
                code=st.code,
                name=None,
                status=st.status,
            )
            for st in structure_matches
        ]
        groups.append(SearchGroup(entity_type="structure", items=structure_items))
        total_results += len(structure_items)

    # Cables
    cable_matches = (
        db.query(Cable)
        .filter(
            Cable.status != "retired",
            or_(Cable.code.ilike(f"%{clean_q}%"), Cable.model.ilike(f"%{clean_q}%")),
        )
        .limit(limit)
        .all()
    )
    if cable_matches:
        cable_items = [
            SearchResultItem(
                id=str(c.id),
                entity_type="cable",
                code=c.code,
                name=c.model,
                status=c.status,
            )
            for c in cable_matches
        ]
        groups.append(SearchGroup(entity_type="cable", items=cable_items))
        total_results += len(cable_items)

    # Devices (OLTs, Switches, ONUs com serial_number)
    device_matches = (
        db.query(Device)
        .filter(
            Device.status != "retired",
            or_(
                Device.code.ilike(f"%{clean_q}%"),
                Device.model.ilike(f"%{clean_q}%"),
                Device.serial_number.ilike(f"%{clean_q}%"),
            ),
        )
        .limit(limit)
        .all()
    )
    if device_matches:
        device_items = [
            SearchResultItem(
                id=str(d.id),
                entity_type=d.kind,
                code=d.code,
                name=f"{d.manufacturer} {d.model}" if d.manufacturer else d.model,
                status=d.status,
            )
            for d in device_matches
        ]
        groups.append(SearchGroup(entity_type="device", items=device_items))
        total_results += len(device_items)

    # Customers (Assinantes — Apenas se o usuário tiver permissão customers:read)
    user_can_read_customers = False
    if current_user is not None:
        try:
            role_enum = UserRole(current_user.role)
            user_can_read_customers = has_permission(role_enum, "customers:read")
        except ValueError:
            user_can_read_customers = False
    if user_can_read_customers:
        customer_matches = (
            db.query(Customer)
            .filter(
                or_(
                    Customer.code.ilike(f"%{clean_q}%"),
                    Customer.name.ilike(f"%{clean_q}%"),
                    Customer.phone.ilike(f"%{clean_q}%"),
                    Customer.email.ilike(f"%{clean_q}%"),
                )
            )
            .limit(limit)
            .all()
        )
        if customer_matches:
            customer_items = [
                SearchResultItem(
                    id=str(cust.id),
                    entity_type="customer",
                    code=cust.code,
                    name=cust.name,
                    status="active",
                )
                for cust in customer_matches
            ]
            groups.append(SearchGroup(entity_type="customer", items=customer_items))
            total_results += len(customer_items)

    return GlobalSearchResponse(
        query=clean_q,
        total_results=total_results,
        groups=groups,
    )


def get_cto_occupancy_report(
    db: Session,
    site_id: uuid.UUID | None = None,
    min_occupancy_pct: float | None = None,
    max_occupancy_pct: float | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CTOOccupancyReportItem], int]:
    """Relatório paginado e filtrável de ocupação de portas das caixas CTO."""
    query = select(Structure).where(Structure.kind == "cto")
    if site_id:
        query = query.where(Structure.site_id == site_id)
    if status_filter:
        query = query.where(Structure.status == status_filter)
    else:
        query = query.where(Structure.status != "retired")

    ctos = db.scalars(query.order_by(Structure.code.asc())).all()

    all_items: list[CTOOccupancyReportItem] = []

    for cto in ctos:
        ports = db.scalars(select(Port).where(Port.structure_id == cto.id)).all()
        total_p = len(ports)
        port_ids = [p.id for p in ports]

        active_links = set(
            db.scalars(
                select(ServiceLink.port_id).where(
                    ServiceLink.port_id.in_(port_ids),
                    ServiceLink.status == "active",
                )
            ).all()
        )

        terminals = db.scalars(
            select(Terminal).where(
                Terminal.entity_id.in_(port_ids),
                Terminal.entity_type == "port",
            )
        ).all()
        term_ids = [t.id for t in terminals]
        term_map = {t.entity_id: t for t in terminals if t.entity_id}

        active_conns = set()
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
                    active_conns.add(c.terminal_a_id)
                if c.terminal_b_id in term_ids:
                    active_conns.add(c.terminal_b_id)

        active_res = set()
        if term_ids:
            res_list = db.scalars(
                select(TerminalReservation.terminal_id).where(
                    TerminalReservation.terminal_id.in_(term_ids),
                    TerminalReservation.is_active.is_(True),
                )
            ).all()
            active_res = set(res_list)

        occupied = 0
        reserved = 0
        for p in ports:
            term = term_map.get(p.id)
            if p.id in active_links or (
                term
                and (
                    term.id in active_conns or term.occupancy in ("connected", "customer_connected")
                )
            ):
                occupied += 1
            elif term and (term.id in active_res or term.occupancy == "reserved"):
                reserved += 1

        free = max(0, total_p - occupied - reserved)
        pct = round((occupied / total_p) * 100.0, 1) if total_p > 0 else 0.0

        if min_occupancy_pct is not None and pct < min_occupancy_pct:
            continue
        if max_occupancy_pct is not None and pct > max_occupancy_pct:
            continue

        site_name = None
        if cto.site_id:
            site = db.get(Site, cto.site_id)
            site_name = site.name if site else None

        all_items.append(
            CTOOccupancyReportItem(
                structure_id=str(cto.id),
                code=cto.code,
                site_id=str(cto.site_id) if cto.site_id else None,
                site_name=site_name,
                total_ports=total_p,
                occupied_ports=occupied,
                reserved_ports=reserved,
                free_ports=free,
                occupancy_pct=pct,
                status=cto.status,
            )
        )

    total_count = len(all_items)
    paginated = all_items[offset : offset + limit]
    return paginated, total_count


def get_cable_capacity_report(
    db: Session,
    status_filter: str | None = None,
    min_usage_pct: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CableCapacityReportItem], int]:
    """Relatório paginado de capacidade óptica de cabos e uso de fibras."""
    query = select(Cable)
    if status_filter:
        query = query.where(Cable.status == status_filter)
    else:
        query = query.where(Cable.status != "retired")

    cables = db.scalars(query.order_by(Cable.code.asc())).all()

    all_items: list[CableCapacityReportItem] = []

    for cable in cables:
        # Busca todas as fibras associadas a este cabo através dos tubos
        tubes = db.scalars(select(Tube).where(Tube.cable_id == cable.id)).all()
        tube_ids = [t.id for t in tubes]

        fibers: list[Fiber] = []
        if tube_ids:
            fibers = list(db.scalars(select(Fiber).where(Fiber.tube_id.in_(tube_ids))).all())

        total_fibers = len(fibers) if fibers else cable.fiber_count
        fiber_ids = [f.id for f in fibers]

        connected_fibers = 0
        reserved_fibers = 0
        damaged_fibers = 0

        if fiber_ids:
            # Terminais de fibra
            fiber_terms = db.scalars(
                select(Terminal).where(
                    Terminal.entity_id.in_(fiber_ids),
                    Terminal.entity_type == "fiber",
                )
            ).all()
            term_ids = [t.id for t in fiber_terms]
            term_map = {t.entity_id: t for t in fiber_terms if t.entity_id}

            active_conns = set()
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
                        active_conns.add(c.terminal_a_id)
                    if c.terminal_b_id in term_ids:
                        active_conns.add(c.terminal_b_id)

            for f in fibers:
                term = term_map.get(f.id)
                if term and (term.id in active_conns or term.occupancy == "connected"):
                    connected_fibers += 1
                elif term and term.occupancy == "reserved":
                    reserved_fibers += 1
                elif term and term.occupancy == "damaged":
                    damaged_fibers += 1

        free_fibers = max(0, total_fibers - connected_fibers - reserved_fibers - damaged_fibers)
        usage_pct = (
            round(((connected_fibers + reserved_fibers) / total_fibers) * 100.0, 1)
            if total_fibers > 0
            else 0.0
        )

        if min_usage_pct is not None and usage_pct < min_usage_pct:
            continue

        all_items.append(
            CableCapacityReportItem(
                cable_id=str(cable.id),
                code=cable.code,
                model=cable.model,
                cable_type="optical_cable",
                total_fibers=total_fibers,
                connected_fibers=connected_fibers,
                reserved_fibers=reserved_fibers,
                free_fibers=free_fibers,
                damaged_fibers=damaged_fibers,
                usage_pct=usage_pct,
                status=cable.status,
            )
        )

    total_count = len(all_items)
    paginated = all_items[offset : offset + limit]
    return paginated, total_count


def get_inconsistencies_report(
    db: Session,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[InconsistencyReportItem], int]:
    """Relatório paginado de pendências cadastrais e inconsistências técnicas."""
    items: list[InconsistencyReportItem] = []

    # 1. Cabos ativos sem segmentos georreferenciados
    cables_without_segments = db.scalars(
        select(Cable).where(Cable.status != "retired", ~Cable.segments.any())
    ).all()
    for c in cables_without_segments:
        items.append(
            InconsistencyReportItem(
                inconsistency_type="cable_without_segments",
                entity_type="cable",
                entity_id=str(c.id),
                code=c.code,
                severity="critical",
                description="Cabo cadastrado no inventário sem nenhum segmento georreferenciado na malha física.",
            )
        )

    # 2. Segmentos de cabo sem comprimento efetivo calculado
    bad_segments = db.scalars(
        select(CableSegment).where(CableSegment.effective_length_m <= 0)
    ).all()
    for seg in bad_segments:
        items.append(
            InconsistencyReportItem(
                inconsistency_type="zero_effective_length",
                entity_type="cable_segment",
                entity_id=str(seg.id),
                code=f"SEG-{str(seg.id)[:8]}",
                severity="warning",
                description="Segmento de rota com comprimento óptico efetivo zerado ou negativo.",
            )
        )

    # 3. Estruturas sem POP / Site de referência
    structs_without_site = db.scalars(
        select(Structure).where(Structure.status != "retired", Structure.site_id.is_(None))
    ).all()
    for st in structs_without_site:
        items.append(
            InconsistencyReportItem(
                inconsistency_type="structure_without_site",
                entity_type="structure",
                entity_id=str(st.id),
                code=st.code,
                severity="warning",
                description=f"Estrutura do tipo {st.kind} sem POP ou Site pai associado.",
            )
        )

    # 4. Portas com notas de avaria/dano
    damaged_ports = db.scalars(
        select(Port).where(
            or_(
                Port.notes.ilike("%danificad%"),
                Port.notes.ilike("%defeito%"),
                Port.notes.ilike("%quebrad%"),
            )
        )
    ).all()
    for p in damaged_ports:
        items.append(
            InconsistencyReportItem(
                inconsistency_type="damaged_port",
                entity_type="port",
                entity_id=str(p.id),
                code=p.name,
                severity="warning",
                description=f"Porta física com observação de dano: '{p.notes}'",
            )
        )

    total_count = len(items)
    paginated = items[offset : offset + limit]
    return paginated, total_count
