"""add backup telegram chat id

Revision ID: b7c8d9e0f1a4
Revises: b7c8d9e0f1a3
"""
from alembic import op
import sqlalchemy as sa

revision = "b7c8d9e0f1a4"
down_revision = "b7c8d9e0f1a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("backups", sa.Column("telegram_chat_id", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("backups", "telegram_chat_id")
