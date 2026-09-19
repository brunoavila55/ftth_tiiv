"""R08 (PERF-01 / PERF-03): dashboard sem N+1 (mesmos números) e índice de terminais por entidade."""

import random
from datetime import UTC, datetime

from sqlalchemy import event, or_, select, text
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.modules.connectivity.models import Connection, Terminal, TerminalReservation
from app.modules.customers.models import Customer, ServiceLink
from app.modules.inventory.models import Device, Port, Site, Structure
from app.modules.reports.service import calculate_dashboard_summary

PORT_STATES = [
    "free",
    "free",
    "link",  # atendimento ativo
    "occ_connected",  # terminal.occupancy == connected
    "occ_customer_connected",
    "occ_reserved",
    "active_connection_a",  # conexão ativa com o terminal como ponta A
    "active_connection_b",
    "active_reservation",
    "inactive_connection",  # não conta
    "inactive_reservation",  # não conta
    "inactive_link",  # atendimento desativado: não conta
]


def build_dataset(db: Session, n_ctos: int, seed: int = 7) -> None:
    """Cria CTOs com 0..6 portas em estados variados (inclui CTO aposentada e não-CTO)."""
    rng = random.Random(seed)
    site = Site(
        code="S-PERF", name="Site", kind="pop", status="installed", location="POINT(-46 -23)"
    )
    customer = Customer(code="C-PERF", name="Cliente", version=1)
    db.add_all([site, customer])
    db.flush()

    def structure(code: str, kind: str, status: str) -> Structure:
        s = Structure(
            code=code,
            kind=kind,
            status=status,
            condition="ok",
            capacity=8,
            location="POINT(-46 -23)",
            site_id=site.id,
            version=1,
        )
        db.add(s)
        return s

    ctos = [
        structure(f"CTO-{i:04d}", "cto", "retired" if i % 23 == 0 else "installed")
        for i in range(n_ctos)
    ]
    structure("CEO-PERF", "ceo", "installed")
    db.flush()

    onu_seq = 0
    for cto in ctos:
        for n in range(rng.randint(0, 6)):
            port = Port(
                structure_id=cto.id,
                name=f"P{n}",
                role="customer_drop",
                connector_type="SC/APC",
                version=1,
            )
            db.add(port)
            db.flush()
            state = rng.choice(PORT_STATES)
            term = Terminal(
                kind="port",
                structure_id=cto.id,
                entity_type="port",
                entity_id=port.id,
                label=f"{cto.code}-P{n}",
                version=1,
                occupancy={
                    "occ_connected": "connected",
                    "occ_customer_connected": "customer_connected",
                    "occ_reserved": "reserved",
                }.get(state, "free"),
                is_occupied=False,
            )
            db.add(term)
            db.flush()
            if state in ("link", "inactive_link"):
                onu_seq += 1
                onu = Device(
                    code=f"ONU-{onu_seq}",
                    kind="onu",
                    manufacturer="M",
                    model="X",
                    site_id=site.id,
                    status="active",
                    version=1,
                )
                db.add(onu)
                db.flush()
                db.add(
                    ServiceLink(
                        customer_id=customer.id,
                        onu_device_id=onu.id,
                        port_id=port.id,
                        status="active" if state == "link" else "deactivated",
                        activated_at=datetime.now(UTC),
                        version=1,
                    )
                )
            elif state.startswith(("active_connection", "inactive_connection")):
                other = Terminal(kind="fiber_end", structure_id=cto.id, label="peer", version=1)
                db.add(other)
                db.flush()
                a, b = (
                    (term, other)
                    if state.endswith("_a") or state.startswith("inactive")
                    else (other, term)
                )
                db.add(
                    Connection(
                        structure_id=cto.id,
                        terminal_a_id=a.id,
                        terminal_b_id=b.id,
                        connection_type="fusion",
                        loss_db=0.1,
                        is_active=state.startswith("active"),
                        version=1,
                    )
                )
            elif state in ("active_reservation", "inactive_reservation"):
                db.add(
                    TerminalReservation(
                        terminal_id=term.id,
                        reason="r",
                        is_active=state == "active_reservation",
                        version=1,
                    )
                )
    db.commit()


