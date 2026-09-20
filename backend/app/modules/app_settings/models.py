import uuid

from sqlalchemy import CheckConstraint, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, VersionedModelMixin

APP_SETTINGS_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class AppSettingsRecord(Base, VersionedModelMixin):
    """Linha singleton com preferências editáveis da instalação."""

    __tablename__ = "app_settings"

    organization_name: Mapped[str] = mapped_column(String(150), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    default_map_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    default_map_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    default_map_zoom: Mapped[int] = mapped_column(Integer, nullable=False)
    excess_loss_tolerance_db: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "default_map_longitude BETWEEN -180 AND 180", name="chk_app_settings_longitude"
        ),
        CheckConstraint(
            "default_map_latitude BETWEEN -90 AND 90", name="chk_app_settings_latitude"
        ),
        CheckConstraint("default_map_zoom BETWEEN 1 AND 22", name="chk_app_settings_zoom"),
        CheckConstraint(
            "excess_loss_tolerance_db BETWEEN 0.1 AND 10.0",
            name="chk_app_settings_excess_loss",
        ),
    )
