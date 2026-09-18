import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.concurrency import check_if_match
from app.core.errors import (
    NotFoundError,
    UnprocessableEntityError,
)
from app.modules.connectivity.models import Terminal
from app.modules.customers.models import ServiceLink
from app.modules.measurements.models import OpticalMeasurement
from app.modules.optical.service import calculate_service_link_budget
from app.schemas.measurements import (
    MeasurementComparisonResponse,
    MeasurementCreate,
    MeasurementOrigin,
    MeasurementRead,
    MeasurementUpdate,
)
from app.schemas.optical import BudgetCalculationRequest
from app.schemas.topology import TraceDirection


def measurement_to_read(m: OpticalMeasurement) -> MeasurementRead:
    return MeasurementRead(
        id=str(m.id),
        terminal_id=str(m.terminal_id),
        service_link_id=str(m.service_link_id) if m.service_link_id else None,
        power_dbm=m.power_dbm,
        wavelength_nm=m.wavelength_nm,
        direction=TraceDirection(m.direction),
        origin=MeasurementOrigin(m.origin)
        if m.origin in MeasurementOrigin.__members__.values()
        else MeasurementOrigin.MANUAL_ENTRY,
        instrument_model=m.instrument_model,
        measured_at=m.measured_at,
        user_id=str(m.user_id) if m.user_id else None,
        predicted_power_dbm=m.predicted_power_dbm,
        excess_loss_db=m.excess_loss_db,
        topology_revision=m.topology_revision,
        notes=m.notes,
        version=m.version,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def get_measurement_by_id(session: Session, measurement_id: str) -> OpticalMeasurement:
    try:
        uid = uuid.UUID(measurement_id)
    except ValueError:
        raise NotFoundError(
            "Medição óptica não encontrada.", code="measurement_not_found"
        ) from None

    measurement = session.scalar(select(OpticalMeasurement).where(OpticalMeasurement.id == uid))
    if not measurement:
        raise NotFoundError("Medição óptica não encontrada.", code="measurement_not_found")
    return measurement


def list_measurements_paginated(
    session: Session,
    page: int = 1,
    page_size: int = 50,
    service_link_id: str | None = None,
    terminal_id: str | None = None,
) -> tuple[list[OpticalMeasurement], int]:
    query = select(OpticalMeasurement)

    if service_link_id:
        try:
            sl_uid = uuid.UUID(service_link_id)
            query = query.where(OpticalMeasurement.service_link_id == sl_uid)
        except ValueError:
            return [], 0

    if terminal_id:
        try:
            term_uid = uuid.UUID(terminal_id)
            query = query.where(OpticalMeasurement.terminal_id == term_uid)
        except ValueError:
            return [], 0

    count_query = select(func.count()).select_from(query.subquery())
    total = session.scalar(count_query) or 0

    items_query = (
        query.order_by(desc(OpticalMeasurement.measured_at), desc(OpticalMeasurement.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(session.scalars(items_query).all())
    return items, total


def create_measurement(
    session: Session,
    payload: MeasurementCreate,
    user_id: str | None = None,
) -> OpticalMeasurement:
    # 1. Validar existência do terminal
    try:
        term_uid = uuid.UUID(payload.terminal_id)
    except ValueError:
        raise UnprocessableEntityError("UUID de terminal inválido.", field="terminal_id") from None

    terminal = session.scalar(select(Terminal).where(Terminal.id == term_uid))
    if not terminal:
        raise NotFoundError("Terminal óptico receptor não encontrado.", code="terminal_not_found")

    # 2. Validar existência do service_link_id se informado
    sl_uid: uuid.UUID | None = None
    if payload.service_link_id:
        try:
            sl_uid = uuid.UUID(payload.service_link_id)
        except ValueError:
            raise UnprocessableEntityError(
                "UUID de atendimento inválido.", field="service_link_id"
            ) from None
        service_link = session.scalar(select(ServiceLink).where(ServiceLink.id == sl_uid))
        if not service_link:
            raise NotFoundError(
                "Atendimento de cliente não encontrado.", code="service_link_not_found"
            )

    # 3. Tentar orçar a potência prevista de referência no momento do registro
    predicted_rx: float | None = None
    excess_loss: float | None = None
    topology_rev: int | None = None
    calculation_snapshot: dict[str, Any] | None = None

    try:
        budget_req = BudgetCalculationRequest(
            service_link_id=str(sl_uid) if sl_uid else None,
            start_terminal_id=str(term_uid) if not sl_uid else None,
            direction=payload.direction,
        )
        budget_resp = calculate_service_link_budget(session, budget_req)
        if budget_resp.status == "complete" and budget_resp.predicted_rx_dbm is not None:
            topology_rev = budget_resp.topology_revision
            calculation_snapshot = budget_resp.model_dump(mode="json")
            # Só calcula perda excedente se o comprimento de onda do orçamento coincidir com o medido
            if budget_resp.wavelength_nm == payload.wavelength_nm:
                predicted_rx = budget_resp.predicted_rx_dbm
                excess_loss = round(predicted_rx - payload.power_dbm, 2)
    except Exception:
        # Não bloqueia o registro de campo se o caminho ainda não estiver 100% documentado
        pass

    user_uid = uuid.UUID(user_id) if user_id else None

    measurement = OpticalMeasurement(
        terminal_id=term_uid,
        service_link_id=sl_uid,
        power_dbm=payload.power_dbm,
        wavelength_nm=payload.wavelength_nm,
        direction=payload.direction.value,
        origin=payload.origin.value,
        instrument_model=payload.instrument_model.strip() if payload.instrument_model else None,
        measured_at=payload.measured_at or datetime.now(UTC),
        user_id=user_uid,
        predicted_power_dbm=predicted_rx,
        excess_loss_db=excess_loss,
        topology_revision=topology_rev,
        calculation_snapshot=calculation_snapshot,
        notes=payload.notes.strip() if payload.notes else None,
        version=1,
    )
    session.add(measurement)
    session.commit()
    session.refresh(measurement)
    return measurement


def update_measurement(
    session: Session,
    measurement_id: str,
    payload: MeasurementUpdate,
    if_match: str | None,
) -> OpticalMeasurement:
    measurement = get_measurement_by_id(session, measurement_id)
    check_if_match(if_match, measurement.version)

    # Edição não altera leituras físicas ou terminal histórico; apenas anotações
    if payload.notes is not None:
        measurement.notes = payload.notes.strip() if payload.notes.strip() else None

    measurement.version += 1
    measurement.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(measurement)
    return measurement


def delete_measurement(
    session: Session,
    measurement_id: str,
    if_match: str | None,
) -> None:
    measurement = get_measurement_by_id(session, measurement_id)
    check_if_match(if_match, measurement.version)

    session.delete(measurement)
    session.commit()


def compare_measurement(
    session: Session,
    measurement_id: str,
    tolerance_db: float = 2.0,
) -> MeasurementComparisonResponse:
    """Compara medição de campo com a potência prevista (B11).

    Calcula a perda excedente = RX previsto - RX medido.
    Exemplo do critério de aceite:
    previsto -19,3 dBm e medido -25,4 dBm produzem exatamente +6,1 dB de perda excedente.
    Medições com direção, onda ou receptor incompatíveis não geram falsos alertas.
    """
    measurement = get_measurement_by_id(session, measurement_id)

    # 1. Executar cálculo de orçamento óptico atualizado para o mesmo elemento receptor
    budget_req = BudgetCalculationRequest(
        service_link_id=str(measurement.service_link_id) if measurement.service_link_id else None,
        start_terminal_id=str(measurement.terminal_id) if not measurement.service_link_id else None,
        direction=TraceDirection(measurement.direction),
    )

    budget_resp = calculate_service_link_budget(session, budget_req)

    # 2. Verificar compatibilidade
    if budget_resp.status != "complete" or budget_resp.predicted_rx_dbm is None:
        return MeasurementComparisonResponse(
            measurement_id=str(measurement.id),
            measured_power_dbm=measurement.power_dbm,
            predicted_power_dbm=None,
            excess_loss_db=None,
            wavelength_nm=measurement.wavelength_nm,
            direction=TraceDirection(measurement.direction),
            tolerance_db=tolerance_db,
            is_within_tolerance=False,
            is_compatible=False,
            incompatibility_reason=(
                "Documentação incompleta do caminho óptico: não foi possível encontrar uma rota "
                "contínua e íntegra até o transmissor de sinal."
            ),
            topology_revision=budget_resp.topology_revision,
        )

    # Verificar compatibilidade do comprimento de onda
    if budget_resp.wavelength_nm != measurement.wavelength_nm:
        return MeasurementComparisonResponse(
            measurement_id=str(measurement.id),
            measured_power_dbm=measurement.power_dbm,
            predicted_power_dbm=budget_resp.predicted_rx_dbm,
            excess_loss_db=None,
            wavelength_nm=measurement.wavelength_nm,
            direction=TraceDirection(measurement.direction),
            tolerance_db=tolerance_db,
            is_within_tolerance=False,
            is_compatible=False,
            incompatibility_reason=(
                f"Comprimento de onda incompatível: instrumento mediu em {measurement.wavelength_nm} nm, "
                f"enquanto o orçamento projetado utiliza {budget_resp.wavelength_nm} nm."
            ),
            topology_revision=budget_resp.topology_revision,
        )

    # 3. Cálculo da Perda Excedente: RX previsto - RX medido
    # Ex: previsto -19.3 dBm - (-25.4 dBm) = +6.1 dB
    predicted_rx = budget_resp.predicted_rx_dbm
    excess_loss = round(predicted_rx - measurement.power_dbm, 2)

    # Dentro da tolerância se a perda excedente não ultrapassar a tolerância máxima permitida
    is_within_tolerance = excess_loss <= tolerance_db

    return MeasurementComparisonResponse(
        measurement_id=str(measurement.id),
        measured_power_dbm=measurement.power_dbm,
        predicted_power_dbm=predicted_rx,
        excess_loss_db=excess_loss,
        wavelength_nm=measurement.wavelength_nm,
        direction=TraceDirection(measurement.direction),
        tolerance_db=tolerance_db,
        is_within_tolerance=is_within_tolerance,
        is_compatible=True,
        incompatibility_reason=None,
        topology_revision=budget_resp.topology_revision,
    )
