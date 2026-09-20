import math
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql import Select

from app.core.concurrency import check_if_match
from app.core.errors import ConflictError, NotFoundError, UnprocessableEntityError
from app.modules.cables.models import FiberSegment
from app.modules.connectivity.models import (
    Connection,
    ConnectionEndpoint,
    InternalEdge,
    Splitter,
    SplitterOutput,
    Terminal,
    TerminalReservation,
)
from app.modules.gis.service import bump_topology_revision
from app.modules.inventory.models import Device, Structure
from app.modules.measurements.models import OpticalMeasurement
from app.schemas.splitters import (
    SplitterCreate,
    SplitterPortLoss,
    SplitterPortRead,
    SplitterRead,
    SplitterUpdate,
)

_RATIO_PATTERN = re.compile(
    r"^\s*1\s*:\s*(\d+)(?:\s+(?:desbalanceado|unbalanced))?\s*$", re.IGNORECASE
)
_STANDARD_LOSS_DB = {2: 3.6, 4: 7.2, 8: 10.5, 16: 13.7, 32: 17.0, 64: 20.5}


def _default_loss(output_count: int) -> float:
    return _STANDARD_LOSS_DB.get(output_count, round(3.5 * math.log2(output_count), 2))


def _validate_ratio(ratio: str, output_count: int) -> str:
    clean_ratio = ratio.strip()
    match = _RATIO_PATTERN.match(clean_ratio)
    if match is None or int(match.group(1)) != output_count:
        raise UnprocessableEntityError(
            detail=(
                f"A razão '{ratio}' deve começar com '1:{output_count}' para corresponder "
                "à quantidade de portas de saída."
            ),
            field="ratio",
            code="splitter_ratio_mismatch",
        )
    return clean_ratio


def _normalized_losses(ports: list[SplitterPortLoss], output_count: int) -> list[SplitterPortLoss]:
    if not ports:
        loss = _default_loss(output_count)
        return [
            SplitterPortLoss(
                port_number=number,
                loss_1310_db=loss,
                loss_1490_db=loss,
                loss_1550_db=loss,
            )
            for number in range(1, output_count + 1)
        ]

    numbers = [port.port_number for port in ports]
    expected = list(range(1, output_count + 1))
    if sorted(numbers) != expected:
        raise UnprocessableEntityError(
            detail=(
                "A lista de perdas deve conter exatamente uma entrada para cada porta, "
                f"numeradas de 1 a {output_count}."
            ),
            field="ports",
            code="invalid_splitter_ports",
        )
    return sorted(ports, key=lambda port: port.port_number)


def _splitter_query() -> Select[tuple[Splitter]]:
    return select(Splitter).options(selectinload(Splitter.outputs))


def _get_splitter(db: Session, splitter_id: uuid.UUID) -> Splitter:
    splitter = db.scalar(_splitter_query().where(Splitter.id == splitter_id))
    if splitter is None:
        raise NotFoundError(detail=f"Splitter {splitter_id} não existe.", code="splitter_not_found")
    return splitter


def splitter_to_read(splitter: Splitter) -> SplitterRead:
    outputs = sorted(splitter.outputs, key=lambda output: output.output_number)
    ports = [
        SplitterPortRead(
            port_number=0,
            is_input=True,
            terminal_id=str(splitter.input_terminal_id),
        )
    ]
    ports.extend(
        SplitterPortRead(
            port_number=output.output_number,
            is_input=False,
            terminal_id=str(output.terminal_id),
            loss_1310_db=(
                output.loss_1310_db if output.loss_1310_db is not None else output.nominal_loss_db
            ),
            loss_1490_db=(
                output.loss_1490_db if output.loss_1490_db is not None else output.nominal_loss_db
            ),
            loss_1550_db=output.loss_1550_db,
        )
        for output in outputs
    )
    return SplitterRead(
        id=str(splitter.id),
        code=splitter.code,
        structure_id=str(splitter.structure_id) if splitter.structure_id else None,
        device_id=str(splitter.device_id) if splitter.device_id else None,
        ratio=splitter.ratio,
        output_ports_count=len(outputs),
        input_terminal_id=str(splitter.input_terminal_id),
        ports=ports,
        notes=splitter.notes,
        version=splitter.version,
        created_at=splitter.created_at,
        updated_at=splitter.updated_at,
    )


