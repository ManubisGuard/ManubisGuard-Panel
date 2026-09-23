from app.migration.compatibility import (
    analyze_timescale_sql,
    classify_restore_error,
    version_lt,
)


def test_old_timescale_catalog_is_detected():
    result = analyze_timescale_sql(
        '''
        COPY _timescaledb_catalog.chunk (id, schema_name, table_name) FROM stdin;
        1 public users
        \\.
        '''
    )
    assert result.catalog_era == "schema_name"
    assert result.recommended_version == "2.28.3"
    assert result.minimum_version == "2.28.3"
    assert result.warnings


def test_new_timescale_catalog_is_detected():
    result = analyze_timescale_sql(
        'COPY _timescaledb_catalog.chunk (id, relid) FROM stdin;'
    )
    assert result.catalog_era == "relid"
    assert result.recommended_version == "2.29.0"


def test_timescale_version_comparison_is_numeric():
    assert version_lt("2.9.0", "2.29.0")
    assert not version_lt("2.29.0", "2.9.0")


def test_restore_error_classification():
    assert classify_restore_error("password authentication failed for user postgres") == "authentication"
    assert classify_restore_error(
        'ERROR: column "schema_name" of relation "chunk" does not exist'
    ) == "timescaledb_catalog_mismatch"
    assert classify_restore_error("ERROR: could not extend file: No space left on device") == "disk_full"
