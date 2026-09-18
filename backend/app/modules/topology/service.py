import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.errors import NotFoundError, TopologyRevisionConflictError
from app.modules.cables.models import CableSegment, FiberSegment
from app.modules.connectivity.models import Terminal
from app.modules.customers.models import Customer, ServiceLink
from app.modules.inventory.models import Device, Port, Structure
from app.modules.topology.graph import (
    TraceGraph,
    effective_max_hops,
    load_trace_graph,
    run_trace,
)
from app.modules.topology.models import NetworkTopologyState
from app.schemas.topology import (
    ImpactAnalysisRequest,
    ImpactAnalysisResponse,
    ImpactedCustomerItem,
    TraceDirection,
    TraceRequest,
    TraceResponse,
)

PON_ROLES = ("pon", "olt_pon", "trunk")


def get_current_topology_revision(db: Session) -> int:
    """Retorna a revisão monotônica atual da topologia."""
    state = db.get(NetworkTopologyState, 1)
    if not state:
        return 1
    return state.topology_revision


def trace_optical_path(
    db: Session,
    request: TraceRequest,
) -> TraceResponse:
    """Executa a travessia determinística e consistente no grafo óptico a partir de um terminal.

    Semântica:
    - Downstream: Sinal parte da OLT em direção aos assinantes/ONUs.
      Em splitters, o sinal entra na porta de entrada e se ramifica deterministicamente
      para todas as saídas (1:N). Saídas irmãs NÃO transitam sinal entre si.
    - Upstream: Sinal parte do assinante/ONU em direção à OLT.
      Em splitters, o sinal entra por uma das saídas e converge EXCLUSIVAMENTE para a entrada.
      Não há transição para saídas irmãs.
    - Continuidade sem corte: Fibras que passam direto por caixas (internal_edges) são preservadas.
    - Detecção de ciclos, pontas abertas, ambiguidades e estouro de limites.

    Desempenho: o subgrafo relevante é carregado em número FIXO de queries (independe de
    `max_hops`) e a travessia roda em memória (ver `modules/topology/graph.py`). O teto de saltos é
    min(max_hops, MAX_TRACE_HOPS).
    """
    start_uuid = uuid.UUID(request.start_terminal_id)
    current_revision = get_current_topology_revision(db)
    max_hops = effective_max_hops(request.max_hops, get_settings().MAX_TRACE_HOPS)

    graph = load_trace_graph(db, [start_uuid], request.direction, max_hops)
    if start_uuid not in graph.terminals:
        raise NotFoundError(f"Terminal óptico {request.start_terminal_id} não encontrado.")

    return run_trace(
        graph,
        start_uuid,
        request.direction,
        max_results=request.max_results,
        max_hops=max_hops,
        topology_revision=current_revision,
    )


