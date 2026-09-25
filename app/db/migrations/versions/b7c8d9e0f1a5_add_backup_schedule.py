"""add persisted backup schedule

Revision ID: b7c8d9e0f1a5
Revises: b7c8d9e0f1a4
Create Date: 2026-09-25
"""

import sqlalchemy as sa
from alembic import op

from app.db.compiles_types import SqliteCompatibleBigInteger

revision = "b7c8d9e0f1a5"
down_revision = "b7c8d9e0f1a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backup_schedules",
        sa.Column("id", SqliteCompatibleBigInteger(), autoincrement=True, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("frequency", sa.String(length=16), nullable=False, server_default="daily"),
        sa.Column("hour", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("minute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("day_of_month", sa.Integer(), nullable=True),
        sa.Column("retention_count", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backup_schedules_enabled", "backup_schedules", ["enabled"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_backup_schedules_enabled", table_name="backup_schedules")
    op.drop_table("backup_schedules")
