from io import StringIO

from app.migration.restore_safety import (
    prepare_postgresql_sql,
    prepare_postgresql_sql_stream,
    sanitize_role_password_line,
)


def test_role_password_is_removed():
    line = "ALTER ROLE pasarguard WITH LOGIN PASSWORD 'legacy-secret';"
    transformed, changed = sanitize_role_password_line(line)
    assert changed is True
    assert "PASSWORD" not in transformed.upper()
    assert "legacy-secret" not in transformed


def test_destination_role_statement_is_suppressed():
    line = "ALTER ROLE \"pasarguard\" WITH SUPERUSER LOGIN PASSWORD 'legacy-secret';"
    transformed, changed = sanitize_role_password_line(
        line,
        destination_role="pasarguard",
    )
    assert changed is True
    assert transformed == ""


def test_quoted_non_destination_role_keeps_non_password_attributes():
    line = "CREATE ROLE \"legacy_admin\" WITH LOGIN PASSWORD 'legacy-secret';"
    transformed, changed = sanitize_role_password_line(
        line,
        destination_role="pasarguard",
    )
    assert changed is True
    assert transformed == 'CREATE ROLE "legacy_admin" WITH LOGIN;'


def test_prepare_postgresql_sql_counts_transformations():
    source = (
        "-- PostgreSQL database cluster dump\n"
        "ALTER ROLE pasarguard WITH SUPERUSER LOGIN PASSWORD 'secret';\n"
        "ALTER ROLE \"pasarguard\" WITH CREATEDB PASSWORD 'other-secret';\n"
        "CREATE ROLE legacy_admin WITH LOGIN PASSWORD 'legacy-admin-secret';\n"
    )
    transformed, removed, suppressed = prepare_postgresql_sql(
        source,
        destination_role="pasarguard",
    )
    assert "secret" not in transformed
    assert "other-secret" not in transformed
    assert "legacy-admin-secret" not in transformed
    assert "CREATE ROLE legacy_admin WITH LOGIN;" in transformed
    assert removed == 1
    assert suppressed == 2


def test_stream_sanitizer_handles_realistic_globals_shape_without_loading_password():
    source = StringIO(
        "-- PostgreSQL database cluster dump\n"
        'CREATE ROLE "pasarguard";\n'
        "ALTER ROLE \"pasarguard\" WITH SUPERUSER LOGIN PASSWORD 'legacy-secret';\n"
        "CREATE ROLE \"legacy_admin\" WITH LOGIN PASSWORD 'other-secret';\n"
    )
    output = StringIO()
    removed, suppressed = prepare_postgresql_sql_stream(source, output, destination_role="pasarguard")
    transformed = output.getvalue()
    assert "legacy-secret" not in transformed
    assert "other-secret" not in transformed
    assert "pasarguard" not in transformed
    assert 'CREATE ROLE "legacy_admin" WITH LOGIN;' in transformed
    assert removed == 1
    assert suppressed == 2


def test_create_user_password_is_removed():
    transformed, removed, suppressed = prepare_postgresql_sql(
        "CREATE USER legacy WITH LOGIN PASSWORD 'secret';\n",
    )
    assert "secret" not in transformed
    assert removed == 1
    assert suppressed == 0


def test_multiline_role_password_is_removed():
    transformed, removed, suppressed = prepare_postgresql_sql(
        "ALTER ROLE legacy\nWITH LOGIN\nPASSWORD 'secret';\n",
    )
    assert "secret" not in transformed
    assert removed == 1
    assert suppressed == 0


def test_multiline_destination_user_statement_is_suppressed():
    transformed, removed, suppressed = prepare_postgresql_sql(
        "ALTER USER destination\nWITH LOGIN\nPASSWORD 'secret';\n",
        destination_role="destination",
    )
    assert transformed == ""
    assert removed == 0
    assert suppressed == 1


def test_owner_to_is_rewritten_to_destination_role():
    transformed, changed = sanitize_role_password_line(
        "ALTER TABLE public.users OWNER TO pasarguard;",
        destination_role="manubisguard",
    )
    assert changed is True
    assert transformed == "ALTER TABLE public.users OWNER TO manubisguard;"