def legacy_bucket_counts(db: Session) -> tuple[int, int, int, int]:
    """Implementação original (N+1) mantida aqui como oráculo do comportamento."""
    ctos = db.scalars(
        select(Structure).where(Structure.kind == "cto", Structure.status != "retired")
    ).all()
    empty_0 = low = high = full = 0
    for cto in ctos:
        ports = db.scalars(select(Port).where(Port.structure_id == cto.id)).all()
        total_p = len(ports)
        if total_p == 0:
            empty_0 += 1
            continue
        port_ids = [p.id for p in ports]
        active_link_port_ids = set(
            db.scalars(
                select(ServiceLink.port_id).where(
                    ServiceLink.port_id.in_(port_ids), ServiceLink.status == "active"
                )
            ).all()
        )
        terminals = db.scalars(
            select(Terminal).where(Terminal.entity_id.in_(port_ids), Terminal.entity_type == "port")
        ).all()
        term_ids = [t.id for t in terminals]
        term_map = {t.entity_id: t for t in terminals if t.entity_id}
        active_conns = set()
        if term_ids:
            for c in db.scalars(
                select(Connection).where(
                    Connection.is_active.is_(True),
                    or_(
                        Connection.terminal_a_id.in_(term_ids),
                        Connection.terminal_b_id.in_(term_ids),
                    ),
                )
            ).all():
                if c.terminal_a_id in term_ids:
                    active_conns.add(c.terminal_a_id)
                if c.terminal_b_id in term_ids:
                    active_conns.add(c.terminal_b_id)
        active_res = set()
        if term_ids:
            active_res = set(
                db.scalars(
                    select(TerminalReservation.terminal_id).where(
                        TerminalReservation.terminal_id.in_(term_ids),
                        TerminalReservation.is_active.is_(True),
                    )
                ).all()
            )
        occupied = 0
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
                occupied += 1
        pct = (occupied / total_p) * 100.0
        if pct == 0:
            empty_0 += 1
        elif pct <= 50:
            low += 1
        elif pct < 100:
            high += 1
        else:
            full += 1
    return empty_0, low, high, full


class StatementCounter:
    def __init__(self) -> None:
        self.count = 0

    def __enter__(self) -> "StatementCounter":
        event.listen(get_engine(), "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc: object) -> None:
        event.remove(get_engine(), "before_cursor_execute", self._on)

    def _on(self, *args: object) -> None:
        self.count += 1


def test_dashboard_buckets_match_legacy_implementation(db_session: Session) -> None:
    build_dataset(db_session, n_ctos=150)
    expected = legacy_bucket_counts(db_session)
    assert sum(expected) > 100 and all(v > 0 for v in expected)  # dataset exercita as 4 faixas

    b = calculate_dashboard_summary(db_session).ctos_occupancy
    assert (b.empty_0_pct, b.low_1_to_50_pct, b.high_51_to_99_pct, b.full_100_pct) == expected


def test_dashboard_statement_count_does_not_grow_with_ctos(db_session: Session) -> None:
    build_dataset(db_session, n_ctos=400)
    with StatementCounter() as counter:
        calculate_dashboard_summary(db_session)
    assert counter.count <= 10, f"{counter.count} statements para o dashboard"


def test_terminals_entity_index_exists_and_is_used(db_session: Session) -> None:
    idx = db_session.execute(
        text("SELECT indexdef FROM pg_indexes WHERE indexname = 'idx_terminals_entity'")
    ).scalar()
    assert idx is not None and "(entity_type, entity_id)" in idx

    db_session.execute(text("SET LOCAL enable_seqscan = off"))
    plan = "\n".join(
        row[0]
        for row in db_session.execute(
            text(
                "EXPLAIN SELECT * FROM terminals WHERE entity_type = 'port' "
                "AND entity_id = '00000000-0000-4000-8000-000000000001'"
            )
        )
    )
    assert "idx_terminals_entity" in plan, plan
    db_session.rollback()
