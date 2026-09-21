"""add AmneziaWG core type.

The downgrade is deliberately data-safe rather than a silent no-op. PostgreSQL
cannot remove an enum value in place, so downgrade rebuilds ``coretype`` only
when no row still uses ``amneziawg``. If such a row exists, it raises instead
of deleting or rewriting user data. SQLite stores this SQLAlchemy enum as a
VARCHAR and therefore has no enum type to remove; its downgrade is a safe
schema no-op.

Revision ID: awg2026091901
Revises: 48a6bcb8bba1
Create Date: 2026-09-19 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

_LEGACY_CORE_TYPES = ("xray", "wg", "mtproto", "singbox")


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
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        # SQLite has no standalone enum type for this column. The value is
        # stored as VARCHAR, so changing Alembic's revision is schema-safe.
        return

    if dialect == "postgresql":
        awg_count = bind.execute(
            sa.text("SELECT COUNT(*) FROM core_configs WHERE type = 'amneziawg'")
        ).scalar_one()
        if awg_count:
            raise RuntimeError(
                "Cannot downgrade awg2026091901 while core_configs contains "
                "AmneziaWG rows; migrate those rows explicitly first."
            )

        bind.execute(sa.text("ALTER TABLE core_configs ALTER COLUMN type DROP DEFAULT"))
        bind.execute(
            sa.text(
                "CREATE TYPE coretype_downgrade AS ENUM "
                "('xray', 'wg', 'mtproto', 'singbox')"
            )
        )
        bind.execute(
            sa.text(
                "ALTER TABLE core_configs ALTER COLUMN type TYPE coretype_downgrade "
                "USING type::text::coretype_downgrade"
            )
        )
        bind.execute(sa.text("DROP TYPE coretype"))
        bind.execute(sa.text("ALTER TYPE coretype_downgrade RENAME TO coretype"))
        bind.execute(sa.text("ALTER TABLE core_configs ALTER COLUMN type SET DEFAULT 'xray'::coretype"))
        return

    if dialect == "mysql":
        awg_count = bind.execute(
            sa.text("SELECT COUNT(*) FROM core_configs WHERE type = 'amneziawg'")
        ).scalar_one()
        if awg_count:
            raise RuntimeError(
                "Cannot downgrade awg2026091901 while core_configs contains "
                "AmneziaWG rows; migrate those rows explicitly first."
            )
        legacy_values = ", ".join(f"'{value}'" for value in _LEGACY_CORE_TYPES)
        bind.execute(
            sa.text(
                "ALTER TABLE core_configs MODIFY COLUMN type "
                f"ENUM({legacy_values}) NOT NULL DEFAULT 'xray'"
            )
        )
