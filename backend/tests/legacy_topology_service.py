"""ORÁCULO (R14): cópia literal da implementação de trace/impacto anterior à otimização.

Usada só pelos testes de caracterização para provar que a nova travessia em memória devolve
exatamente os mesmos resultados. NÃO importar em código de produção."""

import hashlib
import uuid
from collections import deque

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.errors import NotFoundError, TopologyRevisionConflictError
from app.modules.cables.models import CableSegment, FiberSegment
from app.modules.connectivity.models import (
    Connection,
    InternalEdge,
    Splitter,
    SplitterOutput,
    Terminal,
)
from app.modules.customers.models import Customer, ServiceLink
from app.modules.inventory.models import Device, Port, Structure
from app.modules.topology.models import NetworkTopologyState
from app.schemas.topology import (
    ImpactAnalysisRequest,
    ImpactAnalysisResponse,
    ImpactedCustomerItem,
    TraceDirection,
    TracePath,
    TraceRequest,
    TraceResponse,
    TraceStatus,
    TraceStep,
)


def get_current_topology_revision(db: Session) -> int:
    """Retorna a revisão monotônica atual da topologia."""
    state = db.get(NetworkTopologyState, 1)
    if not state:
        return 1
    return state.topology_revision


def _generate_path_id(origin_id: str, dest_id: str | None, step_ids: list[str]) -> str:
    """Gera um ID único determinístico para o caminho óptico."""
    raw = f"{origin_id}->{dest_id or 'none'}::" + "->".join(step_ids)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"path_{digest}"


