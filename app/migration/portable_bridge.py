from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import asyncpg

from app.migration.async_utils import run_async


@dataclass(frozen=True)
class HypertableDimension:
    column_name: str
    dimension_type: str
    time_interval: str | None = None
    integer_interval: int | None = None
    num_partitions: int | None = None


@dataclass(frozen=True)
class HypertableMetadata:
    schema: str
    name: str
    dimensions: tuple[HypertableDimension, ...]


@dataclass(frozen=True)
class ContinuousAggregateMetadata:
    schema: str
    name: str
    view_definition: str
    materialized_only: bool
    finalized: bool


@dataclass(frozen=True)
class TimescalePolicyMetadata:
    relation_schema: str
    relation_name: str
    proc_name: str
    schedule_interval: str | None
    config: Mapping[str, Any]


@dataclass(frozen=True)
class PortableTimescalePlan:
    source_version: str
    target_version: str
    hypertables: tuple[HypertableMetadata, ...]
    continuous_aggregates: tuple[ContinuousAggregateMetadata, ...]
    policies: tuple[TimescalePolicyMetadata, ...]
    excluded_tables: tuple[str, ...]
    warnings: tuple[str, ...] = ()


# TimescaleDB 2.30 removed is_distributed from this public information view.
# Filtering on that column caused UndefinedColumnError during portable restores.
# Distributed hypertables are no longer exposed through this public hypertable view,
# so the stable schema/name columns are sufficient here.
HYPERTABLES_QUERY = """
SELECT hypertable_schema, hypertable_name
FROM timescaledb_information.hypertables
ORDER BY hypertable_schema, hypertable_name
"""

DIMENSIONS_QUERY = """
SELECT hypertable_schema, hypertable_name, dimension_number, column_name,
       dimension_type, time_interval, integer_interval, num_partitions
FROM timescaledb_information.dimensions
ORDER BY hypertable_schema, hypertable_name, dimension_number
"""

CONTINUOUS_AGGREGATES_QUERY = """
SELECT view_schema, view_name, view_definition, materialized_only,
       COALESCE((to_jsonb(cagg)->>'finalized')::boolean, true) AS finalized
FROM timescaledb_information.continuous_aggregates AS cagg
ORDER BY view_schema, view_name
"""

POLICIES_QUERY = """
SELECT hypertable_schema, hypertable_name, proc_name,
       schedule_interval::text, config
FROM timescaledb_information.jobs
WHERE proc_name LIKE 'policy_%'
  AND hypertable_schema IS NOT NULL
  AND hypertable_schema NOT LIKE '_timescaledb%'
ORDER BY hypertable_schema, hypertable_name, proc_name
"""

_SUPPORTED_POLICIES = {
    "policy_retention",
    "policy_refresh_continuous_aggregate",
    "policy_compression",
    "policy_reorder",
}


def _quote_ident(value: str) -> str:
    if not value:
        raise ValueError("Identifier must not be empty.")
    return '"' + value.replace('"', '""') + '"'


def _qualified(schema: str, name: str) -> str:
    return f"{_quote_ident(schema)}.{_quote_ident(name)}"


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _dimension_value(value: Any) -> str:
    if isinstance(value, bool):
        raise TypeError("Boolean dimension interval is invalid.")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError("Fractional integer dimension interval is invalid.")
        return str(int(value))
    text = str(value).strip()
    if not text:
        raise ValueError("Dimension interval must not be empty.")
    return f"INTERVAL {_sql_string(text)}"


