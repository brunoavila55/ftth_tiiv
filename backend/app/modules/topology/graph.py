"""Grafo óptico em memória para rastreio e análise de impacto (PERF-02 / PERF-14).

A implementação anterior consultava o banco a cada salto (≥ 5 queries por terminal visitado e um
trace completo por cliente na análise de impacto). Aqui o subconjunto relevante da rede é carregado
em um número FIXO de queries (independente de `max_hops` e do nº de clientes) e a travessia roda em
memória, com a mesma semântica e os mesmos textos/valores da implementação original:

1. uma CTE recursiva calcula os terminais alcançáveis a partir dos pontos de partida (até
   `max_hops` saltos, respeitando a direção nos splitters);
2. uma query por tipo de elemento carrega só as arestas desses terminais;
3. `run_trace` percorre o grafo (BFS com bifurcação em splitters) sem tocar no banco.
"""

from __future__ import annotations

import hashlib
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import ARRAY, any_, bindparam, select, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session

from app.modules.cables.models import Cable, CableSegment, FiberSegment
from app.modules.connectivity.models import (
    Connection,
    InternalEdge,
    Splitter,
    SplitterOutput,
    Terminal,
)
from app.modules.customers.models import ServiceLink
from app.modules.inventory.models import Device, Port, Structure
from app.schemas.topology import (
    TraceDirection,
    TracePath,
    TraceRequest,
    TraceResponse,
    TraceStatus,
    TraceStep,
)

UUID_ARRAY = ARRAY(PGUUID(as_uuid=True))

# Papéis de porta que terminam o sinal (ver _is_endpoint_valid)
DOWNSTREAM_END_ROLES = ("customer_drop", "onu_port", "drop")
UPSTREAM_END_ROLES = ("pon", "olt_pon", "trunk")


@dataclass(frozen=True)
class TerminalData:
    id: uuid.UUID
    label: str
    structure_id: uuid.UUID | None
    structure_code: str | None
    entity_type: str | None
    entity_id: uuid.UUID | None


@dataclass(frozen=True)
class FiberEdge:
    id: uuid.UUID
    a: uuid.UUID
    b: uuid.UUID
    fiber_number: int
    segment_length_m: float | None  # None: trecho ausente (comprimento tratado como 0)
    cable_code: str | None


@dataclass(frozen=True)
class ConnectionEdge:
    id: uuid.UUID
    a: uuid.UUID
    b: uuid.UUID
    connection_type: str
    loss_db: float


@dataclass(frozen=True)
class InternalEdgeData:
    id: uuid.UUID
    a: uuid.UUID
    b: uuid.UUID
    edge_type: str
    loss_db: float


@dataclass(frozen=True)
class SplitterOutputData:
    splitter_id: uuid.UUID
    splitter_code: str
    ratio: str
    input_terminal_id: uuid.UUID
    output_number: int
    terminal_id: uuid.UUID
    loss_db: float  # medida, se houver; senão nominal


@dataclass(frozen=True)
class PortData:
    role: str
    device_id: uuid.UUID | None
    device_kind: str | None


@dataclass
class TraceGraph:
    terminals: dict[uuid.UUID, TerminalData] = field(default_factory=dict)
    fibers: dict[uuid.UUID, list[FiberEdge]] = field(default_factory=dict)
    connections: dict[uuid.UUID, list[ConnectionEdge]] = field(default_factory=dict)
    internals: dict[uuid.UUID, list[InternalEdgeData]] = field(default_factory=dict)
    # downstream: entrada do splitter -> saídas (ordenadas); upstream: terminal de saída -> saída
    splitter_outputs_by_input: dict[uuid.UUID, list[SplitterOutputData]] = field(
        default_factory=dict
    )
    splitter_output_by_terminal: dict[uuid.UUID, SplitterOutputData] = field(default_factory=dict)
    ports: dict[uuid.UUID, PortData] = field(default_factory=dict)
    port_names: dict[uuid.UUID, str] = field(default_factory=dict)
    active_link_ports: set[uuid.UUID] = field(default_factory=set)