def _is_terminal_valid_endpoint(
    db: Session,
    terminal: Terminal,
    direction: TraceDirection,
) -> bool:
    """Verifica se o terminal é um ponto final válido de término de sinal."""
    # 1. Terminal de porta
    if terminal.entity_type == "port" and terminal.entity_id:
        port = db.get(Port, terminal.entity_id)
        if port:
            if direction == TraceDirection.DOWNSTREAM:
                # Downstream termina em drop de cliente ou porta de dispositivo ONU
                if port.role in ("customer_drop", "onu_port", "drop"):
                    return True
                if port.device_id:
                    dev = db.get(Device, port.device_id)
                    if dev and dev.kind == "onu":
                        return True
            else:
                # Upstream termina em porta de OLT (PON)
                if port.role in ("pon", "olt_pon", "trunk"):
                    return True
                if port.device_id:
                    dev = db.get(Device, port.device_id)
                    if dev and dev.kind in ("olt", "switch"):
                        return True

    # 2. Terminal associado a atendimento ativo de cliente (ServiceLink)
    if direction == TraceDirection.DOWNSTREAM and terminal.entity_id:
        active_link = db.scalar(
            select(ServiceLink).where(
                ServiceLink.port_id == terminal.entity_id,
                ServiceLink.status == "active",
            )
        )
        if active_link:
            return True

    return False


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
    """
    start_uuid = uuid.UUID(request.start_terminal_id)
    start_terminal = db.get(Terminal, start_uuid)
    if not start_terminal:
        raise NotFoundError(f"Terminal óptico {request.start_terminal_id} não encontrado.")

    current_revision = get_current_topology_revision(db)

    paths: list[TracePath] = []
    warnings: list[str] = []
    unresolved_terminals: list[str] = []

    has_cycle = False
    has_ambiguity = False
    limit_exceeded = False
    any_incomplete = False

    # Estrutura de exploração em fila (BFS determinístico com bifurcação em splitters)
    # Cada item na fila representa o estado de exploração de um ramo do caminho óptico:
    # (current_terminal_id, steps_so_far, visited_terminal_ids, last_element_tuple)
    # last_element_tuple: (element_type, element_id) para evitar voltar pela mesma fibra/conexão
    queue: deque[
        tuple[uuid.UUID, list[TraceStep], list[uuid.UUID], tuple[str, uuid.UUID] | None]
    ] = deque()
    queue.append((start_uuid, [], [start_uuid], None))

    while queue:
        if len(paths) >= request.max_results:
            limit_exceeded = True
            warnings.append(
                f"Limite máximo de {request.max_results} caminhos atingido durante o rastreamento."
            )
            break

        current_term_id, current_steps, visited_terms, last_elem = queue.popleft()

        if len(current_steps) >= request.max_hops:
            limit_exceeded = True
            warnings.append(
                f"Limite máximo de {request.max_hops} saltos ópticos atingido durante o rastreamento."
            )
            total_len = current_steps[-1].accumulated_length_m if current_steps else 0.0
            total_loss = current_steps[-1].accumulated_loss_db if current_steps else 0.0
            step_ids = [s.element_id for s in current_steps]
            path_id = _generate_path_id(str(start_uuid), str(current_term_id), step_ids)
            paths.append(
                TracePath(
                    path_id=path_id,
                    origin_terminal_id=str(start_uuid),
                    destination_terminal_id=str(current_term_id),
                    total_length_m=total_len,
                    total_loss_db=total_loss,
                    steps=current_steps,
                )
            )
            continue

        current_term = db.get(Terminal, current_term_id)
        if not current_term:
            unresolved_terminals.append(str(current_term_id))
            any_incomplete = True
            continue

        # Calcula valores acumulados até agora
        acc_len = current_steps[-1].accumulated_length_m if current_steps else 0.0
        acc_loss = current_steps[-1].accumulated_loss_db if current_steps else 0.0

        location_code: str | None = None
        if current_term.structure_id:
            struct = db.get(Structure, current_term.structure_id)
            if struct:
                location_code = struct.code

        # ======================================================================
        # 1. TRANSIÇÃO: FIBER SEGMENT (Segmento de Fibra em Cabo)
        # ======================================================================
        fiber_transitions: list[tuple[uuid.UUID, TraceStep, tuple[str, uuid.UUID]]] = []
        fiber_segs = db.scalars(
            select(FiberSegment)
            .options(joinedload(FiberSegment.cable_segment).joinedload(CableSegment.cable))
            .where(
                or_(
                    FiberSegment.terminal_a_id == current_term_id,
                    FiberSegment.terminal_b_id == current_term_id,
                )
            )
        ).all()

        for fseg in fiber_segs:
            if last_elem and last_elem == ("fiber_segment", fseg.id):
                continue  # Não volta pelo mesmo segmento de fibra

            next_term_id = (
                fseg.terminal_b_id if fseg.terminal_a_id == current_term_id else fseg.terminal_a_id
            )
            cseg = fseg.cable_segment
            seg_len = cseg.effective_length_m if cseg else 0.0
            # Atenuação padrão monomodo ~0.25 dB/km em 1310/1490/1550 nm
            seg_loss = round((seg_len / 1000.0) * 0.25, 4)

            step_num = len(current_steps) + 1
            step = TraceStep(
                step_number=step_num,
                element_type="fiber_segment",
                element_id=str(fseg.id),
                element_code=f"{cseg.cable.code if cseg and cseg.cable else 'CABO'} - FO #{fseg.fiber_number}",
                input_terminal_id=str(current_term_id),
                output_terminal_id=str(next_term_id),
                length_m=round(seg_len, 2),
                loss_db=seg_loss,
                accumulated_length_m=round(acc_len + seg_len, 2),
                accumulated_loss_db=round(acc_loss + seg_loss, 4),
                location_code=location_code,
            )
            fiber_transitions.append((next_term_id, step, ("fiber_segment", fseg.id)))

        # ======================================================================
        # 2. TRANSIÇÃO: CONEXÃO EXTERNA (Fusão / Patch Cord / Drop)
        # ======================================================================
        conn_transitions: list[tuple[uuid.UUID, TraceStep, tuple[str, uuid.UUID]]] = []
        connections = db.scalars(
            select(Connection).where(
                Connection.is_active.is_(True),
                or_(
                    Connection.terminal_a_id == current_term_id,
                    Connection.terminal_b_id == current_term_id,
                ),
            )
        ).all()

        for conn in connections:
            if last_elem and last_elem == ("connection", conn.id):
                continue

            next_term_id = (
                conn.terminal_b_id if conn.terminal_a_id == current_term_id else conn.terminal_a_id
            )
            step_num = len(current_steps) + 1
            step = TraceStep(
                step_number=step_num,
                element_type=conn.connection_type,
                element_id=str(conn.id),
                element_code=f"{conn.connection_type.upper()}",
                input_terminal_id=str(current_term_id),
                output_terminal_id=str(next_term_id),
                length_m=0.0,
                loss_db=conn.loss_db,
                accumulated_length_m=round(acc_len, 2),
                accumulated_loss_db=round(acc_loss + conn.loss_db, 4),
                location_code=location_code,
            )
            conn_transitions.append((next_term_id, step, ("connection", conn.id)))

        # Se houver mais de uma conexão ativa concorrente no mesmo terminal -> Ambíguo!
        if len(conn_transitions) > 1:
            has_ambiguity = True
            warnings.append(
                f"Ambiguidade detectada: Terminal '{current_term.label}' possui {len(conn_transitions)} conexões simultâneas."
            )

        # ======================================================================
        # 3. TRANSIÇÃO: ARESTA INTERNA (Continuidade sem corte / Pass-through)
        # ======================================================================
        internal_transitions: list[tuple[uuid.UUID, TraceStep, tuple[str, uuid.UUID]]] = []
        internal_edges = db.scalars(
            select(InternalEdge).where(
                or_(
                    InternalEdge.terminal_a_id == current_term_id,
                    InternalEdge.terminal_b_id == current_term_id,
                )
            )
        ).all()

        for edge in internal_edges:
            if last_elem and last_elem == ("internal_edge", edge.id):
                continue

            next_term_id = (
                edge.terminal_b_id if edge.terminal_a_id == current_term_id else edge.terminal_a_id
            )
            step_num = len(current_steps) + 1
            step = TraceStep(
                step_number=step_num,
                element_type=edge.edge_type,
                element_id=str(edge.id),
                element_code=f"Passagem interna ({edge.edge_type})",
                input_terminal_id=str(current_term_id),
                output_terminal_id=str(next_term_id),
                length_m=0.0,
                loss_db=edge.loss_db,
                accumulated_length_m=round(acc_len, 2),
                accumulated_loss_db=round(acc_loss + edge.loss_db, 4),
                location_code=location_code,
            )
            internal_transitions.append((next_term_id, step, ("internal_edge", edge.id)))

        # ======================================================================
        # 4. TRANSIÇÃO: SPLITTER PASSIVO (Regra Semântica Downstream / Upstream)
        # ======================================================================
        splitter_transitions: list[tuple[uuid.UUID, TraceStep, tuple[str, uuid.UUID]]] = []

        if request.direction == TraceDirection.DOWNSTREAM:
            # DOWNSTREAM: Se o terminal atual é a ENTRADA do splitter, ramifica para TODAS as saídas
            splitters_input = db.scalars(
                select(Splitter)
                .options(selectinload(Splitter.outputs))
                .where(Splitter.input_terminal_id == current_term_id)
            ).all()

            for spl in splitters_input:
                outputs = sorted(spl.outputs, key=lambda o: o.output_number)
                for out in outputs:
                    spl_loss = (
                        out.measured_loss_db
                        if out.measured_loss_db is not None
                        else out.nominal_loss_db
                    )
                    step_num = len(current_steps) + 1
                    step = TraceStep(
                        step_number=step_num,
                        element_type="splitter",
                        element_id=str(spl.id),
                        element_code=f"{spl.code} ({spl.ratio}) S#{out.output_number}",
                        input_terminal_id=str(current_term_id),
                        output_terminal_id=str(out.terminal_id),
                        length_m=0.0,
                        loss_db=spl_loss,
                        accumulated_length_m=round(acc_len, 2),
                        accumulated_loss_db=round(acc_loss + spl_loss, 4),
                        location_code=location_code,
                    )
                    splitter_transitions.append((out.terminal_id, step, ("splitter", spl.id)))

        else:
            # UPSTREAM: Se o terminal atual é uma SAÍDA do splitter, converge EXCLUSIVAMENTE para a entrada
            spl_output = db.scalar(
                select(SplitterOutput)
                .options(joinedload(SplitterOutput.splitter))
                .where(SplitterOutput.terminal_id == current_term_id)
            )
            if spl_output and spl_output.splitter:
                spl = spl_output.splitter
                spl_loss = (
                    spl_output.measured_loss_db
                    if spl_output.measured_loss_db is not None
                    else spl_output.nominal_loss_db
                )
                step_num = len(current_steps) + 1
                step = TraceStep(
                    step_number=step_num,
                    element_type="splitter",
                    element_id=str(spl.id),
                    element_code=f"{spl.code} ({spl.ratio}) Entrada",
                    input_terminal_id=str(current_term_id),
                    output_terminal_id=str(spl.input_terminal_id),
                    length_m=0.0,
                    loss_db=spl_loss,
                    accumulated_length_m=round(acc_len, 2),
                    accumulated_loss_db=round(acc_loss + spl_loss, 4),
                    location_code=location_code,
                )
                splitter_transitions.append((spl.input_terminal_id, step, ("splitter", spl.id)))

        # ======================================================================
        # CONSOLIDAÇÃO DE TRANSIÇÕES DISPONÍVEIS
        # ======================================================================
        all_transitions = (
            fiber_transitions + conn_transitions + internal_transitions + splitter_transitions
        )

        if not all_transitions:
            # Nenhum elemento a seguir: Caminho atingiu o final!
            is_endpoint_valid = _is_terminal_valid_endpoint(db, current_term, request.direction)
            if not is_endpoint_valid:
                unresolved_terminals.append(str(current_term_id))
                warnings.append(
                    f"Ponta aberta detectada: Terminal '{current_term.label}' ({current_term_id}) não possui continuidade óptica."
                )
                any_incomplete = True

            total_len = current_steps[-1].accumulated_length_m if current_steps else 0.0
            total_loss = current_steps[-1].accumulated_loss_db if current_steps else 0.0
            step_ids = [s.element_id for s in current_steps]
            path_id = _generate_path_id(str(start_uuid), str(current_term_id), step_ids)

            path = TracePath(
                path_id=path_id,
                origin_terminal_id=str(start_uuid),
                destination_terminal_id=str(current_term_id),
                total_length_m=total_len,
                total_loss_db=total_loss,
                steps=current_steps,
            )
            paths.append(path)
            continue

        # Continua a propagação para os próximos terminais
        for next_id, next_step, elem_meta in all_transitions:
            if next_id in visited_terms:
                # Ciclo inválido detectado no grafo!
                has_cycle = True
                term_cycle = db.get(Terminal, next_id)
                label_cycle = term_cycle.label if term_cycle else str(next_id)
                warnings.append(
                    f"Ciclo óptico detectado: O terminal '{label_cycle}' já foi visitado neste caminho óptico."
                )

                # Registra o caminho truncado até a detecção do ciclo
                total_len = round(acc_len + next_step.length_m, 2)
                total_loss = round(acc_loss + next_step.loss_db, 4)
                cycle_steps = current_steps + [next_step]
                step_ids = [s.element_id for s in cycle_steps]
                path_id = _generate_path_id(str(start_uuid), str(next_id), step_ids)

                paths.append(
                    TracePath(
                        path_id=path_id,
                        origin_terminal_id=str(start_uuid),
                        destination_terminal_id=str(next_id),
                        total_length_m=total_len,
                        total_loss_db=total_loss,
                        steps=cycle_steps,
                    )
                )
                continue

            # Avança o ramo na fila com histórico atualizado
            new_steps = current_steps + [next_step]
            new_visited = visited_terms + [next_id]
            queue.append((next_id, new_steps, new_visited, elem_meta))

    # Determinação do status de integridade da travessia (prioridade estrita)
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
        topology_revision=current_revision,
        status=trace_status,
        paths=paths,
        warnings=warnings,
        unresolved_terminals=unresolved_terminals,
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
    - Executa travessia óptica reversa (upstream) a partir do terminal de cada cliente ativo
      para determinar se o enlace óptico atravessava algum dos segmentos rompidos.
    - Retorna a contagem e lista detalhada de clientes impactados, clientes não afetados em outros ramos,
      clientes previamente desconectados e clientes com topologia indeterminada.
    - Retorna os códigos das CTOs e das portas PON atingidas pelo evento.
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

    # Coleta todas as fibras pertencentes aos segmentos rompidos
    broken_fiber_segments = db.scalars(
        select(FiberSegment).where(FiberSegment.cable_segment_id.in_(broken_uuids))
    ).all()
    broken_fseg_ids = {str(f.id) for f in broken_fiber_segments}

    # Estruturas CTO diretamente ligadas aos trechos rompidos
    impacted_ctos_set: set[str] = set()
    for seg in existing_segments:
        if seg.origin_structure and seg.origin_structure.kind == "cto":
            impacted_ctos_set.add(seg.origin_structure.code)
        if seg.destination_structure and seg.destination_structure.kind == "cto":
            impacted_ctos_set.add(seg.destination_structure.code)

    impacted_pon_ports_set: set[str] = set()
    impacted_customers: list[ImpactedCustomerItem] = []
    unaffected_customers_count = 0
    previously_disconnected_count = 0
    unknown_status_count = 0

    # Analisa todos os clientes e vínculos de atendimento
    all_customers = db.scalars(
        select(Customer).options(
            selectinload(Customer.service_links).joinedload(ServiceLink.onu_device),
            selectinload(Customer.service_links)
            .joinedload(ServiceLink.port)
            .joinedload(Port.structure),
        )
    ).all()

    for cust in all_customers:
        active_links = [link for link in cust.service_links if link.status == "active"]
        if not active_links:
            # Cliente sem vínculo ativo: já estava desconectado antes do evento
            previously_disconnected_count += 1
            continue

        for link in active_links:
            cto_code = "UNKNOWN"
            if link.port:
                if link.port.structure:
                    cto_code = link.port.structure.code
                elif link.port.device_id:
                    dev = db.get(Device, link.port.device_id)
                    if dev and dev.structure_id:
                        st = db.get(Structure, dev.structure_id)
                        if st:
                            cto_code = st.code

            onu_code = link.onu_device.code if link.onu_device else "UNKNOWN"

            # Localiza o terminal óptico de início para travessia upstream (terminal na ONU ou na porta CTO)
            term_rx: Terminal | None = None
            if link.onu_device_id:
                onu_ports = db.scalars(
                    select(Port.id).where(Port.device_id == link.onu_device_id)
                ).all()
                if onu_ports:
                    term_rx = db.scalar(
                        select(Terminal).where(
                            Terminal.entity_type == "port",
                            Terminal.entity_id.in_(onu_ports),
                        )
                    )
            if not term_rx and link.port_id:
                term_rx = db.scalar(
                    select(Terminal).where(
                        Terminal.entity_type == "port",
                        Terminal.entity_id == link.port_id,
                    )
                )

            if not term_rx:
                unknown_status_count += 1
                continue

            # Executa rastreamento upstream a partir do cliente em direção à OLT
            trace_req = TraceRequest(
                start_terminal_id=str(term_rx.id),
                direction=TraceDirection.UPSTREAM,
                max_results=50,
                max_hops=200,
            )
            trace_res = trace_optical_path(db, trace_req)

            if not trace_res.paths:
                unknown_status_count += 1
                continue

            # Verifica se algum passo do caminho passa por um segmento rompido
            is_impacted = False
            for path in trace_res.paths:
                for step in path.steps:
                    if step.element_type == "fiber_segment" and step.element_id in broken_fseg_ids:
                        is_impacted = True
                        break
                if path.destination_terminal_id:
                    try:
                        dest_term = db.get(Terminal, uuid.UUID(path.destination_terminal_id))
                        if dest_term and dest_term.entity_type == "port" and dest_term.entity_id:
                            dest_port = db.get(Port, dest_term.entity_id)
                            if (
                                dest_port
                                and dest_port.role in ("pon", "olt_pon", "trunk")
                                and is_impacted
                            ):
                                impacted_pon_ports_set.add(dest_port.name)
                    except Exception:
                        pass

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
