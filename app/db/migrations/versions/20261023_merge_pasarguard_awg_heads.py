"""Merge the PasarGuard production and ManubisGuard AWG migration heads.

Revision ID: 20261023merge01
Revises: c8d2e4f6a1b3, c1a2b3c4d5e6
Create Date: 2026-10-23
"""
from alembic import op

revision = "20261023merge01"
down_revision = ("c8d2e4f6a1b3", "c1a2b3c4d5e6")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
