import pytest

from app.migration.portable_bridge import (
    DIMENSIONS_QUERY,
    ContinuousAggregateMetadata,
    HypertableDimension,
    HypertableMetadata,
    TimescalePolicyMetadata,
    build_continuous_aggregate_sql,
    build_hypertable_sql,
    build_pg_dump_data_args,
    build_policy_sql,
    build_portable_bridge_artifacts,
    build_portable_plan,
    render_hypertable_sql,
    render_post_data_sql,
    render_recreate_sql,
)


def test_dimensions_query_excludes_continuous_aggregate_materialization_hypertables():
    assert "materialization_hypertable_schema" in DIMENSIONS_QUERY
    assert "materialization_hypertable_name" in DIMENSIONS_QUERY
    assert "NOT EXISTS" in DIMENSIONS_QUERY


def test_hypertable_recreation_uses_public_metadata_only():
    hypertable = HypertableMetadata(
        schema="public",
        name="metrics",
        dimensions=(
            HypertableDimension(
                column_name="time",
                dimension_type="Time",
                time_interval="1 day",
            ),
            HypertableDimension(
                column_name="device_id",
                dimension_type="Space",
                num_partitions=4,
            ),
        ),
    )
    sql = build_hypertable_sql(hypertable)
    assert "create_hypertable" in sql[0]
    assert "by_range('time', INTERVAL '1 day')" in sql[0]
    assert "add_dimension" in sql[1]
    assert "_timescaledb_catalog" not in "\n".join(sql)


def test_integer_time_dimension_is_preserved():
    hypertable = HypertableMetadata(
        schema="public",
        name="usage",
        dimensions=(
            HypertableDimension(
                column_name="bucket",
                dimension_type="Time",
                integer_interval=3600000,
            ),
        ),
    )
    assert "by_range('bucket', 3600000)" in build_hypertable_sql(hypertable)[0]


def test_cagg_recreation_is_portable():
    cagg = ContinuousAggregateMetadata(
        schema="public",
        name="daily_usage",
        view_definition="SELECT time_bucket('1 day', time) AS bucket, count(*) FROM usage GROUP BY bucket",
        materialized_only=True,
        finalized=True,
    )
    sql = build_continuous_aggregate_sql(cagg)
    assert "CREATE MATERIALIZED VIEW" in sql[0]
    assert "WITH NO DATA" in sql[0]
    assert "refresh_continuous_aggregate('public.daily_usage', NULL, NULL)" in sql[1]
    assert 'refresh_continuous_aggregate("public"."daily_usage"' not in sql[1]
    assert "_timescaledb_internal" not in "\n".join(sql)


def test_supported_policies_render_without_internal_catalog_ids():
    policy = TimescalePolicyMetadata(
        relation_schema="public",
        relation_name="usage",
        proc_name="policy_retention",
        schedule_interval="1 day",
        config={"drop_after": "30 days", "hypertable_id": 12},
    )
    sql = build_policy_sql(policy)
    assert "add_retention_policy" in sql
    assert "hypertable_id" not in sql


def test_unknown_policy_is_fail_closed():
    policy = TimescalePolicyMetadata(
        relation_schema="public",
        relation_name="usage",
        proc_name="policy_custom",
        schedule_interval="1 day",
        config={},
    )
    with pytest.raises(ValueError, match="Unsupported Timescale policy"):
        build_policy_sql(policy)


def test_portable_plan_rejects_non_downgrade_case():
    with pytest.raises(ValueError, match="only required"):
        build_portable_plan(
            source_version="2.28.2",
            target_version="2.29.0",
            hypertable_rows=[],
            dimension_rows=[],
            continuous_aggregate_rows=[],
            policy_rows=[],
        )


def test_portable_plan_rejects_old_cagg_target():
    with pytest.raises(ValueError, match="2.7"):
        build_portable_plan(
            source_version="2.30.0",
            target_version="2.6.0",
            hypertable_rows=[],
            dimension_rows=[],
            continuous_aggregate_rows=[],
            policy_rows=[],
        )


