"""allow assigning multiple core configs to one node

Revision ID: c1a2b3c4d5e6
Revises: b7c8d9e0f1a5
"""
from alembic import op
import sqlalchemy as sa

revision = "c1a2b3c4d5e6"
down_revision = "b7c8d9e0f1a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("nodes", sa.Column("core_config_ids", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("nodes", "core_config_ids")
