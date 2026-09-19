"""R14 (PERF-02 / PERF-14): trace e impacto em memória — mesmos resultados, poucas queries.

- Caracterização: grafos aleatórios (ciclos, ambiguidade, splitters, pontas abertas, limites)
  comparados com a implementação original (tests/legacy_topology_service.py, usada como oráculo).
- Desempenho: nº de statements de /topology/trace independe de max_hops (≤ 10) e o de
  /topology/impact independe do nº de clientes (≤ 30).
"""

import random
import uuid
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.cables.models import Cable, CableSegment, Fiber, FiberSegment, Tube
from app.modules.connectivity.models import (
    Connection,
    InternalEdge,
    Splitter,
    SplitterOutput,
    Terminal,
)
from app.modules.customers.models import Customer, ServiceLink
from app.modules.gis.helpers import linestring_geometry_to_wkb
from app.modules.inventory.models import Device, Port, Site, Structure
from app.modules.topology import service as new_service
from app.schemas.geojson import LineStringGeometry
from app.schemas.topology import (
    ImpactAnalysisRequest,
    TraceDirection,
    TraceRequest,
)
from tests import legacy_topology_service as legacy_service
from tests.integration.test_dashboard_performance import StatementCounter

POINT = "POINT(-46.6333 -23.5505)"


class NetworkBuilder:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.tag = uuid.uuid4().hex[:6]  # códigos únicos: várias redes por teste
        self.site = Site(
            code=f"S-TOPO-{self.tag}",
            name="S",
            kind="pop",
            status="installed",
            location=POINT,
            version=1,
        )
        db.add(self.site)
        db.flush()
        self.structures = [
            Structure(
                code=f"ST-{i}-{self.tag}",
                kind="ceo",
                status="installed",
                condition="ok",
                capacity=0,
                location=POINT,
                site_id=self.site.id,
                version=1,
            )
            for i in range(3)
        ]
        db.add_all(self.structures)
        self.cable = Cable(
            code=f"CAB-TOPO-{self.tag}",
            model="M",
            fiber_count=1000,
            tube_count=1,
            color_standard="NBR",
            status="installed",
            version=1,
        )
        db.add(self.cable)
        db.flush()
        self.tube = Tube(
            cable_id=self.cable.id, number=1, color_name="Verde", is_logical_group=True, version=1
        )
        db.add(self.tube)
        db.flush()
        self.fiber_seq = 0
        self.terminal_seq = 0

    def terminal(self, structure: Structure | None = None, port: Port | None = None) -> Terminal:
        self.terminal_seq += 1
        structure = structure or self.structures[self.terminal_seq % len(self.structures)]
        term = Terminal(
            kind="port" if port else "fiber_endpoint",
            structure_id=structure.id,
            label=f"T{self.terminal_seq:03d}",
            occupancy="free",
            is_occupied=False,
            version=1,
            entity_type="port" if port else None,
            entity_id=port.id if port else None,
        )
        self.db.add(term)
        self.db.flush()
        return term

    def fiber_segment(self, a: Terminal, b: Terminal, length_m: float) -> FiberSegment:
        self.fiber_seq += 1
        line = LineStringGeometry(coordinates=[(-46.63, -23.55), (-46.64, -23.56)])
        seg = CableSegment(
            cable_id=self.cable.id,
            origin_structure_id=self.structures[0].id,
            destination_structure_id=self.structures[1].id,
            geometry=linestring_geometry_to_wkb(line),
            map_length_m=length_m,
            slack_length_m=0.0,
            effective_length_m=length_m,
            length_source="calculated",
            version=1,
        )
        fiber = Fiber(
            cable_id=self.cable.id,
            tube_id=self.tube.id,
            global_number=self.fiber_seq,
            tube_position=1,
            color_name="Verde",
            status="installed",
            version=1,
        )
        self.db.add_all([seg, fiber])
        self.db.flush()
        fs = FiberSegment(
            cable_segment_id=seg.id,
            fiber_id=fiber.id,
            fiber_number=self.fiber_seq,
            terminal_a_id=a.id,
            terminal_b_id=b.id,
            occupancy="free",
            version=1,
        )
        self.db.add(fs)
        self.db.flush()
        return fs

    def connection(
        self, a: Terminal, b: Terminal, active: bool = True, loss: float = 0.1
    ) -> Connection:
        conn = Connection(
            terminal_a_id=a.id,
            terminal_b_id=b.id,
            connection_type="fusion_splice",
            loss_db=loss,
            structure_id=self.structures[0].id,
            is_active=active,
            version=1,
        )
        self.db.add(conn)
        self.db.flush()
        return conn

    def internal_edge(self, a: Terminal, b: Terminal) -> InternalEdge:
        edge = InternalEdge(
            terminal_a_id=a.id,
            terminal_b_id=b.id,
            edge_type="fiber_continuity",
            entity_type="fiber_segment",
            entity_id=uuid.uuid4(),
            loss_db=0.0,
            is_bidirectional=True,
            version=1,
        )
        self.db.add(edge)
        self.db.flush()
        return edge

    def splitter(
        self, code: str, inp: Terminal, outs: list[Terminal], measured: bool = False
    ) -> Splitter:
        spl = Splitter(
            structure_id=self.structures[0].id,
            code=code,
            splitter_type="balanced",
            ratio=f"1:{len(outs)}",
            input_terminal_id=inp.id,
            version=1,
        )
        self.db.add(spl)
        self.db.flush()
        for n, out in enumerate(outs, start=1):
            self.db.add(
                SplitterOutput(
                    splitter_id=spl.id,
                    output_number=n,
                    terminal_id=out.id,
                    nominal_loss_db=10.5,
                    measured_loss_db=10.9 if measured and n == 1 else None,
                    version=1,
                )
            )
        self.db.flush()
        return spl

    def port(self, role: str, device: Device | None = None, name: str = "P") -> Port:
        port = Port(
            name=name,
            role=role,
            device_id=device.id if device else None,
            structure_id=None if device else self.structures[0].id,
            connector_type="SC/APC",
            version=1,
        )
        self.db.add(port)
        self.db.flush()
        return port

    def device(self, code: str, kind: str) -> Device:
        dev = Device(
            code=f"{code}-{self.tag}",
            kind=kind,
            manufacturer="M",
            model="X",
            site_id=self.site.id,
            status="installed",
            condition="ok",
            version=1,
        )
        self.db.add(dev)
        self.db.flush()
        return dev


