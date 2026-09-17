from sqlalchemy import CheckConstraint, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, VersionedModelMixin


class OpticalProfile(Base, VersionedModelMixin):
    """Perfil de parâmetros ópticos para transmissor/receptor de uma tecnologia PON."""

    __tablename__ = "optical_profiles"
    __table_args__ = (
        CheckConstraint(
            "tx_min_dbm <= tx_max_dbm",
            name="chk_optical_profile_tx",
        ),
        CheckConstraint(
            "rx_sensitivity_dbm <= rx_overload_dbm",
            name="chk_optical_profile_rx",
        ),
        CheckConstraint(
            "wavelength_nm >= 800 AND wavelength_nm <= 2000",
            name="chk_optical_profile_wavelength",
        ),
        CheckConstraint(
            "default_attenuation_db_per_km >= 0.0",
            name="chk_optical_profile_attenuation",
        ),
    )

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    technology: Mapped[str] = mapped_column(String(50), nullable=False, default="GPON")
    wavelength_nm: Mapped[int] = mapped_column(Integer, nullable=False)
    tx_min_dbm: Mapped[float] = mapped_column(Float, nullable=False)
    tx_max_dbm: Mapped[float] = mapped_column(Float, nullable=False)
    rx_sensitivity_dbm: Mapped[float] = mapped_column(Float, nullable=False)
    rx_overload_dbm: Mapped[float] = mapped_column(Float, nullable=False)
    default_attenuation_db_per_km: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.35
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
