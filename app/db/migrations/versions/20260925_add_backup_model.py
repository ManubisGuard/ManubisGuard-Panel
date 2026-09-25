"""add backup model

Revision ID: b7c8d9e0f1a2
Revises: awg2026091901
Create Date: 2026-09-25

"""
from alembic import op
import sqlalchemy as sa

from app.db.compiles_types import SqliteCompatibleBigInteger

revision = "b7c8d9e0f1a2"
down_revision = "awg2026091901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backups",
        sa.Column("id", SqliteCompatibleBigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("source_version", sa.String(length=64), nullable=True),
        sa.Column("source_db", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("backup_path", sa.String(length=2048), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("schedule_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["admins.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backups_created_at", "backups", ["created_at"], unique=False)
    op.create_index("ix_backups_status", "backups", ["status"], unique=False)
    op.create_index("ix_backups_schedule_id", "backups", ["schedule_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_backups_schedule_id", table_name="backups")
    op.drop_index("ix_backups_status", table_name="backups")
    op.drop_index("ix_backups_created_at", table_name="backups")
    op.drop_table("backups")