# ------------------------------------------------------------------------------------------
# Carga (número fixo de queries)
# ------------------------------------------------------------------------------------------


def _reach_sql(direction: TraceDirection) -> str:
    # Splitter: downstream vai da entrada às saídas; upstream, da saída à entrada (como o trace).
    # Cada aresta é uma subconsulta LATERAL indexada por terminal (nada de varrer as tabelas a cada
    # nível da recursão).
    splitter_edge = (
        "SELECT so.terminal_id FROM splitters s "
        "JOIN splitter_outputs so ON so.splitter_id = s.id WHERE s.input_terminal_id = r.tid"
        if direction == TraceDirection.DOWNSTREAM
        else "SELECT s.input_terminal_id FROM splitter_outputs so "
        "JOIN splitters s ON s.id = so.splitter_id WHERE so.terminal_id = r.tid"
    )
    return f"""
        WITH RECURSIVE reach(tid, depth) AS (
            SELECT DISTINCT unnest(CAST(:starts AS uuid[])), 0
            UNION
            SELECT n.other, r.depth + 1
            FROM reach r
            CROSS JOIN LATERAL (
                SELECT f.terminal_b_id AS other FROM fiber_segments f WHERE f.terminal_a_id = r.tid
                UNION ALL SELECT f.terminal_a_id FROM fiber_segments f WHERE f.terminal_b_id = r.tid
                UNION ALL SELECT c.terminal_b_id FROM connections c
                    WHERE c.is_active AND c.terminal_a_id = r.tid
                UNION ALL SELECT c.terminal_a_id FROM connections c
                    WHERE c.is_active AND c.terminal_b_id = r.tid
                UNION ALL SELECT e.terminal_b_id FROM internal_edges e WHERE e.terminal_a_id = r.tid
                UNION ALL SELECT e.terminal_a_id FROM internal_edges e WHERE e.terminal_b_id = r.tid
                UNION ALL {splitter_edge}
            ) n
            WHERE r.depth < :max_depth
        )
        SELECT DISTINCT tid FROM reach
    """  # noqa: S608 - fragmento fixo (sem entrada do usuário)


def _in(column: Any, ids: list[uuid.UUID]) -> Any:
    return column == any_(bindparam(None, ids, type_=UUID_ARRAY))