def list_splitters(
    db: Session,
    *,
    structure_id: uuid.UUID | None,
    page: int,
    page_size: int,
) -> tuple[list[SplitterRead], int]:
    query = _splitter_query()
    count_query = select(func.count(Splitter.id))
    if structure_id is not None:
        # Splitters alojados diretamente ou em dispositivos da estrutura.
        device_ids = select(Device.id).where(Device.structure_id == structure_id)
        location_filter = or_(
            Splitter.structure_id == structure_id,
            Splitter.device_id.in_(device_ids),
        )
        query = query.where(location_filter)
        count_query = count_query.where(location_filter)

    total = db.scalar(count_query) or 0
    rows = db.scalars(
        query.order_by(Splitter.code, Splitter.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [splitter_to_read(splitter) for splitter in rows], total


def get_splitter(db: Session, splitter_id: uuid.UUID) -> SplitterRead:
    return splitter_to_read(_get_splitter(db, splitter_id))


def create_splitter(db: Session, payload: SplitterCreate) -> SplitterRead:
    if bool(payload.structure_id) == bool(payload.device_id):
        raise UnprocessableEntityError(
            detail="O splitter deve pertencer exclusivamente a uma estrutura OU dispositivo.",
            field="location",
            code="invalid_splitter_location",
        )

    code = payload.code.strip().upper()
    if db.scalar(select(Splitter.id).where(func.lower(Splitter.code) == code.lower())):
        raise ConflictError(
            detail=f"Já existe um splitter com o código '{code}'.",
            code="code_already_exists",
        )

    ratio = _validate_ratio(payload.ratio, payload.output_ports_count)
    losses = _normalized_losses(payload.ports, payload.output_ports_count)

    structure_id: uuid.UUID | None = None
    site_id: uuid.UUID | None = None
    device_id: uuid.UUID | None = None
    if payload.structure_id:
        structure_id = uuid.UUID(payload.structure_id)
        if db.get(Structure, structure_id) is None:
            raise NotFoundError(
                detail="Estrutura informada não encontrada.", code="structure_not_found"
            )
    else:
        device_id = uuid.UUID(payload.device_id or "")
        device = db.get(Device, device_id)
        if device is None:
            raise NotFoundError(
                detail="Dispositivo informado não encontrado.", code="device_not_found"
            )
        structure_id = device.structure_id
        site_id = device.site_id

    input_terminal = Terminal(
        kind="splitter_input",
        structure_id=structure_id,
        site_id=site_id,
        label=f"{code} IN",
        is_occupied=False,
        occupancy="free",
        entity_type="splitter",
        version=1,
    )
    db.add(input_terminal)
    db.flush()

    splitter = Splitter(
        structure_id=structure_id,
        site_id=site_id,
        device_id=device_id,
        code=code,
        splitter_type=(
            "unbalanced"
            if len({loss.loss_1490_db for loss in losses}) > 1
            or "desbalanceado" in ratio.lower()
            or "unbalanced" in ratio.lower()
            else "balanced"
        ),
        ratio=ratio,
        input_terminal_id=input_terminal.id,
        notes=payload.notes,
        version=1,
    )
    db.add(splitter)
    db.flush()
    input_terminal.entity_id = splitter.id

    for loss in losses:
        terminal = Terminal(
            kind="splitter_output",
            structure_id=structure_id,
            site_id=site_id,
            label=f"{code} OUT {loss.port_number}",
            is_occupied=False,
            occupancy="free",
            entity_type="splitter",
            entity_id=splitter.id,
            version=1,
        )
        db.add(terminal)
        db.flush()
        db.add(
            SplitterOutput(
                splitter_id=splitter.id,
                output_number=loss.port_number,
                terminal_id=terminal.id,
                nominal_loss_db=loss.loss_1490_db,
                measured_loss_db=None,
                loss_1310_db=loss.loss_1310_db,
                loss_1490_db=loss.loss_1490_db,
                loss_1550_db=loss.loss_1550_db,
                version=1,
            )
        )

    bump_topology_revision(db)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            detail="Conflito de integridade ao criar o splitter.",
            code="splitter_integrity_conflict",
        ) from exc
    return get_splitter(db, splitter.id)


def update_splitter(
    db: Session,
    *,
    splitter_id: uuid.UUID,
    payload: SplitterUpdate,
    if_match: str | None,
) -> SplitterRead:
    splitter = _get_splitter(db, splitter_id)
    check_if_match(if_match, splitter.version)

    if "notes" in payload.model_fields_set:
        splitter.notes = payload.notes
    if payload.ports is not None:
        losses = _normalized_losses(payload.ports, len(splitter.outputs))
        outputs = {output.output_number: output for output in splitter.outputs}
        for loss in losses:
            output = outputs[loss.port_number]
            output.nominal_loss_db = loss.loss_1490_db
            output.loss_1310_db = loss.loss_1310_db
            output.loss_1490_db = loss.loss_1490_db
            output.loss_1550_db = loss.loss_1550_db
            output.version += 1
            output.updated_at = datetime.now(UTC)
        splitter.splitter_type = (
            "unbalanced" if len({loss.loss_1490_db for loss in losses}) > 1 else "balanced"
        )

    splitter.version += 1
    splitter.updated_at = datetime.now(UTC)
    bump_topology_revision(db)
    db.commit()
    return get_splitter(db, splitter.id)


def _terminal_has_dependencies(db: Session, terminal_ids: list[uuid.UUID]) -> bool:
    checks = (
        select(func.count(Connection.id)).where(
            or_(
                Connection.terminal_a_id.in_(terminal_ids),
                Connection.terminal_b_id.in_(terminal_ids),
            )
        ),
        select(func.count(ConnectionEndpoint.id)).where(
            ConnectionEndpoint.terminal_id.in_(terminal_ids)
        ),
        select(func.count(TerminalReservation.id)).where(
            TerminalReservation.terminal_id.in_(terminal_ids)
        ),
        select(func.count(InternalEdge.id)).where(
            or_(
                InternalEdge.terminal_a_id.in_(terminal_ids),
                InternalEdge.terminal_b_id.in_(terminal_ids),
            )
        ),
        select(func.count(FiberSegment.id)).where(
            or_(
                FiberSegment.terminal_a_id.in_(terminal_ids),
                FiberSegment.terminal_b_id.in_(terminal_ids),
            )
        ),
        select(func.count(OpticalMeasurement.id)).where(
            OpticalMeasurement.terminal_id.in_(terminal_ids)
        ),
    )
    return any((db.scalar(statement) or 0) > 0 for statement in checks)


def delete_splitter(
    db: Session,
    *,
    splitter_id: uuid.UUID,
    if_match: str | None,
) -> None:
    splitter = _get_splitter(db, splitter_id)
    check_if_match(if_match, splitter.version)
    terminal_ids = [
        splitter.input_terminal_id,
        *(output.terminal_id for output in splitter.outputs),
    ]
    if _terminal_has_dependencies(db, terminal_ids):
        raise ConflictError(
            detail=(
                "Não é possível excluir o splitter enquanto suas portas possuem conexões, "
                "reservas, medições ou outros vínculos ópticos."
            ),
            code="splitter_in_use",
        )

    terminals = list(db.scalars(select(Terminal).where(Terminal.id.in_(terminal_ids))).all())
    db.delete(splitter)
    db.flush()
    for terminal in terminals:
        db.delete(terminal)
    bump_topology_revision(db)
    db.commit()
