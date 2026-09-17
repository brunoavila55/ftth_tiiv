from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NetworkTopologyState(Base):
    """Estado monotônico da revisão da topologia da rede FTTH.

    Esta tabela armazena a versão global da topologia (topology_revision).
    Qualquer mutação física ou lógica que afete caminhos ópticos, perdas ou comprimentos
    incrementa atomicamente este contador.
    """

    __tablename__ = "network_topology_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    topology_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