def build_random_network(db: Session, seed: int, n_terminals: int = 26) -> list[Terminal]:
    rng = random.Random(seed)
    b = NetworkBuilder(db)
    olt = b.device("OLT-R", "olt")
    onu = b.device("ONU-R", "onu")
    terminals: list[Terminal] = []
    for i in range(n_terminals):
        port = None
        roll = rng.random()
        if roll < 0.12:
            port = b.port("pon", olt, f"PON{i}")
        elif roll < 0.24:
            port = b.port("onu_port", onu, f"ONU{i}")
        elif roll < 0.30:
            port = b.port("customer_drop", None, f"DROP{i}")
        elif roll < 0.36:
            port = b.port("uplink", olt, f"UP{i}")
        terminals.append(b.terminal(port=port))

    def pick() -> Terminal:
        return rng.choice(terminals)

    used_fiber: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for _ in range(int(n_terminals * 0.55)):
        x, y = pick(), pick()
        if x is not y and (x.id, y.id) not in used_fiber:
            used_fiber.add((x.id, y.id))
            b.fiber_segment(x, y, round(rng.uniform(10, 900), 2))
    for _ in range(int(n_terminals * 0.35)):
        x, y = pick(), pick()
        if x is not y:
            b.connection(x, y, active=rng.random() < 0.85, loss=round(rng.uniform(0, 0.3), 2))
    seen_edges: set[frozenset[uuid.UUID]] = set()
    for _ in range(int(n_terminals * 0.2)):
        x, y = pick(), pick()
        if x is not y and frozenset((x.id, y.id)) not in seen_edges:
            seen_edges.add(frozenset((x.id, y.id)))
            b.internal_edge(x, y)
    pool = terminals[:]
    rng.shuffle(pool)
    for n in range(rng.randint(1, 3)):
        if len(pool) >= 4:
            inp, outs = pool.pop(), [pool.pop() for _ in range(rng.randint(2, 3))]
            b.splitter(f"SPL-{seed}-{n}", inp, outs, measured=rng.random() < 0.5)
    # atendimentos ativos em algumas portas (valida pontas por ServiceLink)
    customer = Customer(code=f"CLI-{seed}", name="Cliente", version=1)
    db.add(customer)
    db.flush()
    for term in terminals:
        if term.entity_id and rng.random() < 0.25:
            link_onu = b.device(
                f"ONU-L{term.terminal_seq if hasattr(term, 'terminal_seq') else term.label}", "onu"
            )
            db.add(
                ServiceLink(
                    customer_id=customer.id,
                    onu_device_id=link_onu.id,
                    port_id=term.entity_id,
                    status="active",
                    version=1,
                )
            )
    db.commit()
    return terminals


