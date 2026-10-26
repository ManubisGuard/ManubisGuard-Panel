# AmneziaWG Backup Coverage Matrix

Date: 2026-10-26
Scope: native panel archive and panel-side records required to reconstruct AWG configuration. This audit is read-only with respect to production data. Remote Node/N2 hosts were not accessed or modified.

## Coverage matrix

| Data or asset | Source of truth | Archive coverage | Evidence / limits |
|---|---|---|---|
| Core protocol type and AWG2.x config | core_configs.type and core_configs.config JSON | Included in the configured application DB dump | Native PostgreSQL path uses a database dump, not an AWG-specific field export. All 16 code-defined fields were checked in a native backup/restore round-trip. |
| Node/Core assignment | nodes.core_config_id and nodes.core_config_ids | Included in the configured application DB dump | The focused native fixture verified the single-core foreign-key relationship after restore. The full multi-core list remains covered by generic DB dump semantics, not by this minimal fixture. |
| Panel-side Node connection record | nodes.address, ports, api_key, server_ca, connection settings | Included when the configured application DB is captured | These fields live on the panel-side Node row. They can make an archive sensitive. They are distinct from secrets/state stored only on the remote Node host. |
| Per-user WG peer identity and addresses | users.proxy_settings (wireguard.private_key, public_key, peer_ips) | Included by the full application DB dump | Source-level coverage verified; user peer rows were not present in the minimal round-trip fixture. |
| Host/inbound subscription settings | hosts.wireguard_overrides, hosts.inbound_tag, inbounds, host/group associations | Included by the full application DB dump | Source-level coverage verified; these related rows were not present in the minimal round-trip fixture. |
| WG/AWG IP allocator | wireguard_subnets.network, next_offset, free_offsets | Included by the full application DB dump | Source-level coverage verified; allocator rows were not present in the minimal round-trip fixture. |
| Other application tables | Remaining schema/data in the configured application DB | Included by the logical database dump | No table-level exclusion exists in the native pg_dump command. The test fixture is intentionally smaller than the real panel schema. |
| Application files and configuration | APP_DIR=/opt/pasarguard | Generally included | The app directory is copied except the backup directory and generated dump/restore metadata. Destination .env and Compose file are preserved by normal in-place restore semantics. |
| Panel persistent data | DATA_DIR=/var/lib/pasarguard | Generally included | Copied to pasarguard_data/, excluding top-level xray-core, mysql, mariadb, postgresql, and timescaledb directories. Database storage is handled as a SQL dump instead. |
| Remote Node runtime config/state and Node-local secrets | Node host, documented default state path /var/lib/pg-node/ | Not included | This is outside panel APP_DIR/DATA_DIR. A separate host-local recovery procedure is required for each Node. N2/production Node was not accessed during this audit. |
| Node-installed AWG/kernel/userspace binaries and host packages | Remote Node OS/package manager | Not guaranteed | Do not assume the panel archive reconstructs OS packages, kernel modules or runtime binaries. Capture exact AWG2.x prerequisites in a separate Node recovery runbook. |
| External host configuration | /etc/letsencrypt, Nginx vhosts, firewall and routing | Not included | These paths are outside the panel directories and need separate backups if required by the recovery objective. |

## Database archive integrity caveat

The native TimescaleDB/PostgreSQL path attempts to dump every connectable, non-template user database and records a manifest. If multi-database collection fails, the engine can fall back to a single configured application database. For systems with more than one required database, inspect pg_dump/manifest.tsv and verify every required database is present. This audit did not query production data to infer the production database count.

## Stage 2 validation completed