def load_trace_graph(
    db: Session,
    start_ids: list[uuid.UUID],
    direction: TraceDirection,
    max_hops: int,
) -> TraceGraph:
    """Carrega o subgrafo alcançável a partir de `start_ids` em ≤ 9 queries (fixas)."""
    graph = TraceGraph()
    if not start_ids:
        return graph

    reach_ids = [
        row[0]
        for row in db.execute(
            text(_reach_sql(direction)).bindparams(
                bindparam("starts", type_=UUID_ARRAY), bindparam("max_depth")
            ),
            {"starts": list(dict.fromkeys(start_ids)), "max_depth": max_hops},
        )
    ]
    if not reach_ids:
        return graph

    # 1) terminais (+ código da estrutura)
    for t_row in db.execute(
        select(
            Terminal.id,
            Terminal.label,
            Terminal.structure_id,
            Structure.code,
            Terminal.entity_type,
            Terminal.entity_id,
        )
        .outerjoin(Structure, Structure.id == Terminal.structure_id)
        .where(_in(Terminal.id, reach_ids))
    ):
        graph.terminals[t_row.id] = TerminalData(
            t_row.id,
            t_row.label,
            t_row.structure_id,
            t_row.code,
            t_row.entity_type,
            t_row.entity_id,
        )

    # 2) segmentos de fibra (+ comprimento do trecho e código do cabo)
    fiber_rows = db.execute(
        select(
            FiberSegment.id,
            FiberSegment.terminal_a_id,
            FiberSegment.terminal_b_id,
            FiberSegment.fiber_number,
            CableSegment.effective_length_m,
            Cable.code,
        )
        .outerjoin(CableSegment, CableSegment.id == FiberSegment.cable_segment_id)
        .outerjoin(Cable, Cable.id == CableSegment.cable_id)
        .where(
            _in(FiberSegment.terminal_a_id, reach_ids) | _in(FiberSegment.terminal_b_id, reach_ids)
        )
        .order_by(FiberSegment.created_at, FiberSegment.id)
    )
    for row in fiber_rows:
        edge = FiberEdge(
            row.id,
            row.terminal_a_id,
            row.terminal_b_id,
            row.fiber_number,
            row.effective_length_m,
            row.code,
        )
        _link(graph.fibers, edge.a, edge.b, edge)

    # 3) conexões externas ativas
    for c_row in db.execute(
        select(
            Connection.id,
            Connection.terminal_a_id,
            Connection.terminal_b_id,
            Connection.connection_type,
            Connection.loss_db,
        )
        .where(
            Connection.is_active.is_(True),
            _in(Connection.terminal_a_id, reach_ids) | _in(Connection.terminal_b_id, reach_ids),
        )
        .order_by(Connection.created_at, Connection.id)
    ):
        conn = ConnectionEdge(
            c_row.id, c_row.terminal_a_id, c_row.terminal_b_id, c_row.connection_type, c_row.loss_db
        )
        _link(graph.connections, conn.a, conn.b, conn)

    # 4) arestas internas (continuidade sem corte)
    for i_row in db.execute(
        select(
            InternalEdge.id,
            InternalEdge.terminal_a_id,
            InternalEdge.terminal_b_id,
            InternalEdge.edge_type,
            InternalEdge.loss_db,
        )
        .where(
            _in(InternalEdge.terminal_a_id, reach_ids) | _in(InternalEdge.terminal_b_id, reach_ids)
        )
        .order_by(InternalEdge.created_at, InternalEdge.id)
    ):
        edge_i = InternalEdgeData(
            i_row.id, i_row.terminal_a_id, i_row.terminal_b_id, i_row.edge_type, i_row.loss_db
        )
        _link(graph.internals, edge_i.a, edge_i.b, edge_i)

    # 5) splitters (só a direção usada)
    key_column = (
        Splitter.input_terminal_id
        if direction == TraceDirection.DOWNSTREAM
        else SplitterOutput.terminal_id
    )
    for s_row in db.execute(
        select(
            Splitter.id,
            Splitter.code,
            Splitter.ratio,
            Splitter.input_terminal_id,
            SplitterOutput.output_number,
            SplitterOutput.terminal_id,
            SplitterOutput.measured_loss_db,
            SplitterOutput.nominal_loss_db,
        )
        .join(SplitterOutput, SplitterOutput.splitter_id == Splitter.id)
        .where(_in(key_column, reach_ids))
        .order_by(Splitter.created_at, Splitter.id, SplitterOutput.output_number)
    ):
        out = SplitterOutputData(
            s_row.id,
            s_row.code,
            s_row.ratio,
            s_row.input_terminal_id,
            s_row.output_number,
            s_row.terminal_id,
            s_row.measured_loss_db if s_row.measured_loss_db is not None else s_row.nominal_loss_db,
        )
        if direction == TraceDirection.DOWNSTREAM:
            graph.splitter_outputs_by_input.setdefault(out.input_terminal_id, []).append(out)
        else:
            graph.splitter_output_by_terminal.setdefault(out.terminal_id, out)

    # 6) portas (+ tipo do dispositivo) dos terminais do tipo porta, para validar pontas
    port_ids = list(
        {t.entity_id for t in graph.terminals.values() if t.entity_type == "port" and t.entity_id}
    )
    if port_ids:
        for p_row in db.execute(
            select(Port.id, Port.role, Port.device_id, Device.kind, Port.name)
            .outerjoin(Device, Device.id == Port.device_id)
            .where(_in(Port.id, port_ids))
        ):
            graph.ports[p_row.id] = PortData(p_row.role, p_row.device_id, p_row.kind)
            graph.port_names[p_row.id] = p_row.name

    # 7) atendimentos ativos nas portas referenciadas por qualquer terminal
    entity_ids = list({t.entity_id for t in graph.terminals.values() if t.entity_id})
    if entity_ids and direction == TraceDirection.DOWNSTREAM:
        graph.active_link_ports = set(
            db.scalars(
                select(ServiceLink.port_id).where(
                    ServiceLink.status == "active", _in(ServiceLink.port_id, entity_ids)
                )
            ).all()
        )
    return graph