def analyze_cable_impact(
    db: Session,
    payload: ImpactAnalysisRequest,
) -> ImpactAnalysisResponse:
    """Simula a remoção virtual de trechos de cabos em um snapshot consistente da rede.

    Semântica:
    - Valida a revisão monotônica esperada com detecção de concorrência otimista (409 Conflict).
    - Valida a existência dos trechos de cabo especificados (404 Not Found caso algum inexista).
    - Identifica todas as fibras ópticas pertencentes aos trechos rompidos.
    - Executa travessia óptica reversa (upstream) a partir do terminal de cada vínculo ativo
      para determinar se o enlace óptico atravessava algum dos segmentos rompidos.
    - Retorna a contagem e lista detalhada de clientes impactados, clientes não afetados em outros ramos,
      clientes previamente desconectados e clientes com topologia indeterminada.
    - Retorna os códigos das CTOs e das portas PON atingidas pelo evento.

    Desempenho: o grafo de TODOS os vínculos ativos é carregado uma única vez (número fixo de
    queries, independente da quantidade de clientes) e cada rastreio upstream roda em memória.
    """
    current_revision = get_current_topology_revision(db)
    if payload.expected_topology_revision != current_revision:
        raise TopologyRevisionConflictError(
            detail=(
                f"A revisão topológica esperada ({payload.expected_topology_revision}) "
                f"diverge da revisão atual ({current_revision}). Atualize os dados antes de prosseguir."
            )
        )

    broken_uuids: set[uuid.UUID] = set()
    for seg_id_str in payload.cable_segment_ids:
        try:
            broken_uuids.add(uuid.UUID(seg_id_str))
        except ValueError:
            raise NotFoundError(
                detail=f"Segmento de cabo com UUID inválido: '{seg_id_str}'"
            ) from None

    existing_segments = db.scalars(
        select(CableSegment)
        .options(
            joinedload(CableSegment.origin_structure),
            joinedload(CableSegment.destination_structure),
        )
        .where(CableSegment.id.in_(broken_uuids))
    ).all()

    found_uuids = {s.id for s in existing_segments}
    missing_uuids = broken_uuids - found_uuids
    if missing_uuids:
        missing_str = ", ".join(str(m) for m in missing_uuids)
        raise NotFoundError(detail=f"Segmento(s) de cabo não encontrado(s): {missing_str}")

    # Fibras pertencentes aos segmentos rompidos
    broken_fseg_ids = {
        str(fid)
        for fid in db.scalars(
            select(FiberSegment.id).where(FiberSegment.cable_segment_id.in_(broken_uuids))
        ).all()
    }

    # Estruturas CTO diretamente ligadas aos trechos rompidos
    impacted_ctos_set: set[str] = set()
    for seg in existing_segments:
        if seg.origin_structure and seg.origin_structure.kind == "cto":
            impacted_ctos_set.add(seg.origin_structure.code)
        if seg.destination_structure and seg.destination_structure.kind == "cto":
            impacted_ctos_set.add(seg.destination_structure.code)

    # Clientes sem vínculo ativo: já estavam desconectados antes do evento
    total_customers, customers_with_active_link = db.execute(
        select(
            select(func.count(Customer.id)).scalar_subquery(),
            select(func.count(func.distinct(ServiceLink.customer_id)))
            .where(ServiceLink.status == "active")
            .scalar_subquery(),
        )
    ).one()
    previously_disconnected_count = int(total_customers) - int(customers_with_active_link)

    # Todos os vínculos ativos (com cliente, ONU, porta e estrutura) numa só query
    links = list(
        db.scalars(
            select(ServiceLink)
            .options(
                joinedload(ServiceLink.customer),
                joinedload(ServiceLink.onu_device),
                joinedload(ServiceLink.port).joinedload(Port.structure),
            )
            .where(ServiceLink.status == "active")
        ).all()
    )
    links.sort(key=lambda link: (link.customer.code, str(link.id)))

    cto_codes = _resolve_cto_codes(db, links)
    start_terminals = _resolve_start_terminals(db, links)

    graph: TraceGraph = load_trace_graph(
        db,
        list({t for t in start_terminals.values() if t is not None}),
        TraceDirection.UPSTREAM,
        effective_max_hops(200, get_settings().MAX_TRACE_HOPS),
    )
    max_hops = effective_max_hops(200, get_settings().MAX_TRACE_HOPS)

    impacted_pon_ports_set: set[str] = set()
    impacted_customers: list[ImpactedCustomerItem] = []
    unaffected_customers_count = 0
    unknown_status_count = 0

    for link in links:
        cust = link.customer
        cto_code = cto_codes[link.id]
        onu_code = link.onu_device.code if link.onu_device else "UNKNOWN"

        term_rx = start_terminals.get(link.id)
        if term_rx is None:
            unknown_status_count += 1
            continue

        trace_res = run_trace(
            graph,
            term_rx,
            TraceDirection.UPSTREAM,
            max_results=50,
            max_hops=max_hops,
            topology_revision=current_revision,
        )
        if not trace_res.paths:
            unknown_status_count += 1
            continue

        # Algum passo do caminho passa por um segmento rompido?
        is_impacted = False
        for path in trace_res.paths:
            for step in path.steps:
                if step.element_type == "fiber_segment" and step.element_id in broken_fseg_ids:
                    is_impacted = True
                    break
            if path.destination_terminal_id and is_impacted:
                dest_term = graph.terminals.get(uuid.UUID(path.destination_terminal_id))
                if dest_term and dest_term.entity_type == "port" and dest_term.entity_id:
                    dest_port = graph.ports.get(dest_term.entity_id)
                    if dest_port and dest_port.role in PON_ROLES:
                        impacted_pon_ports_set.add(graph.port_names.get(dest_term.entity_id, ""))
            if is_impacted:
                break

        if is_impacted:
            impacted_customers.append(
                ImpactedCustomerItem(
                    customer_id=str(cust.id),
                    customer_code=cust.code,
                    service_link_id=str(link.id),
                    onu_device_code=onu_code,
                    cto_code=cto_code,
                )
            )
            if cto_code != "UNKNOWN":
                impacted_ctos_set.add(cto_code)
        else:
            unaffected_customers_count += 1

    return ImpactAnalysisResponse(
        topology_revision=current_revision,
        broken_segments_count=len(existing_segments),
        impacted_customers=impacted_customers,
        unaffected_customers_count=unaffected_customers_count,
        previously_disconnected_count=previously_disconnected_count,
        unknown_status_count=unknown_status_count,
        impacted_ctos=sorted(impacted_ctos_set),
        impacted_pon_ports=sorted(impacted_pon_ports_set),
    )


