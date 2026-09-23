from app.migration.restore_safety import (
    prepare_postgresql_sql,
    sanitize_role_password_line,
)


def test_role_password_is_removed():
    line = "ALTER ROLE pasarguard WITH LOGIN PASSWORD 'legacy-secret';"
    transformed, changed = sanitize_role_password_line(line)
    assert changed is True
    assert "PASSWORD" not in transformed.upper()
    assert "legacy-secret" not in transformed


def test_destination_role_statement_is_suppressed():
    line = 'ALTER ROLE "pasarguard" WITH SUPERUSER LOGIN PASSWORD \'legacy-secret\';'
    transformed, changed = sanitize_role_password_line(
        line,
        destination_role="pasarguard",
    )
    assert changed is True
    assert transformed == ""


def test_quoted_non_destination_role_keeps_non_password_attributes():
    line = 'CREATE ROLE "legacy_admin" WITH LOGIN PASSWORD \'legacy-secret\';'
    transformed, changed = sanitize_role_password_line(
        line,
        destination_role="pasarguard",
    )
    assert changed is True
    assert transformed == 'CREATE ROLE "legacy_admin" WITH LOGIN;'


def test_prepare_postgresql_sql_counts_transformations():
    source = (
        "-- PostgreSQL database cluster dump\n"
        'ALTER ROLE pasarguard WITH SUPERUSER LOGIN PASSWORD \'secret\';\n'
        'ALTER ROLE "pasarguard" WITH CREATEDB PASSWORD \'other-secret\';\n'
        'CREATE ROLE legacy_admin WITH LOGIN PASSWORD \'legacy-admin-secret\';\n'
    )
    transformed, removed, suppressed = prepare_postgresql_sql(
        source,
        destination_role="pasarguard",
    )
    assert "secret" not in transformed
    assert "other-secret" not in transformed
    assert "legacy-admin-secret" not in transformed
    assert 'CREATE ROLE legacy_admin WITH LOGIN;' in transformed
    assert removed == 1
    assert suppressed == 1