def _link(index: dict[uuid.UUID, list[Any]], a: uuid.UUID, b: uuid.UUID, edge: Any) -> None:
    index.setdefault(a, []).append(edge)
    if b != a:
        index.setdefault(b, []).append(edge)


# ------------------------------------------------------------------------------------------
# Travessia em memória
# ------------------------------------------------------------------------------------------


def generate_path_id(origin_id: str, dest_id: str | None, step_ids: list[str]) -> str:
    """ID único determinístico do caminho óptico."""
    raw = f"{origin_id}->{dest_id or 'none'}::" + "->".join(step_ids)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"path_{digest}"


class _Node:
    """Nó da lista encadeada de passos: ramos compartilham o prefixo (sem copiar listas)."""

    __slots__ = ("depth", "parent", "step", "term_id")

    depth: int
    parent: _Node | None
    step: TraceStep | None
    term_id: uuid.UUID

    def __init__(self, term_id: uuid.UUID, parent: _Node | None, step: TraceStep | None) -> None:
        self.term_id = term_id
        self.parent = parent
        self.step = step
        self.depth = 0 if parent is None else parent.depth + 1

    def steps(self) -> list[TraceStep]:
        out: list[TraceStep] = []
        node: _Node | None = self
        while node is not None and node.step is not None:
            out.append(node.step)
            node = node.parent
        out.reverse()
        return out

    def visited(self, term_id: uuid.UUID) -> bool:
        node: _Node | None = self
        while node is not None:
            if node.term_id == term_id:
                return True
            node = node.parent
        return False


def _is_endpoint_valid(graph: TraceGraph, term: TerminalData, direction: TraceDirection) -> bool:
    if term.entity_type == "port" and term.entity_id:
        port = graph.ports.get(term.entity_id)
        if port:
            if direction == TraceDirection.DOWNSTREAM:
                if port.role in DOWNSTREAM_END_ROLES:
                    return True
                if port.device_id and port.device_kind == "onu":
                    return True
            else:
                if port.role in UPSTREAM_END_ROLES:
                    return True
                if port.device_id and port.device_kind in ("olt", "switch"):
                    return True

    return (
        direction == TraceDirection.DOWNSTREAM
        and term.entity_id is not None
        and term.entity_id in graph.active_link_ports
    )


