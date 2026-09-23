import pytest\n\nfrom app.migration.compatibility import TimescaleCompatibility
from app.migration.timescale import (
    TIMESCALE_FIRST_RELID,
    TIMESCALE_LAST_SCHEMA_NAME,
    build_restore_spec,
    choose_timescale_version,
    filter_timescaledb_ddl_line,
)


def test_pre_229_catalog_uses_exact_source_version():
    compatibility = TimescaleCompatibility(
        versions=("2.28.2",),
        source_version="2.28.2",
        catalog_era="schema_name",
        recommended_version="2.28.3",
    )
    assert choose_timescale_version(compatibility, live_version="2.29.0") == "2.28.2"


def test_relid_catalog_rejects_internally_inconsistent_old_version():
    compatibility = TimescaleCompatibility(
        versions=("2.28.3",),
        catalog_era="relid",
        recommended_version="2.29.0",
    )
    with pytest.raises(ValueError, match="relid catalog"):
        choose_timescale_version(compatibility, live_version="2.29.0")


def test_source_newer_than_production_is_blocked():
    compatibility = TimescaleCompatibility(
        versions=("2.30.0",),
        catalog_era="relid",
        recommended_version="2.30.0",
    )
    with pytest.raises(ValueError, match="newer than destination"):
        choose_timescale_version(compatibility, live_version="2.29.0")


def test_build_restore_spec_marks_version_alignment():
    compatibility = TimescaleCompatibility(
        versions=("2.28.2",),
        source_version="2.28.2",
        catalog_era="schema_name",
        recommended_version="2.28.3",
    )
    spec = build_restore_spec(compatibility, live_version="2.29.0", pg_major=16)
    assert spec.target_version == "2.28.2"
    assert spec.image_tag == "2.28.2-pg16"
    assert spec.conversion_required is True


def test_timescale_extension_ddl_is_filtered():
    assert filter_timescaledb_ddl_line("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    assert filter_timescaledb_ddl_line("DROP EXTENSION timescaledb;")
    assert not filter_timescaledb_ddl_line("CREATE TABLE users (id bigint);")


def test_relid_boundary_is_229():
    assert TIMESCALE_FIRST_RELID == (2, 29, 0)


def test_unknown_exact_source_version_is_rejected():
    compatibility = TimescaleCompatibility(
        versions=(),
        catalog_era="schema_name",
        recommended_version="2.28.3",
    )
    with pytest.raises(ValueError, match="Exact TimescaleDB source version"):
        choose_timescale_version(compatibility, live_version="2.29.0")
