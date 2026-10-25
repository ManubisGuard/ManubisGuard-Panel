"""Per-admin personal host display names.

Revision ID: 20261025_host_admin_names
Revises: 20261023merge01
Create Date: 2026-10-25
"""
import sqlalchemy as sa
from alembic import op

revision = "20261025_host_admin_names"
down_revision = "20261023merge01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "host_admin_names",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("admin_id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), sa.ForeignKey("admins.id", ondelete="CASCADE"), nullable=False),
        sa.Column("host_id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), sa.ForeignKey("hosts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("remark", sa.String(length=256), nullable=False),
        sa.UniqueConstraint("admin_id", "host_id", name="uq_host_admin_names_admin_host"),
    )
    op.create_index("ix_host_admin_names_admin_id", "host_admin_names", ["admin_id"])
    op.create_index("ix_host_admin_names_host_id", "host_admin_names", ["host_id"])


def downgrade() -> None:
    op.drop_index("ix_host_admin_names_host_id", table_name="host_admin_names")
    op.drop_index("ix_host_admin_names_admin_id", table_name="host_admin_names")
    op.drop_table("host_admin_names")
