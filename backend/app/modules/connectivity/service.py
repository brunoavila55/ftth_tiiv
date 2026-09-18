import uuid
from collections.abc import Sequence

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    PreconditionRequiredError,
    TopologyRevisionConflictError,
    UnprocessableEntityError,
    ValidationErrorItem,
)
from app.modules.audit.service import record_audit_event
from app.modules.connectivity.models import (
    Connection,
    ConnectionEndpoint,
    InternalEdge,
    Terminal,
    TerminalReservation,
)
from app.modules.gis.service import bump_topology_revision, get_topology_revision
from app.modules.inventory.models import Structure
from app.schemas.connectivity import (
    BatchOperationType,
    ConnectionBatchRequest,
    ConnectionBatchResponse,
    ConnectionCreate,
    ConnectionRead,
    ConnectionType,
    InternalEdgeRead,
    StructureConnectivityResponse,
    TerminalKind,
    TerminalRead,
    TerminalReservationRead,
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


def terminal_to_read(t: Terminal) -> TerminalRead:
    return TerminalRead(
        id=str(t.id),
        kind=TerminalKind(t.kind),
        entity_id=str(t.entity_id) if t.entity_id else str(t.id),
        entity_type=t.entity_type or "terminal",
        label=t.label,
        is_occupied=t.is_occupied,
    )


def connection_to_read(c: Connection) -> ConnectionRead:
    return ConnectionRead(
        id=str(c.id),
        terminal_a_id=str(c.terminal_a_id),
        terminal_b_id=str(c.terminal_b_id),
        connection_type=ConnectionType(c.connection_type),
        loss_db=c.loss_db,
        structure_id=str(c.structure_id) if c.structure_id else None,
        is_active=c.is_active,
        version=c.version,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def reservation_to_read(r: TerminalReservation) -> TerminalReservationRead:
    return TerminalReservationRead(
        id=str(r.id),
        terminal_id=str(r.terminal_id),
        reason=r.reason,
        reserved_by_id=str(r.reserved_by_id) if r.reserved_by_id else None,
        expires_at=r.expires_at,
        is_active=r.is_active,
        version=r.version,
        created_at=r.created_at,
    )


def internal_edge_to_read(e: InternalEdge) -> InternalEdgeRead:
    return InternalEdgeRead(
        id=str(e.id),
        terminal_a_id=str(e.terminal_a_id),
        terminal_b_id=str(e.terminal_b_id),
        edge_type=e.edge_type,
        entity_type=e.entity_type,
        entity_id=str(e.entity_id),
        loss_db=e.loss_db,
        is_bidirectional=e.is_bidirectional,
    )


def list_connections(
    db: Session,
    *,
    structure_id: uuid.UUID | None = None,
    is_active: bool | None = True,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ConnectionRead], int]:
    """Lista conexões ópticas com filtros e paginação."""
    query = select(Connection)
    if structure_id is not None:
        query = query.where(Connection.structure_id == structure_id)
    if is_active is not None:
        query = query.where(Connection.is_active.is_(is_active))

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()

    offset = (page - 1) * page_size
    items = (
        db.execute(query.order_by(Connection.created_at.desc()).offset(offset).limit(page_size))
        .scalars()
        .all()
    )
    return [connection_to_read(c) for c in items], total


def get_connection_by_id(db: Session, connection_id: uuid.UUID) -> ConnectionRead:
    """Obtém detalhes de uma conexão pelo ID."""
    conn = db.execute(select(Connection).where(Connection.id == connection_id)).scalar_one_or_none()
    if conn is None:
        raise NotFoundError(code="connection_not_found", detail="Conexão óptica não encontrada.")
    return connection_to_read(conn)


def create_connection(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    actor_name: str,
    payload: ConnectionCreate,
    request_id: str | None = None,
) -> ConnectionRead:
    """Cria uma conexão óptica unitária com validações estritas de integridade física."""
    try:
        term_a_uuid = uuid.UUID(payload.terminal_a_id)
        term_b_uuid = uuid.UUID(payload.terminal_b_id)
    except ValueError:
        raise UnprocessableEntityError(detail="UUID de terminal inválido.") from None

    if term_a_uuid == term_b_uuid:
        raise UnprocessableEntityError(
            detail="Uma conexão óptica exige dois terminais distintos.",
            field="terminal_b_id",
            code="identical_terminals",
        )

    struct_uuid: uuid.UUID | None = None
    if payload.structure_id:
        try:
            struct_uuid = uuid.UUID(payload.structure_id)
        except ValueError:
            raise UnprocessableEntityError(detail="UUID de estrutura inválido.") from None

    # Bloqueio determinístico por ordem de UUID para prevenir deadlocks
    sorted_ids = sorted([term_a_uuid, term_b_uuid])
    locked_terms = {
        t.id: t
        for t in db.execute(
            select(Terminal)
            .where(Terminal.id.in_(sorted_ids))
            .order_by(Terminal.id)
            .with_for_update()
        )
        .scalars()
        .all()
    }

    if term_a_uuid not in locked_terms or term_b_uuid not in locked_terms:
        raise NotFoundError(
            code="terminal_not_found",
            detail="Um ou ambos os terminais informados não foram encontrados.",
        )

    term_a = locked_terms[term_a_uuid]
    term_b = locked_terms[term_b_uuid]

    # Validação de localização estrita
    if struct_uuid is not None:
        if term_a.structure_id != struct_uuid or term_b.structure_id != struct_uuid:
            raise ConflictError(
                code="location_mismatch",
                detail=f"Ambos os terminais devem pertencer à estrutura informada ({payload.structure_id}).",
            )
    else:
        # Se structure_id não foi explicitado no payload, valida se ambos pertencem ao mesmo local
        same_structure = (
            term_a.structure_id is not None and term_a.structure_id == term_b.structure_id
        )
        same_site = term_a.site_id is not None and term_a.site_id == term_b.site_id
        if not (same_structure or same_site):
            raise ConflictError(
                code="location_mismatch",
                detail="Os terminais conectados devem estar localizados na mesma estrutura física ou site.",
            )
        struct_uuid = term_a.structure_id

    # Impedir modelo de pass-through de DIO como conexão externa
    if (
        term_a.kind == TerminalKind.PORT_FRONT
        and term_b.kind == TerminalKind.PORT_BACK
        and term_a.entity_id == term_b.entity_id
    ) or (
        term_a.kind == TerminalKind.PORT_BACK
        and term_b.kind == TerminalKind.PORT_FRONT
        and term_a.entity_id == term_b.entity_id
    ):
        raise ConflictError(
            code="internal_edge_conflict",
            detail="A transição frente/trás do DIO é modelada como aresta interna, não como conexão externa.",
        )

    # Checar reserva ativa
    res_a = db.execute(
        select(TerminalReservation).where(
            TerminalReservation.terminal_id == term_a.id,
            TerminalReservation.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if res_a is not None or term_a.occupancy == "reserved":
        raise ConflictError(
            code="terminal_reserved",
            detail=f"O terminal '{term_a.label}' ({term_a.id}) possui uma reserva ativa e exige liberação explícita antes de conectar.",
            errors=[
                ValidationErrorItem(
                    field="terminal_a_id",
                    code="terminal_reserved",
                    message=f"Terminal reservado: {res_a.reason if res_a else 'Reserva ativa'}",
                )
            ],
        )

    res_b = db.execute(
        select(TerminalReservation).where(
            TerminalReservation.terminal_id == term_b.id,
            TerminalReservation.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if res_b is not None or term_b.occupancy == "reserved":
        raise ConflictError(
            code="terminal_reserved",
            detail=f"O terminal '{term_b.label}' ({term_b.id}) possui uma reserva ativa e exige liberação explícita antes de conectar.",
            errors=[
                ValidationErrorItem(
                    field="terminal_b_id",
                    code="terminal_reserved",
                    message=f"Terminal reservado: {res_b.reason if res_b else 'Reserva ativa'}",
                )
            ],
        )

    # Checar ocupação / conexão ativa pré-existente
    if term_a.is_occupied or term_a.occupancy == "connected":
        raise ConflictError(
            code="terminal_already_connected",
            detail=f"O terminal '{term_a.label}' ({term_a.id}) já possui uma conexão ativa.",
            errors=[
                ValidationErrorItem(
                    field="terminal_a_id",
                    code="terminal_already_connected",
                    message="Terminal já possui conexão ativa",
                )
            ],
        )

    if term_b.is_occupied or term_b.occupancy == "connected":
        raise ConflictError(
            code="terminal_already_connected",
            detail=f"O terminal '{term_b.label}' ({term_b.id}) já possui uma conexão ativa.",
            errors=[
                ValidationErrorItem(
                    field="terminal_b_id",
                    code="terminal_already_connected",
                    message="Terminal já possui conexão ativa",
                )
            ],
        )

    conn = Connection(
        terminal_a_id=term_a.id,
        terminal_b_id=term_b.id,
        connection_type=payload.connection_type.value,
        loss_db=payload.loss_db,
        structure_id=struct_uuid,
        site_id=term_a.site_id if term_a.site_id == term_b.site_id else None,
        is_active=True,
        notes=payload.notes,
        version=1,
    )
    db.add(conn)

    try:
        db.flush()
        ep_a = ConnectionEndpoint(connection_id=conn.id, terminal_id=term_a.id, is_active=True)
        ep_b = ConnectionEndpoint(connection_id=conn.id, terminal_id=term_b.id, is_active=True)
        db.add_all([ep_a, ep_b])
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            code="terminal_already_connected",
            detail="Conflito de concorrência: um dos terminais acabou de ser conectado por outra transação.",
        ) from exc

    term_a.is_occupied = True
    term_a.occupancy = "connected"
    term_b.is_occupied = True
    term_b.occupancy = "connected"

    record_audit_event(
        db,
        actor_id=actor_id,
        actor_name=actor_name,
        action="connection_created",
        entity_type="connection",
        entity_id=conn.id,
        changes={
            "terminal_a_id": str(term_a.id),
            "terminal_b_id": str(term_b.id),
            "connection_type": payload.connection_type.value,
            "loss_db": payload.loss_db,
            "structure_id": str(struct_uuid) if struct_uuid else None,
        },
        request_id=request_id,
    )

    bump_topology_revision(db)
    db.commit()
    db.refresh(conn)
    return connection_to_read(conn)


def deactivate_connection(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    actor_name: str,
    connection_id: uuid.UUID,
    if_match: str | None,
    request_id: str | None = None,
) -> None:
    """Desativa suavemente uma conexão óptica (desconexão), liberando os terminais e mantendo histórico."""
    conn = db.execute(
        select(Connection).where(Connection.id == connection_id).with_for_update()
    ).scalar_one_or_none()
    if conn is None or not conn.is_active:
        raise NotFoundError(
            code="connection_not_found",
            detail="Conexão óptica não encontrada ou já inativa.",
        )

    _validate_if_match(if_match, conn.version)

    sorted_ids = sorted([conn.terminal_a_id, conn.terminal_b_id])
    locked_terms = {
        t.id: t
        for t in db.execute(
            select(Terminal)
            .where(Terminal.id.in_(sorted_ids))
            .order_by(Terminal.id)
            .with_for_update()
        )
        .scalars()
        .all()
    }

    conn.is_active = False
    conn.version += 1

    db.execute(
        update(ConnectionEndpoint)
        .where(ConnectionEndpoint.connection_id == conn.id)
        .values(is_active=False)
    )

    for term_id in sorted_ids:
        term = locked_terms.get(term_id)
        if term is not None:
            # Verifica se o terminal ainda tem alguma outra conexão ativa (por segurança)
            active_count = db.execute(
                select(func.count(ConnectionEndpoint.id)).where(
                    ConnectionEndpoint.terminal_id == term.id,
                    ConnectionEndpoint.is_active.is_(True),
                    ConnectionEndpoint.connection_id != conn.id,
                )
            ).scalar_one()
            if active_count == 0:
                term.is_occupied = False
                term.occupancy = "free"

    record_audit_event(
        db,
        actor_id=actor_id,
        actor_name=actor_name,
        action="connection_deactivated",
        entity_type="connection",
        entity_id=conn.id,
        changes={
            "connection_id": str(conn.id),
            "terminal_a_id": str(conn.terminal_a_id),
            "terminal_b_id": str(conn.terminal_b_id),
        },
        request_id=request_id,
    )

    bump_topology_revision(db)
    db.commit()


def execute_batch_connections(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    actor_name: str,
    payload: ConnectionBatchRequest,
    request_id: str | None = None,
) -> ConnectionBatchResponse:
    """Executa um lote atômico de operações de conectividade em uma estrutura (Editor de Fusão)."""
    try:
        struct_id = uuid.UUID(payload.structure_id)
    except ValueError:
        raise UnprocessableEntityError(detail="UUID de estrutura inválido.") from None

    # 1. Bloqueio determinístico da estrutura
    struct = db.execute(
        select(Structure).where(Structure.id == struct_id).with_for_update()
    ).scalar_one_or_none()
    if struct is None:
        raise NotFoundError(
            code="structure_not_found", detail="Estrutura informada não encontrada."
        )

    # 2. Validação da revisão topológica esperada
    current_rev = get_topology_revision(db)
    if payload.expected_topology_revision != current_rev:
        raise TopologyRevisionConflictError(
            detail=(
                f"A revisão topológica esperada ({payload.expected_topology_revision}) "
                f"diverge da revisão atual ({current_rev}). O editor de fusão deve ser recarregado."
            )
        )

    # 3. Coleta e ordenação de todos os terminais envolvidos no lote
    all_term_ids: set[uuid.UUID] = set()
    for idx, op in enumerate(payload.operations):
        try:
            t_a_uuid = uuid.UUID(op.terminal_a_id)
            all_term_ids.add(t_a_uuid)
            if op.terminal_b_id:
                t_b_uuid = uuid.UUID(op.terminal_b_id)
                all_term_ids.add(t_b_uuid)
                if t_a_uuid == t_b_uuid:
                    raise UnprocessableEntityError(
                        detail=f"Operação {idx + 1}: terminal A e B não podem ser o mesmo ({op.terminal_a_id})."
                    )
        except ValueError:
            raise UnprocessableEntityError(
                detail=f"Operação {idx + 1}: UUID de terminal inválido."
            ) from None

    # Bloqueio determinístico de todos os terminais por UUID ascendente
    sorted_term_ids = sorted(all_term_ids)
    locked_terminals = {
        t.id: t
        for t in db.execute(
            select(Terminal)
            .where(Terminal.id.in_(sorted_term_ids))
            .order_by(Terminal.id)
            .with_for_update()
        )
        .scalars()
        .all()
    }

    # Validar se todos os terminais existem
    for t_id in sorted_term_ids:
        if t_id not in locked_terminals:
            raise NotFoundError(
                code="terminal_not_found",
                detail=f"Terminal {t_id} não foi encontrado no banco de dados.",
            )

    # Validar se todos os terminais pertencem à estrutura do lote
    for _t_id, term in locked_terminals.items():
        if term.structure_id != struct_id:
            raise ConflictError(
                code="location_mismatch",
                detail=f"O terminal '{term.label}' ({term.id}) pertence a outra estrutura e não pode ser manipulado nesta caixa.",
            )

    # 4. Executar cada operação em ordem transacional
    for idx, op in enumerate(payload.operations):
        term_a = locked_terminals[uuid.UUID(op.terminal_a_id)]

        if op.action == BatchOperationType.RELEASE:
            # Liberação de reserva
            res = db.execute(
                select(TerminalReservation).where(
                    TerminalReservation.terminal_id == term_a.id,
                    TerminalReservation.is_active.is_(True),
                )
            ).scalar_one_or_none()
            if res is None and term_a.occupancy != "reserved":
                raise ConflictError(
                    code="terminal_not_reserved",
                    detail=f"Operação {idx + 1}: O terminal '{term_a.label}' não possui reserva ativa para liberação.",
                )
            if res is not None:
                res.is_active = False
            term_a.occupancy = "free"
            term_a.is_occupied = False

            record_audit_event(
                db,
                actor_id=actor_id,
                actor_name=actor_name,
                action="reservation_released",
                entity_type="terminal_reservation",
                entity_id=res.id if res else term_a.id,
                changes={"terminal_id": str(term_a.id), "label": term_a.label},
                request_id=request_id,
            )

        elif op.action == BatchOperationType.RESERVE:
            # Reserva de terminal
            if term_a.occupancy == "reserved":
                raise ConflictError(
                    code="terminal_already_reserved",
                    detail=f"Operação {idx + 1}: O terminal '{term_a.label}' já está reservado.",
                )
            if term_a.is_occupied or term_a.occupancy == "connected":
                raise ConflictError(
                    code="terminal_already_connected",
                    detail=f"Operação {idx + 1}: O terminal '{term_a.label}' já está conectado e não pode ser reservado.",
                )

            reservation = TerminalReservation(
                terminal_id=term_a.id,
                reason=op.reservation_reason or "Reserva via editor de fusão",
                reserved_by_id=actor_id,
                is_active=True,
                version=1,
            )
            db.add(reservation)
            db.flush()
            term_a.occupancy = "reserved"

            record_audit_event(
                db,
                actor_id=actor_id,
                actor_name=actor_name,
                action="terminal_reserved",
                entity_type="terminal_reservation",
                entity_id=reservation.id,
                changes={
                    "terminal_id": str(term_a.id),
                    "label": term_a.label,
                    "reason": reservation.reason,
                },
                request_id=request_id,
            )

        elif op.action == BatchOperationType.DISCONNECT:
            # Desconexão de conexão ativa
            ep = db.execute(
                select(ConnectionEndpoint).where(
                    ConnectionEndpoint.terminal_id == term_a.id,
                    ConnectionEndpoint.is_active.is_(True),
                )
            ).scalar_one_or_none()
            if ep is None:
                raise ConflictError(
                    code="connection_not_found",
                    detail=f"Operação {idx + 1}: O terminal '{term_a.label}' não possui conexão ativa para desconectar.",
                )

            conn = db.execute(
                select(Connection).where(Connection.id == ep.connection_id)
            ).scalar_one()

            if op.terminal_b_id:
                target_b_id = uuid.UUID(op.terminal_b_id)
                if target_b_id not in (conn.terminal_a_id, conn.terminal_b_id):
                    raise ConflictError(
                        code="connection_mismatch",
                        detail=f"Operação {idx + 1}: A conexão ativa do terminal A não se conecta ao terminal B especificado.",
                    )

            conn.is_active = False
            conn.version += 1

            db.execute(
                update(ConnectionEndpoint)
                .where(ConnectionEndpoint.connection_id == conn.id)
                .values(is_active=False)
            )

            # Liberar ambos os terminais da conexão
            other_id = conn.terminal_b_id if conn.terminal_a_id == term_a.id else conn.terminal_a_id
            term_a.is_occupied = False
            term_a.occupancy = "free"

            other_term = locked_terminals.get(other_id)
            if other_term is not None:
                other_term.is_occupied = False
                other_term.occupancy = "free"

            record_audit_event(
                db,
                actor_id=actor_id,
                actor_name=actor_name,
                action="connection_deactivated",
                entity_type="connection",
                entity_id=conn.id,
                changes={
                    "connection_id": str(conn.id),
                    "terminal_a_id": str(conn.terminal_a_id),
                    "terminal_b_id": str(conn.terminal_b_id),
                },
                request_id=request_id,
            )

        elif op.action == BatchOperationType.CONNECT:
            if not op.terminal_b_id:
                raise UnprocessableEntityError(
                    detail=f"Operação {idx + 1}: Operação 'connect' exige 'terminal_b_id'."
                )

            term_b = locked_terminals[uuid.UUID(op.terminal_b_id)]

            # Checar reserva ativa
            if term_a.occupancy == "reserved":
                raise ConflictError(
                    code="terminal_reserved",
                    detail=f"Operação {idx + 1}: O terminal '{term_a.label}' possui reserva ativa e exige liberação explícita antes de conectar.",
                )
            if term_b.occupancy == "reserved":
                raise ConflictError(
                    code="terminal_reserved",
                    detail=f"Operação {idx + 1}: O terminal '{term_b.label}' possui reserva ativa e exige liberação explícita antes de conectar.",
                )

            # Checar ocupação
            if term_a.is_occupied or term_a.occupancy == "connected":
                raise ConflictError(
                    code="terminal_already_connected",
                    detail=f"Operação {idx + 1}: O terminal '{term_a.label}' já está conectado.",
                )
            if term_b.is_occupied or term_b.occupancy == "connected":
                raise ConflictError(
                    code="terminal_already_connected",
                    detail=f"Operação {idx + 1}: O terminal '{term_b.label}' já está conectado.",
                )

            # DIO pass-through check
            if (
                term_a.kind == TerminalKind.PORT_FRONT
                and term_b.kind == TerminalKind.PORT_BACK
                and term_a.entity_id == term_b.entity_id
            ) or (
                term_a.kind == TerminalKind.PORT_BACK
                and term_b.kind == TerminalKind.PORT_FRONT
                and term_a.entity_id == term_b.entity_id
            ):
                raise ConflictError(
                    code="internal_edge_conflict",
                    detail=f"Operação {idx + 1}: Transição frente/trás de DIO é aresta interna, não conexão externa.",
                )

            conn_type = (
                op.connection_type.value
                if op.connection_type
                else ConnectionType.FUSION_SPLICE.value
            )
            loss_db = op.loss_db if op.loss_db is not None else 0.10

            new_conn = Connection(
                terminal_a_id=term_a.id,
                terminal_b_id=term_b.id,
                connection_type=conn_type,
                loss_db=loss_db,
                structure_id=struct_id,
                is_active=True,
                version=1,
            )
            db.add(new_conn)

            try:
                db.flush()
                ep_a = ConnectionEndpoint(
                    connection_id=new_conn.id, terminal_id=term_a.id, is_active=True
                )
                ep_b = ConnectionEndpoint(
                    connection_id=new_conn.id, terminal_id=term_b.id, is_active=True
                )
                db.add_all([ep_a, ep_b])
                db.flush()
            except IntegrityError as exc:
                db.rollback()
                raise ConflictError(
                    code="terminal_already_connected",
                    detail=f"Operação {idx + 1}: Um dos terminais já foi ocupado simultaneamente por outra transação.",
                ) from exc

            term_a.is_occupied = True
            term_a.occupancy = "connected"
            term_b.is_occupied = True
            term_b.occupancy = "connected"

            record_audit_event(
                db,
                actor_id=actor_id,
                actor_name=actor_name,
                action="connection_created",
                entity_type="connection",
                entity_id=new_conn.id,
                changes={
                    "terminal_a_id": str(term_a.id),
                    "terminal_b_id": str(term_b.id),
                    "connection_type": conn_type,
                    "loss_db": loss_db,
                    "structure_id": str(struct_id),
                },
                request_id=request_id,
            )

    new_rev = bump_topology_revision(db)
    db.commit()

    return ConnectionBatchResponse(
        success=True,
        applied_operations_count=len(payload.operations),
        new_topology_revision=new_rev,
    )


def get_structure_connectivity(
    db: Session, structure_id: uuid.UUID
) -> StructureConnectivityResponse:
    """Retorna o panorama completo de conectividade de uma estrutura (terminais, conexões, reservas e arestas internas)."""
    struct = db.execute(select(Structure).where(Structure.id == structure_id)).scalar_one_or_none()
    if struct is None:
        raise NotFoundError(code="structure_not_found", detail="Estrutura física não encontrada.")

    current_rev = get_topology_revision(db)

    # 1. Terminais da estrutura
    terms = (
        db.execute(
            select(Terminal)
            .where(Terminal.structure_id == structure_id)
            .order_by(Terminal.label.asc())
        )
        .scalars()
        .all()
    )
    term_ids = [t.id for t in terms]

    # 2. Conexões ativas da estrutura
    connections: Sequence[Connection] = []
    if term_ids:
        connections = (
            db.execute(
                select(Connection).where(
                    Connection.is_active.is_(True),
                    or_(
                        Connection.structure_id == structure_id,
                        Connection.terminal_a_id.in_(term_ids),
                        Connection.terminal_b_id.in_(term_ids),
                    ),
                )
            )
            .scalars()
            .all()
        )

    # 3. Reservas ativas
    reservations: Sequence[TerminalReservation] = []
    if term_ids:
        reservations = (
            db.execute(
                select(TerminalReservation).where(
                    TerminalReservation.terminal_id.in_(term_ids),
                    TerminalReservation.is_active.is_(True),
                )
            )
            .scalars()
            .all()
        )

    # 4. Arestas internas
    internal_edges: Sequence[InternalEdge] = []
    if term_ids:
        internal_edges = (
            db.execute(
                select(InternalEdge).where(
                    or_(
                        InternalEdge.terminal_a_id.in_(term_ids),
                        InternalEdge.terminal_b_id.in_(term_ids),
                    )
                )
            )
            .scalars()
            .all()
        )

    return StructureConnectivityResponse(
        structure_id=str(structure_id),
        topology_revision=current_rev,
        terminals=[terminal_to_read(t) for t in terms],
        connections=[connection_to_read(c) for c in connections],
        reservations=[reservation_to_read(r) for r in reservations],
        internal_edges=[internal_edge_to_read(e) for e in internal_edges],
    )