def canonical(resp: Any) -> dict[str, Any]:
    data = resp.model_dump(mode="json")
    data["paths"] = sorted(data["paths"], key=lambda p: p["path_id"])
    data["warnings"] = sorted(data["warnings"])
    data["unresolved_terminals"] = sorted(data["unresolved_terminals"])
    return data


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_new_trace_matches_legacy_implementation(db_session: Session, seed: int) -> None:
    terminals = build_random_network(db_session, seed)
    statuses: set[str] = set()
    compared = 0
    for term in terminals:
        for direction in (TraceDirection.DOWNSTREAM, TraceDirection.UPSTREAM):
            for max_hops, max_results in ((12, 50), (4, 5)):
                req = TraceRequest(
                    start_terminal_id=str(term.id),
                    direction=direction,
                    max_hops=max_hops,
                    max_results=max_results,
                )
                old = legacy_service.trace_optical_path(db_session, req)
                new = new_service.trace_optical_path(db_session, req)
                assert canonical(new) == canonical(old), (seed, term.label, direction, max_hops)
                statuses.add(str(new.status))
                compared += 1
    assert compared == len(terminals) * 4
    # o gerador exercita variedade de estados (não é só o caminho feliz)
    assert len(statuses) >= 3, statuses


def test_generated_networks_cover_cycles_ambiguity_and_open_ends(db_session: Session) -> None:
    seen: set[str] = set()
    for seed in (1, 2, 3, 4, 5, 6):
        for t in build_random_network(db_session, seed, n_terminals=22):
            for d in (TraceDirection.DOWNSTREAM, TraceDirection.UPSTREAM):
                seen.add(
                    str(
                        new_service.trace_optical_path(
                            db_session,
                            TraceRequest(start_terminal_id=str(t.id), direction=d, max_hops=10),
                        ).status
                    )
                )
    assert {"cycle_detected", "incomplete", "complete"} <= {s.split(".")[-1] for s in seen} | seen


def test_unknown_start_terminal_is_404(db_session: Session) -> None:
    from app.core.errors import NotFoundError

    with pytest.raises(NotFoundError):
        new_service.trace_optical_path(
            db_session, TraceRequest(start_terminal_id=str(uuid.uuid4()))
        )


# ---------------------------------------------------------------------------------------------
# Número de statements do trace independe de max_hops
# ---------------------------------------------------------------------------------------------


def build_chain(db: Session, length: int) -> Terminal:
    """Cadeia linear de `length` segmentos de fibra a partir de uma porta PON."""
    b = NetworkBuilder(db)
    olt = b.device("OLT-C", "olt")
    start = b.terminal(port=b.port("pon", olt))
    prev = start
    for _ in range(length):
        nxt = b.terminal()
        b.fiber_segment(prev, nxt, 50.0)
        prev = nxt
    db.commit()
    return start


@pytest.mark.parametrize("max_hops", [5, 50, 300])
def test_trace_statement_count_is_fixed_regardless_of_max_hops(
    db_session: Session, max_hops: int
) -> None:
    start = build_chain(db_session, 40)
    req = TraceRequest(
        start_terminal_id=str(start.id),
        direction=TraceDirection.DOWNSTREAM,
        max_hops=max_hops,
        max_results=50,
    )
    with StatementCounter() as counter:
        resp = new_service.trace_optical_path(db_session, req)
    assert counter.count <= 10, f"{counter.count} statements com max_hops={max_hops}"
    assert resp.paths  # produz caminho (truncado em max_hops ou completo)


