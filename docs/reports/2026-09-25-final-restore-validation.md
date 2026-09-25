# Restore / Migration Validation — 2026-09-25

## Scope

Feature branch: `feature/amnezia-wg`.

Production cutover/apply was not executed.

## Gates

- Real backup `--check`: PASS; exit code 0.
- Real staging restore: PASS; isolated source-compatible TimescaleDB runtime.
- Durable row validation: PASS; admins=42, core_configs=9, groups=19, hosts=30, inbounds=28, nodes=7, user_templates=0, users=2147.
- Foreign keys: PASS; 22 public foreign keys validated.
- Public sequences: PASS; 26 sequences validated.
- Identity columns: PASS; 0 identity columns.
- Hypertables/CAGGs: PASS; source backup catalog contained 0/0 and target metadata matched the backup catalog.
- Alembic/schema version: PASS; `awg2026091901`.
- Timescale compatibility: PASS; isolated upgrade and disposable PG17/Timescale 2.30.0 -> PG16/Timescale 2.29.2 portable bridge E2E passed.
- Bridge integrity: PASS; devices=3, usage=48, hypertable usage=48 on both sides, CAGG=48.
- Migration suite: PASS; 86 tests passed.
- Ruff lint/format: PASS.
- Staging logical dump/integrity: PASS; validated staging dump completed and integrity marker was present.
- Disposable rollback: PASS; cutover rename/rollback simulation restored the original database name and preserved validation markers.
- Clean image artifact: PASS; `/code/dashboard/build/index.html` exists and is non-empty.
- Clean image import: PASS; `import app`.
- Clean disposable runtime health: PASS; `/health` returned `{"status":"ok"}`.

## Production Safety

Production database was not modified by these gates. No `--apply` was executed.

## Remaining

The production `--apply` cutover remains intentionally unexecuted. The Restore/Migration gates are checkpointed; the next project phase is Domains & SSL Intelligence according to the roadmap, without performing production cutover in this checkpoint.
