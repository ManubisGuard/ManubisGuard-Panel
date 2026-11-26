# P01 Backup integrity acceptance checkpoint

Scope: staging source `/opt/manubisguard-panel` on CLY606677 only. Do not copy production data or contact live nodes. This checkpoint does not approve any production restore.

## Safety requirements
- [x] PostgreSQL 17 newer dump trailers accepted only with matching restrict/unrestrict markers and a completion marker.
- [x] Duplicate uploads cannot overwrite previously imported archives.
- [x] Oversized uploads remove only the newly created temporary file.
- [x] Files outside the configured backup root cannot be deleted by the backup API.
- [x] Failed database commit cannot remove the archived backup.
- [x] Only scheduled backups are eligible for automatic retention, never manual uploads.
- [x] Telegram delivery failure does not block the next local backup; unsuccessful retry is throttled for one hour.
- [x] PostgreSQL password excluded from the process argument list (via child environment).
- [x] Blocking pg_dump and zip operations moved off the event loop.
- [x] Production and in-app staging restore endpoints remain fail-closed.
- [x] Synthetic PostgreSQL 16 and 17 -> network-disconnected TimescaleDB restore round-trip, including exact fixture data checks.
- [x] Database export now streams through private disk files and ZIP input, preventing a multi-GB RAM copy.
- [ ] GitHub CI and code review of the submitted pull request.

## Evidence
- `tests/test_backup_safety_phase1.py`
- `tests/migration/test_backup_payload.py`
- `tests/test_backup_restore_fail_closed.py`
- `tests/migration/test_backup_restore.py`
- `tests/test_native_backup_architecture.py`
- `scripts/qa-p01-isolated-roundtrip.sh` (PG16/PG17, no network, tmpfs-only)
- Test logs under `/var/log/manubis-p01-*` on staging.

## Non-goals
No production deployment, database migration, live restore, live Telegram delivery, or disabling the protective restore guard.