def run_trace(
    graph: TraceGraph,
    start_uuid: uuid.UUID,
    direction: TraceDirection,
    max_results: int,
    max_hops: int,
    topology_revision: int,
) -> TraceResponse:
    """Travessia determinística (BFS com bifurcação em splitters) sobre o grafo já carregado."""
    paths: list[TracePath] = []
    warnings: list[str] = []
    unresolved_terminals: list[str] = []
    has_cycle = has_ambiguity = limit_exceeded = any_incomplete = False

    def make_path(node: _Node, dest_id: uuid.UUID) -> TracePath:
        steps = node.steps()
        total_len = steps[-1].accumulated_length_m if steps else 0.0
        total_loss = steps[-1].accumulated_loss_db if steps else 0.0
        return TracePath(
            path_id=generate_path_id(str(start_uuid), str(dest_id), [s.element_id for s in steps]),
            origin_terminal_id=str(start_uuid),
            destination_terminal_id=str(dest_id),
            total_length_m=total_len,
            total_loss_db=total_loss,
            steps=steps,
        )

    queue: deque[tuple[uuid.UUID, _Node, tuple[str, uuid.UUID] | None]] = deque()
    queue.append((start_uuid, _Node(start_uuid, None, None), None))

    while queue:
        if len(paths) >= max_results:
            limit_exceeded = True
            warnings.append(
                f"Limite máximo de {max_results} caminhos atingido durante o rastreamento."
            )
            break

        current_term_id, node, last_elem = queue.popleft()

        if node.depth >= max_hops:
            limit_exceeded = True
            warnings.append(
                f"Limite máximo de {max_hops} saltos ópticos atingido durante o rastreamento."
            )
            paths.append(make_path(node, current_term_id))
            continue

        current_term = graph.terminals.get(current_term_id)
        if current_term is None:
            unresolved_terminals.append(str(current_term_id))
            any_incomplete = True
            continue

        last_step = node.step
        acc_len = last_step.accumulated_length_m if last_step else 0.0
        acc_loss = last_step.accumulated_loss_db if last_step else 0.0
        location_code = current_term.structure_code
        step_num = node.depth + 1

        transitions: list[tuple[uuid.UUID, TraceStep, tuple[str, uuid.UUID]]] = []

        # 1. Segmentos de fibra em cabo
        for fseg in graph.fibers.get(current_term_id, []):
            if last_elem == ("fiber_segment", fseg.id):
                continue
            next_id = fseg.b if fseg.a == current_term_id else fseg.a
            seg_len = fseg.segment_length_m if fseg.segment_length_m is not None else 0.0
            seg_loss = round((seg_len / 1000.0) * 0.25, 4)
            step = TraceStep(
                step_number=step_num,
                element_type="fiber_segment",
                element_id=str(fseg.id),
                element_code=f"{fseg.cable_code or 'CABO'} - FO #{fseg.fiber_number}",
                input_terminal_id=str(current_term_id),
                output_terminal_id=str(next_id),
                length_m=round(seg_len, 2),
                loss_db=seg_loss,
                accumulated_length_m=round(acc_len + seg_len, 2),
                accumulated_loss_db=round(acc_loss + seg_loss, 4),
                location_code=location_code,
            )
            transitions.append((next_id, step, ("fiber_segment", fseg.id)))

        # 2. Conexões externas (fusão / patch cord / drop)
        conn_count = 0
        for conn in graph.connections.get(current_term_id, []):
            if last_elem == ("connection", conn.id):
                continue
            next_id = conn.b if conn.a == current_term_id else conn.a
            step = TraceStep(
                step_number=step_num,
                element_type=conn.connection_type,
                element_id=str(conn.id),
                element_code=f"{conn.connection_type.upper()}",
                input_terminal_id=str(current_term_id),
                output_terminal_id=str(next_id),
                length_m=0.0,
                loss_db=conn.loss_db,
                accumulated_length_m=round(acc_len, 2),
                accumulated_loss_db=round(acc_loss + conn.loss_db, 4),
                location_code=location_code,
            )
            transitions.append((next_id, step, ("connection", conn.id)))
            conn_count += 1

        if conn_count > 1:
            has_ambiguity = True
            warnings.append(
                f"Ambiguidade detectada: Terminal '{current_term.label}' possui {conn_count} conexões simultâneas."
            )

        # 3. Arestas internas (continuidade sem corte)
        for edge in graph.internals.get(current_term_id, []):
            if last_elem == ("internal_edge", edge.id):
                continue
            next_id = edge.b if edge.a == current_term_id else edge.a
            step = TraceStep(
                step_number=step_num,
                element_type=edge.edge_type,
                element_id=str(edge.id),
                element_code=f"Passagem interna ({edge.edge_type})",
                input_terminal_id=str(current_term_id),
                output_terminal_id=str(next_id),
                length_m=0.0,
                loss_db=edge.loss_db,
                accumulated_length_m=round(acc_len, 2),
                accumulated_loss_db=round(acc_loss + edge.loss_db, 4),
                location_code=location_code,
            )
            transitions.append((next_id, step, ("internal_edge", edge.id)))

        # 4. Splitter passivo (regra semântica downstream / upstream)
        if direction == TraceDirection.DOWNSTREAM:
            for out in graph.splitter_outputs_by_input.get(current_term_id, []):
                step = TraceStep(
                    step_number=step_num,
                    element_type="splitter",
                    element_id=str(out.splitter_id),
                    element_code=f"{out.splitter_code} ({out.ratio}) S#{out.output_number}",
                    input_terminal_id=str(current_term_id),
                    output_terminal_id=str(out.terminal_id),
                    length_m=0.0,
                    loss_db=out.loss_db,
                    accumulated_length_m=round(acc_len, 2),
                    accumulated_loss_db=round(acc_loss + out.loss_db, 4),
                    location_code=location_code,
                )
                transitions.append((out.terminal_id, step, ("splitter", out.splitter_id)))
        else:
            up = graph.splitter_output_by_terminal.get(current_term_id)
            if up is not None:
                step = TraceStep(
                    step_number=step_num,
                    element_type="splitter",
                    element_id=str(up.splitter_id),
                    element_code=f"{up.splitter_code} ({up.ratio}) Entrada",
                    input_terminal_id=str(current_term_id),
                    output_terminal_id=str(up.input_terminal_id),
                    length_m=0.0,
                    loss_db=up.loss_db,
                    accumulated_length_m=round(acc_len, 2),
                    accumulated_loss_db=round(acc_loss + up.loss_db, 4),
                    location_code=location_code,
                )
                transitions.append((up.input_terminal_id, step, ("splitter", up.splitter_id)))

        if not transitions:
            # Nenhum elemento a seguir: o caminho terminou
            if not _is_endpoint_valid(graph, current_term, direction):
                unresolved_terminals.append(str(current_term_id))
                warnings.append(
                    f"Ponta aberta detectada: Terminal '{current_term.label}' ({current_term_id}) não possui continuidade óptica."
                )
                any_incomplete = True
            paths.append(make_path(node, current_term_id))
            continue

        for next_id, next_step, elem_meta in transitions:
            if node.visited(next_id):
                has_cycle = True
                cycle_term = graph.terminals.get(next_id)
                label_cycle = cycle_term.label if cycle_term else str(next_id)
                warnings.append(
                    f"Ciclo óptico detectado: O terminal '{label_cycle}' já foi visitado neste caminho óptico."
                )
                total_len = round(acc_len + next_step.length_m, 2)
                total_loss = round(acc_loss + next_step.loss_db, 4)
                cycle_steps = [*node.steps(), next_step]
                paths.append(
                    TracePath(
                        path_id=generate_path_id(
                            str(start_uuid), str(next_id), [s.element_id for s in cycle_steps]
                        ),
                        origin_terminal_id=str(start_uuid),
                        destination_terminal_id=str(next_id),
                        total_length_m=total_len,
                        total_loss_db=total_loss,
                        steps=cycle_steps,
                    )
                )
                continue

            queue.append((next_id, _Node(next_id, node, next_step), elem_meta))

    if has_cycle:
        trace_status = TraceStatus.CYCLE_DETECTED
    elif limit_exceeded:
        trace_status = TraceStatus.LIMIT_EXCEEDED
    elif has_ambiguity:
        trace_status = TraceStatus.AMBIGUOUS
    elif any_incomplete or not paths:
        trace_status = TraceStatus.INCOMPLETE
    else:
        trace_status = TraceStatus.COMPLETE

    return TraceResponse(
        topology_revision=topology_revision,
        status=trace_status,
        paths=paths,
        warnings=warnings,
        unresolved_terminals=unresolved_terminals,
    )


def effective_max_hops(request_max_hops: int, configured_max: int) -> int:
    """Aplica o teto global de saltos (MAX_TRACE_HOPS)."""
    return min(request_max_hops, configured_max)


__all__ = [
    "TraceGraph",
    "TraceRequest",
    "effective_max_hops",
    "generate_path_id",
    "load_trace_graph",
    "run_trace",
]
