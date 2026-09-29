"""cadastra enlaces de rádio entre POPs wireless e torres

Revision ID: 0018_wireless_links
Revises: 0017_default_map_rs
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_wireless_links"
down_revision: str | None = "0017_default_map_rs"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_devices_id_site_id", "devices", ["id", "site_id"])
    op.create_table(
        "radio_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "site_a_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "site_b_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "radio_a_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "radio_b_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("frequency_mhz", sa.Float(), nullable=False),
        sa.Column("channel_width_mhz", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="planned"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("site_a_id <> site_b_id", name="chk_radio_link_distinct_sites"),
        sa.CheckConstraint("radio_a_id <> radio_b_id", name="chk_radio_link_distinct_radios"),
        sa.CheckConstraint(
            "frequency_mhz > 0 AND frequency_mhz <= 100000", name="chk_radio_link_frequency"
        ),
        sa.CheckConstraint(
            "channel_width_mhz > 0 AND channel_width_mhz <= 10000", name="chk_radio_link_width"
        ),
        sa.ForeignKeyConstraint(
            ["radio_a_id", "site_a_id"],
            ["devices.id", "devices.site_id"],
            name="fk_radio_link_a_device_site",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["radio_b_id", "site_b_id"],
            ["devices.id", "devices.site_id"],
            name="fk_radio_link_b_device_site",
            ondelete="RESTRICT",
        ),
    )
    for column in ("code", "site_a_id", "site_b_id", "radio_a_id", "radio_b_id"):
        op.create_index(
            f"ix_radio_links_{column}", "radio_links", [column], unique=column == "code"
        )


def downgrade() -> None:
    op.drop_table("radio_links")
    op.drop_constraint("uq_devices_id_site_id", "devices", type_="unique")
