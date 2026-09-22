"""usa o Rio Grande do Sul como centro padrão do mapa

Revision ID: 0017_default_map_rs
Revises: 0016_splitter_crud_settings
Create Date: 2026-09-22 10:00:00.000000
"""

from alembic import op

revision: str = "0017_default_map_rs"
down_revision: str | None = "0016_splitter_crud_settings"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Preserva instalações que já personalizaram o centro do mapa.
    op.execute(
        "UPDATE app_settings "
        "SET default_map_longitude = -53.0, default_map_latitude = -30.0, "
        "default_map_zoom = 7, version = version + 1, updated_at = NOW() "
        "WHERE default_map_longitude = -46.633308 "
        "AND default_map_latitude = -23.550520 "
        "AND default_map_zoom = 14"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE app_settings "
        "SET default_map_longitude = -46.633308, default_map_latitude = -23.550520, "
        "default_map_zoom = 14, version = version + 1, updated_at = NOW() "
        "WHERE default_map_longitude = -53.0 "
        "AND default_map_latitude = -30.0 "
        "AND default_map_zoom = 7"
    )