def test_portable_plan_tracks_cagg_exclusions():
    plan = build_portable_plan(
        source_version="2.30.0",
        target_version="2.29.0",
        hypertable_rows=[{"hypertable_schema": "public", "hypertable_name": "usage"}],
        dimension_rows=[
            {
                "hypertable_schema": "public",
                "hypertable_name": "usage",
                "dimension_number": 1,
                "column_name": "time",
                "dimension_type": "Time",
                "time_interval": "1 day",
                "integer_interval": None,
                "num_partitions": None,
            }
        ],
        continuous_aggregate_rows=[
            {
                "view_schema": "public",
                "view_name": "daily_usage",
                "view_definition": "SELECT 1",
                "materialized_only": True,
                "finalized": True,
            }
        ],
        policy_rows=[],
    )
    assert plan.excluded_tables == ("public.daily_usage",)


def test_dump_plan_excludes_timescale_internal_schemas_and_caggs():
    args = build_pg_dump_data_args(
        database="source_db",
        excluded_tables=("public.daily_usage",),
    )
    joined = " ".join(args)
    assert "--data-only" in joined
    assert "--exclude-schema=_timescaledb_catalog" in joined
    assert "--exclude-extension=timescaledb" in joined
    assert "--exclude-table=public.daily_usage" in joined


def test_rendered_plan_analyzes_data_after_rebuild():
    plan = build_portable_plan(
        source_version="2.30.0",
        target_version="2.29.0",
        hypertable_rows=[],
        dimension_rows=[],
        continuous_aggregate_rows=[],
        policy_rows=[],
    )
    assert render_recreate_sql(plan).rstrip().endswith("ANALYZE;")


def test_bridge_artifacts_are_written_from_source_metadata(monkeypatch, tmp_path):
    import app.migration.portable_bridge as bridge

    monkeypatch.setattr(
        bridge,
        "_read_source_metadata",
        lambda url: None,
    )

    async def fake_read(_url):
        return (
            [{"hypertable_schema": "public", "hypertable_name": "usage"}],
            [
                {
                    "hypertable_schema": "public",
                    "hypertable_name": "usage",
                    "dimension_number": 1,
                    "column_name": "time",
                    "dimension_type": "Time",
                    "time_interval": "1 day",
                    "integer_interval": None,
                    "num_partitions": None,
                }
            ],
            [],
            [],
        )

    monkeypatch.setattr(bridge, "_read_source_metadata", fake_read)
    plan = build_portable_bridge_artifacts(
        "postgresql://unused",
        source_version="2.30.0",
        target_version="2.29.0",
        output_dir=tmp_path,
    )
    assert plan.hypertables
    assert (tmp_path / "portable-plan.json").exists()
    assert "create_hypertable" in (tmp_path / "portable-hypertables.sql").read_text()
    assert (tmp_path / "portable-post-data.sql").read_text().endswith("ANALYZE;\n")


def test_bridge_recreation_is_ordered_around_data():
    plan = build_portable_plan(
        source_version="2.30.0",
        target_version="2.29.0",
        hypertable_rows=[{"hypertable_schema": "public", "hypertable_name": "usage"}],
        dimension_rows=[
            {
                "hypertable_schema": "public",
                "hypertable_name": "usage",
                "dimension_number": 1,
                "column_name": "time",
                "dimension_type": "Time",
                "time_interval": "1 day",
                "integer_interval": None,
                "num_partitions": None,
            }
        ],
        continuous_aggregate_rows=[],
        policy_rows=[],
    )
    assert "create_hypertable" in render_hypertable_sql(plan)
    assert "ANALYZE;" in render_post_data_sql(plan)
    assert render_recreate_sql(plan).startswith(render_hypertable_sql(plan))
