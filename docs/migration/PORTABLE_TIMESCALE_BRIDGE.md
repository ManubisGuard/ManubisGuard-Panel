# Portable Timescale Bridge

This bridge is used only when the source TimescaleDB version is newer than the
destination version. It deliberately does not downgrade the destination
extension and does not restore Timescale internal catalogs.

## Source metadata

The source-compatible Timescale runtime is queried through the documented
informational views:

- `timescaledb_information.hypertables`
- `timescaledb_information.dimensions`
- `timescaledb_information.continuous_aggregates`
- `timescaledb_information.jobs`

Only public-facing metadata is retained. Internal hypertable/chunk IDs are
never copied.

## Portable transfer order

1. Restore the source backup only into an isolated source-compatible runtime.
2. Dump PostgreSQL schema with Timescale extension/internal schemas excluded.
3. Restore that relational schema into a destination-compatible Timescale runtime.
4. Recreate hypertables and dimensions with the public Timescale APIs.
5. Dump and restore user-table data after hypertables exist.
6. Recreate continuous aggregates with `WITH NO DATA`, then refresh them.
7. Recreate supported retention/refresh/compression/reorder policies.
8. Run `ANALYZE`.
9. Validate table row counts and Timescale metadata before cutover.

PostgreSQL documents `--schema-only`, `--data-only`, `--exclude-schema`,
`--exclude-table`, and `--exclude-extension` for separating this logical
transfer. The source database must be treated as untrusted input.

The bridge intentionally fails closed for unsupported policy types or missing
metadata. It does not fabricate Timescale objects or replay `_timescaledb_*`
catalog rows.
