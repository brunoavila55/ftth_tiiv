from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.concurrency import check_if_match
from app.core.config import get_settings
from app.core.errors import UnprocessableEntityError
from app.modules.app_settings.models import APP_SETTINGS_ID, AppSettingsRecord
from app.schemas.settings import AppSettingsRead, AppSettingsUpdate


def _default_record() -> AppSettingsRecord:
    return AppSettingsRecord(
        id=APP_SETTINGS_ID,
        organization_name="Operação FTTH",
        timezone="America/Sao_Paulo",
        default_map_longitude=-53.0,
        default_map_latitude=-30.0,
        default_map_zoom=7,
        excess_loss_tolerance_db=2.0,
        version=1,
    )


def get_record(db: Session) -> AppSettingsRecord:
    record = db.get(AppSettingsRecord, APP_SETTINGS_ID)
    if record is None:
        # Recuperação defensiva caso a linha singleton tenha sido removida fora da aplicação.
        record = _default_record()
        db.add(record)
        db.commit()
        db.refresh(record)
    return record


def settings_to_read(record: AppSettingsRecord) -> AppSettingsRead:
    runtime = get_settings()
    return AppSettingsRead(
        app_name=runtime.APP_NAME,
        organization_name=record.organization_name,
        timezone=record.timezone,
        default_map_center=(record.default_map_longitude, record.default_map_latitude),
        default_map_zoom=record.default_map_zoom,
        max_upload_size_bytes=runtime.MAX_UPLOAD_SIZE_BYTES,
        trace_max_depth=runtime.MAX_TRACE_HOPS,
        excess_loss_tolerance_db=record.excess_loss_tolerance_db,
        version=record.version,
    )


def get_app_settings(db: Session) -> AppSettingsRead:
    return settings_to_read(get_record(db))


def update_app_settings(
    db: Session,
    *,
    payload: AppSettingsUpdate,
    if_match: str | None,
) -> AppSettingsRead:
    record = get_record(db)
    check_if_match(if_match, record.version)

    changed = False
    if payload.organization_name is not None:
        clean_name = payload.organization_name.strip()
        if not clean_name:
            raise UnprocessableEntityError(
                detail="O nome da organização não pode ser vazio.",
                field="organization_name",
            )
        record.organization_name = clean_name
        changed = True
    if payload.timezone is not None:
        try:
            ZoneInfo(payload.timezone)
        except ZoneInfoNotFoundError:
            raise UnprocessableEntityError(
                detail=f"Fuso horário IANA desconhecido: '{payload.timezone}'.",
                field="timezone",
                code="invalid_timezone",
            ) from None
        record.timezone = payload.timezone
        changed = True
    if payload.default_map_center is not None:
        record.default_map_longitude, record.default_map_latitude = payload.default_map_center
        changed = True
    if payload.default_map_zoom is not None:
        record.default_map_zoom = payload.default_map_zoom
        changed = True
    if payload.excess_loss_tolerance_db is not None:
        record.excess_loss_tolerance_db = payload.excess_loss_tolerance_db
        changed = True

    if changed:
        record.version += 1
        record.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(record)
    return settings_to_read(record)