- Expanded tests/test_core_persistence.py to use AWG_OBFUSCATION_FIELDS, the code-defined set of 16 keys: jc, jmin, jmax, s1-s4, h1-h4, i1-i5.
- Focused tests tests/test_core_persistence.py, tests/test_amneziawg.py and tests/test_amneziawg_subscription_render.py: 16 passed; Ruff passed.
- Created native archive /opt/manubisguard-work/awg-native-roundtrip-20261026/stage2-backups/backup_20261026193255.zip from the disposable project. restore --check passed.
- Mutated the disposable DB, then ran Native Restore with explicit destination identity checks. The exact post-restore query matched all 16 lower-case AWG keys, core type and node/core relationship; mutated values were absent. Marker: NATIVE_AWG_16_FIELD_ROUNDTRIP=PASS.
- The initial native round-trip fixture directly covered core_configs and nodes, not users.proxy_settings, hosts/inbounds or wireguard_subnets. A follow-up disposable full-schema database rollback test now covers those related rows; details and the exact 11-row comparison are recorded below.

## Stage 3 validation completed (2026-10-27)

- Created the ORM schema in a disposable PostgreSQL/TimescaleDB test database (33 tables) using checked-out model metadata; no application migrations or production DB were touched.
- Inserted linked fixture rows for users.proxy_settings (including all 16 AWG keys and peer IPs), hosts.wireguard_overrides, hosts.inbound_tag, inbounds, groups, both inbound/group and user/group association tables, core_configs, nodes (single-core and multi-core assignment fields), and wireguard_subnets (allocator high-water mark and free list). All key material is synthetic and explicitly non-real.
- Captured a full pg_dump plus globals, manifest, SHA-256 inventory and safety marker; verified the snapshot before rollback. Then mutated the user peer IP, host and inbound link, all 16 core AWG config values/type, Node/Core assignment, subnet allocator state and both association links; also created an injected-failure table and temporary group.
- Ran manubisguard_rollback_restore_database_safety on the disposable database with different restore and administrative credential arguments. The first restore-credential attempt correctly lacked permission to write the public schema; the helper then used the separate administrative credential and restored the dump.
- Compared the post-rollback JSON representation of all 11 fixture rows against the pre-mutation baseline: exact match. The injected-failure table and mutated group were absent. Markers: AWG_LINKED_ROUNDTRIP=PASS, USER_PROXY_SETTINGS_EXACT=PASS, HOST_INBOUND_AND_WIREGUARD_OVERRIDES_EXACT=PASS, INBOUND_GROUP_AND_USER_GROUP_LINKS_EXACT=PASS, CORE_AWG_FIELDS_AND_NODE_CORE_ASSIGNMENT_EXACT=PASS, WIREGUARD_SUBNET_ALLOCATOR_EXACT=PASS.
- This proves the PostgreSQL rollback helper restores full-schema/data relationships in the disposable fixture. In a second isolated test, the actual `restore_command --file ... --yes` flow was also run with service lifecycle functions mocked and a fault injected into the first database import: the DB was mutated, the import returned failure, cleanup invoked the real rollback helper, `DATABASE_ROLLBACK=PASS` was recorded, and the original row was restored while the injected table was absent. Evidence: `/opt/manubisguard-work/backup-restore-final-validation/restore-command-e2e.9IJh34/`.
- The expanded AWG fixture has been tested through the real database snapshot/rollback helper, but not yet as a full native archive/CLI round-trip. Remote Node host recovery is also still outside this panel-only test.

## Security caveat

A full panel archive can contain credentials and private keys from the database, the panel .env, and files under /var/lib/pasarguard. Treat it as a secret-bearing recovery artifact: restrict permissions, encrypt off-host copies, enforce retention, and store encryption keys separately from archives. Never include production credential values in fixtures or progress logs.

## Remaining work

1. Full-schema linked-row database rollback fixture is complete for users.proxy_settings, hosts/inbounds, association tables, core_configs/nodes and wireguard_subnets. A separate native archive/CLI round-trip of that same expanded fixture remains a follow-up.
2. Define and test a separate Node-host backup/restore procedure for /var/lib/pg-node and AWG runtime prerequisites before claiming full AWG disaster recovery. This must not silently change the native PasarGuard archive format or touch production/N2 during panel tests.
3. Complete the recovery safety work (destination safety backup, rollback path and explicit restore result verification) before considering activation of the production API endpoints.
