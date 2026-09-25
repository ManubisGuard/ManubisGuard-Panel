"""add encrypted backup telegram token

Revision ID: b7c8d9e0f1a3
Revises: b7c8d9e0f1a2
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa

revision = "b7c8d9e0f1a3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("backups", sa.Column("telegram_bot_token", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("backups", "telegram_bot_token")
