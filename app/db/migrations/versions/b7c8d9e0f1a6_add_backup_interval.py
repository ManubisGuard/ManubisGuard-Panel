"""add interval backup schedules

Revision ID: b7c8d9e0f1a6
Revises: b7c8d9e0f1a5
Create Date: 2026-10-03
"""
import sqlalchemy as sa
from alembic import op
revision = "b7c8d9e0f1a6"
down_revision = "b7c8d9e0f1a5"
branch_labels = None
depends_on = None
def upgrade() -> None:
    op.add_column("backup_schedules", sa.Column("interval_minutes", sa.Integer(), nullable=True))
def downgrade() -> None:
    op.drop_column("backup_schedules", "interval_minutes")