def _resolve_cto_codes(db: Session, links: list[ServiceLink]) -> dict[uuid.UUID, str]:
    """Código da CTO de cada vínculo: estrutura da porta ou, na falta, a do dispositivo da porta."""
    codes: dict[uuid.UUID, str] = {}
    need_device: dict[uuid.UUID, uuid.UUID] = {}  # link.id -> device_id
    for link in links:
        code = "UNKNOWN"
        if link.port:
            if link.port.structure:
                code = link.port.structure.code
            elif link.port.device_id:
                need_device[link.id] = link.port.device_id
        codes[link.id] = code

    if need_device:
        rows = db.execute(
            select(Device.id, Structure.code)
            .join(Structure, Structure.id == Device.structure_id)
            .where(Device.id.in_(set(need_device.values())))
        ).all()
        by_device: dict[uuid.UUID, str] = {r[0]: r[1] for r in rows}  # noqa: C416
        for link_id, device_id in need_device.items():
            codes[link_id] = by_device.get(device_id, "UNKNOWN")
    return codes


def _resolve_start_terminals(
    db: Session, links: list[ServiceLink]
) -> dict[uuid.UUID, uuid.UUID | None]:
    """Terminal de partida do rastreio upstream de cada vínculo (terminal da ONU, senão da porta)."""
    onu_ids = {link.onu_device_id for link in links if link.onu_device_id}
    onu_ports: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    if onu_ids:
        for port_id, device_id in db.execute(
            select(Port.id, Port.device_id).where(Port.device_id.in_(onu_ids))
        ):
            onu_ports[device_id].append(port_id)

    port_ids = {p for ports in onu_ports.values() for p in ports}
    port_ids |= {link.port_id for link in links if link.port_id}
    terminal_by_port: dict[uuid.UUID, uuid.UUID] = {}
    if port_ids:
        rows = db.execute(
            select(Terminal.entity_id, Terminal.id)
            .where(Terminal.entity_type == "port", Terminal.entity_id.in_(port_ids))
            .order_by(Terminal.created_at, Terminal.id)
        )
        for entity_id, terminal_id in rows:
            terminal_by_port.setdefault(entity_id, terminal_id)

    result: dict[uuid.UUID, uuid.UUID | None] = {}
    for link in links:
        term: uuid.UUID | None = None
        if link.onu_device_id:
            for port_id in onu_ports.get(link.onu_device_id, []):
                if port_id in terminal_by_port:
                    term = terminal_by_port[port_id]
                    break
        if term is None and link.port_id:
            term = terminal_by_port.get(link.port_id)
        result[link.id] = term
    return result
