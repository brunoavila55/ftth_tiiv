import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    PreconditionRequiredError,
    UnprocessableEntityError,
)
from app.modules.optical.models import OpticalProfile
from app.schemas.optical import (
    OpticalProfileCreate,
    OpticalProfileRead,
    OpticalProfileUpdate,
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


def optical_profile_to_read(profile: OpticalProfile) -> OpticalProfileRead:
    return OpticalProfileRead(
        id=str(profile.id),
        name=profile.name,
        technology=profile.technology,
        wavelength_nm=profile.wavelength_nm,
        tx_min_dbm=profile.tx_min_dbm,
        tx_max_dbm=profile.tx_max_dbm,
        rx_sensitivity_dbm=profile.rx_sensitivity_dbm,
        rx_overload_dbm=profile.rx_overload_dbm,
        default_attenuation_db_per_km=profile.default_attenuation_db_per_km,
        notes=profile.notes,
        version=profile.version,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def list_optical_profiles_paginated(
    session: Session,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[OpticalProfile], int]:
    query = select(OpticalProfile)
    count_query = select(func.count(OpticalProfile.id))

    total = session.scalar(count_query) or 0
    offset = (page - 1) * page_size
    items = list(
        session.scalars(
            query.order_by(OpticalProfile.created_at.desc(), OpticalProfile.id)
            .offset(offset)
            .limit(page_size)
        ).all()
    )
    return items, total


def get_optical_profile_by_id(session: Session, profile_id: str) -> OpticalProfile:
    try:
        profile_uuid = uuid.UUID(profile_id)
    except ValueError:
        raise NotFoundError("Perfil óptico não encontrado.", code="profile_not_found") from None

    profile = session.scalar(select(OpticalProfile).where(OpticalProfile.id == profile_uuid))
    if not profile:
        raise NotFoundError("Perfil óptico não encontrado.", code="profile_not_found")
    return profile


def create_optical_profile(session: Session, payload: OpticalProfileCreate) -> OpticalProfile:
    if payload.tx_min_dbm > payload.tx_max_dbm:
        raise UnprocessableEntityError(
            "Potência mínima de transmissão (tx_min_dbm) não pode ser maior que a máxima (tx_max_dbm).",
            field="tx_min_dbm",
        )
    if payload.rx_sensitivity_dbm > payload.rx_overload_dbm:
        raise UnprocessableEntityError(
            "Sensibilidade RX (rx_sensitivity_dbm) não pode ser maior que o limite de sobrecarga (rx_overload_dbm).",
            field="rx_sensitivity_dbm",
        )

    clean_name = payload.name.strip()
    existing = session.scalar(select(OpticalProfile).where(OpticalProfile.name == clean_name))
    if existing:
        raise ConflictError(
            f"Já existe um perfil óptico com o nome '{clean_name}'.",
            code="name_already_exists",
        )

    profile = OpticalProfile(
        name=clean_name,
        technology=payload.technology.strip(),
        wavelength_nm=payload.wavelength_nm,
        tx_min_dbm=payload.tx_min_dbm,
        tx_max_dbm=payload.tx_max_dbm,
        rx_sensitivity_dbm=payload.rx_sensitivity_dbm,
        rx_overload_dbm=payload.rx_overload_dbm,
        default_attenuation_db_per_km=payload.default_attenuation_db_per_km,
        notes=payload.notes,
        version=1,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def update_optical_profile(
    session: Session,
    profile_id: str,
    payload: OpticalProfileUpdate,
    if_match: str | None,
) -> OpticalProfile:
    profile = get_optical_profile_by_id(session, profile_id)
    _validate_if_match(if_match, profile.version)

    new_tx_min = payload.tx_min_dbm if payload.tx_min_dbm is not None else profile.tx_min_dbm
    new_tx_max = payload.tx_max_dbm if payload.tx_max_dbm is not None else profile.tx_max_dbm
    new_rx_sens = (
        payload.rx_sensitivity_dbm
        if payload.rx_sensitivity_dbm is not None
        else profile.rx_sensitivity_dbm
    )
    new_rx_over = (
        payload.rx_overload_dbm if payload.rx_overload_dbm is not None else profile.rx_overload_dbm
    )

    if new_tx_min > new_tx_max:
        raise UnprocessableEntityError(
            "Potência mínima de transmissão (tx_min_dbm) não pode ser maior que a máxima (tx_max_dbm).",
            field="tx_min_dbm",
        )
    if new_rx_sens > new_rx_over:
        raise UnprocessableEntityError(
            "Sensibilidade RX (rx_sensitivity_dbm) não pode ser maior que o limite de sobrecarga (rx_overload_dbm).",
            field="rx_sensitivity_dbm",
        )

    if payload.name is not None:
        clean_name = payload.name.strip()
        if clean_name != profile.name:
            existing = session.scalar(
                select(OpticalProfile).where(
                    OpticalProfile.name == clean_name, OpticalProfile.id != profile.id
                )
            )
            if existing:
                raise ConflictError(
                    f"Já existe um perfil óptico com o nome '{clean_name}'.",
                    code="name_already_exists",
                )
            profile.name = clean_name

    if payload.tx_min_dbm is not None:
        profile.tx_min_dbm = payload.tx_min_dbm
    if payload.tx_max_dbm is not None:
        profile.tx_max_dbm = payload.tx_max_dbm
    if payload.rx_sensitivity_dbm is not None:
        profile.rx_sensitivity_dbm = payload.rx_sensitivity_dbm
    if payload.rx_overload_dbm is not None:
        profile.rx_overload_dbm = payload.rx_overload_dbm
    if payload.default_attenuation_db_per_km is not None:
        profile.default_attenuation_db_per_km = payload.default_attenuation_db_per_km
    if payload.notes is not None:
        profile.notes = payload.notes

    profile.version += 1
    profile.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(profile)
    return profile


def delete_optical_profile(session: Session, profile_id: str, if_match: str | None) -> None:
    profile = get_optical_profile_by_id(session, profile_id)
    _validate_if_match(if_match, profile.version)

    try:
        session.delete(profile)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ConflictError(
            "Não é possível excluir o perfil óptico pois ele está associado a circuitos ou cabos ativos.",
            code="referenced_entity_conflict",
        ) from None
