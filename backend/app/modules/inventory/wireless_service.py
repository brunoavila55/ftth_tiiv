import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.concurrency import check_if_match
from app.core.errors import ConflictError, NotFoundError, UnprocessableEntityError
from app.core.search import contains
from app.modules.inventory.models import Device, RadioLink, Site
from app.schemas.common import AdministrativeStatus
from app.schemas.wireless import RadioLinkCreate, RadioLinkRead, RadioLinkUpdate

WIRELESS_SITE_KINDS = frozenset({"wireless_pop", "radio_tower"})


def radio_link_to_read(link: RadioLink) -> RadioLinkRead:
    return RadioLinkRead(
        id=str(link.id),
        code=link.code,
        name=link.name,
        site_a_id=str(link.site_a_id),
        site_b_id=str(link.site_b_id),
        radio_a_id=str(link.radio_a_id),
        radio_b_id=str(link.radio_b_id),
        frequency_mhz=link.frequency_mhz,
        channel_width_mhz=link.channel_width_mhz,
        status=AdministrativeStatus(link.status),
        notes=link.notes,
        version=link.version,
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


def list_radio_links(
    session: Session,
    *,
    page: int,
    page_size: int,
    site_id: uuid.UUID | None = None,
    q: str | None = None,
) -> tuple[list[RadioLink], int]:
    query = select(RadioLink)
    count_query = select(func.count(RadioLink.id))
    if site_id:
        condition = or_(RadioLink.site_a_id == site_id, RadioLink.site_b_id == site_id)
        query = query.where(condition)
        count_query = count_query.where(condition)
    if q and q.strip():
        condition = contains(RadioLink.code, q) | contains(RadioLink.name, q)
        query = query.where(condition)
        count_query = count_query.where(condition)
    total = session.scalar(count_query) or 0
    links = list(
        session.scalars(
            query.order_by(RadioLink.created_at.desc(), RadioLink.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return links, total


def get_radio_link(session: Session, link_id: uuid.UUID) -> RadioLink:
    link = session.get(RadioLink, link_id)
    if link is None:
        raise NotFoundError("Enlace de rádio não encontrado.", code="radio_link_not_found")
    return link


def _validate_endpoint(session: Session, site_id: uuid.UUID, radio_id: uuid.UUID) -> None:
    site = session.get(Site, site_id)
    if site is None or site.kind not in WIRELESS_SITE_KINDS:
        raise UnprocessableEntityError(
            "Cada ponta deve ser um POP wireless ou uma torre de rádio cadastrada.",
            field="site_id",
        )
    radio = session.get(Device, radio_id)
    if radio is None or radio.kind != "radio" or radio.site_id != site_id:
        raise UnprocessableEntityError(
            "O rádio da ponta deve estar alocado no site wireless correspondente.",
            field="radio_id",
        )


def create_radio_link(session: Session, payload: RadioLinkCreate) -> RadioLink:
    code = payload.code.strip().upper()
    if session.scalar(select(RadioLink.id).where(RadioLink.code == code)):
        raise ConflictError("Já existe um enlace com este código.", code="code_already_exists")
    site_a_id = uuid.UUID(payload.site_a_id)
    site_b_id = uuid.UUID(payload.site_b_id)
    radio_a_id = uuid.UUID(payload.radio_a_id)
    radio_b_id = uuid.UUID(payload.radio_b_id)
    _validate_endpoint(session, site_a_id, radio_a_id)
    _validate_endpoint(session, site_b_id, radio_b_id)
    link = RadioLink(
        code=code,
        name=payload.name.strip(),
        site_a_id=site_a_id,
        site_b_id=site_b_id,
        radio_a_id=radio_a_id,
        radio_b_id=radio_b_id,
        frequency_mhz=payload.frequency_mhz,
        channel_width_mhz=payload.channel_width_mhz,
        status=payload.status.value,
        notes=payload.notes,
        version=1,
    )
    session.add(link)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ConflictError(
            "Enlace duplicado ou ponta indisponível.", code="radio_link_conflict"
        ) from None
    session.refresh(link)
    return link


def update_radio_link(
    session: Session,
    link_id: uuid.UUID,
    payload: RadioLinkUpdate,
    if_match: str | None,
) -> RadioLink:
    link = get_radio_link(session, link_id)
    check_if_match(if_match, link.version)
    if payload.name is not None:
        link.name = payload.name.strip()
    if payload.frequency_mhz is not None:
        link.frequency_mhz = payload.frequency_mhz
    if payload.channel_width_mhz is not None:
        link.channel_width_mhz = payload.channel_width_mhz
    if payload.status is not None:
        link.status = payload.status.value
    if "notes" in payload.model_fields_set:
        link.notes = payload.notes
    link.version += 1
    link.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(link)
    return link


def delete_radio_link(session: Session, link_id: uuid.UUID, if_match: str | None) -> None:
    link = get_radio_link(session, link_id)
    check_if_match(if_match, link.version)
    session.delete(link)
    session.commit()