def _parse_config(value: Any) -> Mapping[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise TypeError("Timescale policy config must be a JSON object.")
        return parsed
    raise TypeError("Unsupported Timescale policy config type.")


def collect_hypertables(
    hypertable_rows: Sequence[Mapping[str, Any]],
    dimension_rows: Sequence[Mapping[str, Any]],
) -> tuple[HypertableMetadata, ...]:
    grouped: dict[tuple[str, str], list[tuple[int, HypertableDimension]]] = {}
    known = {
        (str(row["hypertable_schema"]), str(row["hypertable_name"]))
        for row in hypertable_rows
    }
    for row in dimension_rows:
        key = (str(row["hypertable_schema"]), str(row["hypertable_name"]))
        if key not in known:
            raise ValueError(f"Dimension references unknown hypertable: {key[0]}.{key[1]}")
        grouped.setdefault(key, []).append(
            (
                int(row.get("dimension_number") or 0),
                HypertableDimension(
                    column_name=str(row["column_name"]),
                    dimension_type=str(row["dimension_type"]),
                    time_interval=(
                        str(row["time_interval"])
                        if row.get("time_interval") is not None
                        else None
                    ),
                    integer_interval=(
                        int(row["integer_interval"])
                        if row.get("integer_interval") is not None
                        else None
                    ),
                    num_partitions=(
                        int(row["num_partitions"])
                        if row.get("num_partitions") is not None
                        else None
                    ),
                ),
            )
        )

    result: list[HypertableMetadata] = []
    for schema, name in sorted(known):
        dimensions = tuple(
            item
            for _, item in sorted(grouped.get((schema, name), ()), key=lambda pair: pair[0])
        )
        if not dimensions:
            raise ValueError(f"Hypertable has no portable dimension metadata: {schema}.{name}")
        result.append(HypertableMetadata(schema, name, dimensions))
    return tuple(result)


def collect_continuous_aggregates(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[ContinuousAggregateMetadata, ...]:
    result = []
    for row in rows:
        definition = str(row.get("view_definition") or "").strip()
        if not definition:
            raise ValueError(
                f"Continuous aggregate has no view definition: "
                f"{row.get('view_schema')}.{row.get('view_name')}"
            )
        result.append(
            ContinuousAggregateMetadata(
                schema=str(row["view_schema"]),
                name=str(row["view_name"]),
                view_definition=definition,
                materialized_only=bool(row.get("materialized_only", True)),
                finalized=bool(row.get("finalized", True)),
            )
        )
    return tuple(result)


def collect_policies(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[TimescalePolicyMetadata, ...]:
    result = []
    for row in rows:
        proc_name = str(row["proc_name"])
        if proc_name not in _SUPPORTED_POLICIES:
            raise ValueError(f"Unsupported Timescale policy: {proc_name}")
        result.append(
            TimescalePolicyMetadata(
                relation_schema=str(row["hypertable_schema"]),
                relation_name=str(row["hypertable_name"]),
                proc_name=proc_name,
                schedule_interval=(
                    str(row["schedule_interval"])
                    if row.get("schedule_interval") is not None
                    else None
                ),
                config=_parse_config(row.get("config")),
            )
        )
    return tuple(result)


def build_hypertable_sql(hypertable: HypertableMetadata) -> tuple[str, ...]:
    dimensions = hypertable.dimensions
    if not dimensions:
        raise ValueError(f"Hypertable has no dimensions: {hypertable.schema}.{hypertable.name}")
    primary = dimensions[0]
    if primary.dimension_type.lower() != "time":
        raise ValueError(
            f"Primary hypertable dimension must be time based: "
            f"{hypertable.schema}.{hypertable.name}"
        )

    primary_args = [_sql_string(primary.column_name)]
    if primary.time_interval is not None:
        primary_args.append(_dimension_value(primary.time_interval))
    elif primary.integer_interval is not None:
        primary_args.append(str(primary.integer_interval))

    statements = [
        "SELECT create_hypertable("
        + _sql_string(f"{hypertable.schema}.{hypertable.name}")
        + ", by_range("
        + ", ".join(primary_args)
        + "), if_not_exists => true);"
    ]

    for dimension in dimensions[1:]:
        if dimension.dimension_type.lower() == "space":
            if not dimension.num_partitions or dimension.num_partitions < 1:
                raise ValueError(
                    f"Space dimension has invalid partition count: "
                    f"{hypertable.schema}.{hypertable.name}.{dimension.column_name}"
                )
            builder = (
                f"by_hash({_sql_string(dimension.column_name)}, "
                f"{dimension.num_partitions})"
            )
        elif dimension.dimension_type.lower() == "time":
            args = [_sql_string(dimension.column_name)]
            if dimension.time_interval is not None:
                args.append(_dimension_value(dimension.time_interval))
            elif dimension.integer_interval is not None:
                args.append(str(dimension.integer_interval))
            builder = f"by_range({', '.join(args)})"
        else:
            raise ValueError(
                f"Unsupported Timescale dimension type: {dimension.dimension_type}"
            )
        statements.append(
            f"SELECT add_dimension({_sql_string(f'{hypertable.schema}.{hypertable.name}')}, "
            f"{builder}, if_not_exists => true);"
        )
    return tuple(statements)


def build_continuous_aggregate_sql(cagg: ContinuousAggregateMetadata) -> tuple[str, ...]:
    options = [
        "timescaledb.continuous",
        f"timescaledb.materialized_only={str(cagg.materialized_only).lower()}",
        f"timescaledb.finalized={str(cagg.finalized).lower()}",
    ]
    view = _qualified(cagg.schema, cagg.name)
    definition = cagg.view_definition.strip().rstrip(";")
    return (
        (
            f"CREATE MATERIALIZED VIEW {view} WITH ({', '.join(options)}) "
            f"AS {definition} WITH NO DATA;"
        ),
        f"CALL refresh_continuous_aggregate({view}, NULL, NULL);",
    )


def _policy_arg(value: Any) -> str:
    if isinstance(value, bool):
        raise TypeError("Boolean policy interval is invalid.")
    if isinstance(value, int):
        return str(value)
    text = str(value).strip()
    if not text:
        raise ValueError("Policy interval must not be empty.")
    return f"INTERVAL {_sql_string(text)}"


def build_policy_sql(policy: TimescalePolicyMetadata) -> str:
    relation = _qualified(policy.relation_schema, policy.relation_name)
    config = dict(policy.config)
    schedule = policy.schedule_interval
    if schedule and schedule.strip().startswith("@ "):
        schedule = schedule.strip()[2:].strip()

    if policy.proc_name == "policy_retention":
        key = "drop_after" if "drop_after" in config else "drop_created_before"
        if key not in config:
            raise ValueError("Retention policy has no supported retention interval.")
        args = [f"{key} => {_policy_arg(config[key])}"]
        if schedule:
            args.append(f"schedule_interval => INTERVAL {_sql_string(schedule)}")
        return f"SELECT add_retention_policy({relation}, {', '.join(args)});"

    if policy.proc_name == "policy_refresh_continuous_aggregate":
        required = ("start_offset", "end_offset")
        if any(key not in config for key in required):
            raise ValueError("Continuous aggregate refresh policy is missing offsets.")
        args = [
            f"start_offset => {_policy_arg(config['start_offset'])}",
            f"end_offset => {_policy_arg(config['end_offset'])}",
        ]
        if schedule:
            args.append(f"schedule_interval => INTERVAL {_sql_string(schedule)}")
        return f"SELECT add_continuous_aggregate_policy({relation}, {', '.join(args)});"

    if policy.proc_name == "policy_compression":
        key = "compress_after" if "compress_after" in config else "compress_created_before"
        if key not in config:
            raise ValueError("Compression policy has no supported threshold.")
        args = [f"{key} => {_policy_arg(config[key])}"]
        if schedule:
            args.append(f"schedule_interval => INTERVAL {_sql_string(schedule)}")
        return f"SELECT add_compression_policy({relation}, {', '.join(args)});"

    if policy.proc_name == "policy_reorder":
        index_name = config.get("index_name")
        if not index_name:
            raise ValueError("Reorder policy has no index_name.")
        return (
            f"SELECT add_reorder_policy({relation}, "
            f"{_sql_string(str(index_name))});"
        )

    raise ValueError(f"Unsupported Timescale policy: {policy.proc_name}")


def build_portable_plan(
    *,
    source_version: str,
    target_version: str,
    hypertable_rows: Sequence[Mapping[str, Any]],
    dimension_rows: Sequence[Mapping[str, Any]],
    continuous_aggregate_rows: Sequence[Mapping[str, Any]],
    policy_rows: Sequence[Mapping[str, Any]],
) -> PortableTimescalePlan:
    from app.migration.compatibility import version_tuple

    source = version_tuple(source_version)
    target = version_tuple(target_version)
    if source is None or target is None:
        raise ValueError("Portable bridge requires valid source and target Timescale versions.")
    if source <= target:
        raise ValueError(
            "Portable Timescale bridge is only required when source TimescaleDB is newer "
            "than the destination."
        )
    if target < (2, 7, 0):
        raise ValueError(
            "Portable continuous-aggregate reconstruction requires TimescaleDB 2.7 or newer."
        )

    hypertables = collect_hypertables(hypertable_rows, dimension_rows)
    caggs = collect_continuous_aggregates(continuous_aggregate_rows)
    policies = collect_policies(policy_rows)
    excluded = tuple(sorted(f"{item.schema}.{item.name}" for item in caggs))
    return PortableTimescalePlan(
        source_version=source_version,
        target_version=target_version,
        hypertables=hypertables,
        continuous_aggregates=caggs,
        policies=policies,
        excluded_tables=excluded,
        warnings=(
            (
                "Timescale internal schemas/catalogs are excluded; only public/user-facing "
                "metadata is used to reconstruct Timescale objects."
            ),
            (
                "Continuous aggregate materialization data is rebuilt by a full refresh; "
                "historical rows deleted from source hypertables are not implicitly preserved."
            ),
        ),
    )


def render_hypertable_sql(plan: PortableTimescalePlan) -> str:
    statements: list[str] = []
    for hypertable in plan.hypertables:
        statements.extend(build_hypertable_sql(hypertable))
    return "\n".join(statements) + ("\n" if statements else "")


def render_post_data_sql(plan: PortableTimescalePlan) -> str:
    statements: list[str] = []
    for cagg in plan.continuous_aggregates:
        statements.extend(build_continuous_aggregate_sql(cagg))
    for policy in plan.policies:
        statements.append(build_policy_sql(policy))
    statements.append("ANALYZE;")
    return "\n".join(statements) + "\n"


def render_recreate_sql(plan: PortableTimescalePlan) -> str:
    return render_hypertable_sql(plan) + render_post_data_sql(plan)


async def _read_source_metadata(database_url: str) -> tuple[
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
]:
    connection = await asyncpg.connect(database_url)
    try:
        async def rows(query: str) -> list[Mapping[str, Any]]:
            records = await connection.fetch(query)
            return [dict(record) for record in records]

        return (
            await rows(HYPERTABLES_QUERY),
            await rows(DIMENSIONS_QUERY),
            await rows(CONTINUOUS_AGGREGATES_QUERY),
            await rows(POLICIES_QUERY),
        )
    finally:
        await connection.close()


def build_portable_bridge_artifacts(
    database_url: str,
    *,
    source_version: str,
    target_version: str,
    output_dir: str | Path,
) -> PortableTimescalePlan:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (
        hypertable_rows,
        dimension_rows,
        cagg_rows,
        policy_rows,
    ) = run_async(_read_source_metadata(database_url))
    plan = build_portable_plan(
        source_version=source_version,
        target_version=target_version,
        hypertable_rows=hypertable_rows,
        dimension_rows=dimension_rows,
        continuous_aggregate_rows=cagg_rows,
        policy_rows=policy_rows,
    )
    (output / "portable-plan.json").write_text(
        json.dumps(asdict(plan), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    (output / "portable-hypertables.sql").write_text(
        render_hypertable_sql(plan),
        encoding="utf-8",
    )
    (output / "portable-post-data.sql").write_text(
        render_post_data_sql(plan),
        encoding="utf-8",
    )
    (output / "portable-exclude-tables.txt").write_text(
        "".join(f"{table}\n" for table in plan.excluded_tables),
        encoding="utf-8",
    )
    return plan


def build_pg_dump_args(
    *,
    database: str,
    excluded_tables: Sequence[str] = (),
) -> tuple[str, ...]:
    args = [
        "pg_dump",
        "--format=plain",
        "--quote-all-identifiers",
        "--no-owner",
        "--no-privileges",
        "--no-tablespaces",
        f"--dbname={database}",
        "--exclude-extension=timescaledb",
        "--exclude-schema=_timescaledb_internal",
        "--exclude-schema=_timescaledb_catalog",
        "--exclude-schema=_timescaledb_config",
    ]
    args.extend(f"--exclude-table={table}" for table in excluded_tables)
    return tuple(args)


def build_pg_dump_data_args(
    *,
    database: str,
    excluded_tables: Sequence[str] = (),
) -> tuple[str, ...]:
    return (
        *build_pg_dump_args(database=database, excluded_tables=excluded_tables),
        "--data-only",
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build a portable TimescaleDB bridge plan.")
    database_group = parser.add_mutually_exclusive_group(required=True)
    database_group.add_argument("--database-url")
    database_group.add_argument("--database-url-env")
    parser.add_argument("--source-version", required=True)
    parser.add_argument("--target-version", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    import os

    database_url = (
        args.database_url
        if args.database_url is not None
        else os.environ.get(args.database_url_env, "")
    )
    if not database_url:
        parser.error("database URL environment variable is empty")

    plan = build_portable_bridge_artifacts(
        database_url,
        source_version=args.source_version,
        target_version=args.target_version,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "source_version": plan.source_version,
                "target_version": plan.target_version,
                "hypertables": len(plan.hypertables),
                "continuous_aggregates": len(plan.continuous_aggregates),
                "policies": len(plan.policies),
                "excluded_tables": list(plan.excluded_tables),
                "warnings": list(plan.warnings),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
