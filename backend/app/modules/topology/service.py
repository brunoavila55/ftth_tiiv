import hashlib
import uuid
from collections import deque

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.cables.models import FiberSegment
from app.modules.connectivity.models import (
    Connection,
    InternalEdge,
    Splitter,
    SplitterOutput,
    Terminal,
)
from app.modules.customers.models import ServiceLink
from app.modules.inventory.models import Device, Port, Structure
from app.modules.topology.models import NetworkTopologyState
from app.schemas.topology import (
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
    queue: deque[tuple[uuid.UUID, list[TraceStep], list[uuid.UUID], tuple[str, uuid.UUID] | None]] = deque()
    queue.append((start_uuid, [], [start_uuid], None))

    while queue:
        if len(paths) >= request.max_results:
            limit_exceeded = True
            warnings.append(
                f"Limite máximo de {request.max_results} caminhos atingido durante o rastreamento."
            )
            break

        current_term_id, current_steps, visited_terms, last_elem = queue.popleft()
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
            select(FiberSegment).where(
                or_(
                    FiberSegment.terminal_a_id == current_term_id,
                    FiberSegment.terminal_b_id == current_term_id,
                )
            )
        ).all()

        for fseg in fiber_segs:
            if last_elem and last_elem == ("fiber_segment", fseg.id):
                continue  # Não volta pelo mesmo segmento de fibra

            next_term_id = fseg.terminal_b_id if fseg.terminal_a_id == current_term_id else fseg.terminal_a_id
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

            next_term_id = conn.terminal_b_id if conn.terminal_a_id == current_term_id else conn.terminal_a_id
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

            next_term_id = edge.terminal_b_id if edge.terminal_a_id == current_term_id else edge.terminal_a_id
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
                select(Splitter).where(Splitter.input_terminal_id == current_term_id)
            ).all()

            for spl in splitters_input:
                outputs = sorted(spl.outputs, key=lambda o: o.output_number)
                for out in outputs:
                    spl_loss = out.measured_loss_db if out.measured_loss_db is not None else out.nominal_loss_db
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
                select(SplitterOutput).where(SplitterOutput.terminal_id == current_term_id)
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