def test_trace_hops_are_capped_by_configured_maximum(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MAX_TRACE_HOPS", "7")
    get_settings.cache_clear()
    start = build_chain(db_session, 30)
    resp = new_service.trace_optical_path(
        db_session,
        TraceRequest(
            start_terminal_id=str(start.id), direction=TraceDirection.DOWNSTREAM, max_hops=500
        ),
    )
    assert str(resp.status).endswith("limit_exceeded")
    assert len(resp.paths[0].steps) == 7  # min(max_hops=500, MAX_TRACE_HOPS=7)


# ---------------------------------------------------------------------------------------------
# Impacto: mesmos números e statements independentes do nº de clientes
# ---------------------------------------------------------------------------------------------


def build_pon(db: Session, customers: int) -> dict[str, Any]:
    """OLT -(tronco)- splitter -(fibra por cliente)- CTO -(drop)- ONU; 1 vínculo ativo por cliente."""
    b = NetworkBuilder(db)
    olt = b.device("OLT-I", "olt")
    t_pon = b.terminal(port=b.port("pon", olt, "PON-1"))
    t_in = b.terminal()
    trunk = b.fiber_segment(t_pon, t_in, 1200.0)
    outs = [b.terminal() for _ in range(customers)]
    b.splitter("SPL-I", t_in, outs)
    branch_segments: list[FiberSegment] = []
    for i, t_out in enumerate(outs):
        cto_port = b.port("client_access", None, f"CTO-P{i}")
        t_cto = b.terminal(port=cto_port)
        branch_segments.append(b.fiber_segment(t_out, t_cto, 80.0 + i))
        onu = b.device(f"ONU-{i:03d}", "onu")
        t_onu = b.terminal(port=b.port("onu_port", onu, f"ONUP-{i}"))
        b.connection(t_cto, t_onu)
        cust = Customer(code=f"CLI-{i:03d}", name=f"Cliente {i}", version=1)
        db.add(cust)
        db.flush()
        db.add(
            ServiceLink(
                customer_id=cust.id,
                onu_device_id=onu.id,
                port_id=cto_port.id,
                status="active",
                version=1,
            )
        )
    # clientes sem vínculo ativo (contam como "previamente desconectados")
    for i in range(3):
        db.add(Customer(code=f"CLI-OFF-{i}", name="Desligado", version=1))
    db.commit()
    return {
        "trunk": trunk.cable_segment_id,
        "branches": [s.cable_segment_id for s in branch_segments],
    }


def impact_canonical(resp: Any) -> dict[str, Any]:
    data = resp.model_dump(mode="json")
    data["impacted_customers"] = sorted(
        data["impacted_customers"], key=lambda c: (c["customer_code"], c["service_link_id"])
    )
    return data


@pytest.mark.parametrize("scenario", ["trunk", "one_branch", "none"])
def test_new_impact_matches_legacy_implementation(db_session: Session, scenario: str) -> None:
    net = build_pon(db_session, customers=8)
    broken = {"trunk": [net["trunk"]], "one_branch": [net["branches"][3]], "none": []}[scenario]
    if (
        scenario == "none"
    ):  # segmento existente mas sem nenhum vínculo passando: ramo inexistente na PON
        broken = [net["branches"][0]]
    revision = new_service.get_current_topology_revision(db_session)
    req = ImpactAnalysisRequest(
        cable_segment_ids=[str(s) for s in broken], expected_topology_revision=revision
    )
    old = legacy_service.analyze_cable_impact(db_session, req)
    new = new_service.analyze_cable_impact(db_session, req)
    assert impact_canonical(new) == impact_canonical(old)
    if scenario == "trunk":
        assert len(new.impacted_customers) == 8 and new.impacted_pon_ports == ["PON-1"]
    else:
        assert len(new.impacted_customers) == 1
        assert new.unaffected_customers_count == 7
    assert new.previously_disconnected_count == 3


@pytest.mark.parametrize("customers", [1, 50])
def test_impact_statement_count_does_not_depend_on_customer_count(
    db_session: Session, customers: int
) -> None:
    net = build_pon(db_session, customers=customers)
    revision = new_service.get_current_topology_revision(db_session)
    req = ImpactAnalysisRequest(
        cable_segment_ids=[str(net["trunk"])], expected_topology_revision=revision
    )
    with StatementCounter() as counter:
        resp = new_service.analyze_cable_impact(db_session, req)
    assert len(resp.impacted_customers) == customers
    assert counter.count <= 30, f"{counter.count} statements com {customers} vínculo(s)"
