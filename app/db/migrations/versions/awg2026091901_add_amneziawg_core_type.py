"""add AmneziaWG core type

Revision ID: awg2026091901
Revises: 48a6bcb8bba1
Create Date: 2026-09-19 00:00:00.000000
"""

from alembic import op


revision = "awg2026091901"
down_revision = "48a6bcb8bba1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute("ALTER TYPE coretype ADD VALUE IF NOT EXISTS 'amneziawg'")
    elif dialect == "mysql":
        op.execute(
            "ALTER TABLE core_configs MODIFY COLUMN type "
            "ENUM('xray','wg','amneziawg','mtproto','singbox') "
            "NOT NULL DEFAULT 'xray'"
        )


def downgrade() -> None:
    # PostgreSQL enum values cannot be safely removed in-place.
    pass
