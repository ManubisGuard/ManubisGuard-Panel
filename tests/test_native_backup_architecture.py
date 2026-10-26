from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "pasarguard"
ADAPTER = ROOT / "scripts" / "manubisguard-native-backup.sh"
RESTORE_SAFETY = ROOT / "scripts" / "manubisguard-native-restore-safety.py"
INSTALLER = ROOT / "install-pasarguard.sh"


def test_native_restore_uses_the_pinned_pasarguard_engine():
    adapter = ADAPTER.read_text()
    cli = CLI.read_text()

    assert 'UPSTREAM_COMMIT="21f64e42e0cc2f9a7c4f633642e9b8f6365ea5a7"' in adapter
    assert 'restore) bash "$work/pasarguard.sh" restore "$@" ;;' in adapter
    assert 'backup) bash "$work/pasarguard.sh" backup "$@" ;;' in adapter
    assert 'exec /usr/local/bin/pasarguard-native-backup restore' in cli
    assert not (ROOT / "scripts" / "manubisguard-native-restore.py").exists()


def test_restore_options_are_forwarded_to_upstream_without_custom_validator():
    adapter = ADAPTER.read_text()
    cli = CLI.read_text()

    assert 'restore) bash "$work/pasarguard.sh" restore "$@" ;;' in adapter
    assert 'manubisguard-native-restore.py --apply' not in cli
    assert 'exec /usr/local/bin/pasarguard-migrate' in cli


def test_in_place_update_refuses_to_discard_tracked_local_edits():
    installer = INSTALLER.read_text()

    assert 'In-place update refused: tracked local changes exist' in installer
    assert 'git -C "$INSTALL_DIR" diff --quiet' in installer
    assert 'git -C "$INSTALL_DIR" diff --cached --quiet' in installer


def test_fresh_restore_has_an_installed_safety_patch_fallback():
    adapter = ADAPTER.read_text()
    installer = INSTALLER.read_text()
    cli = CLI.read_text()

    assert 'readonly SAFETY_PATCH_FALLBACK="$CACHE_DIR/pasarguard-restore-safety.py"' in adapter
    assert 'safety_patch="$SAFETY_PATCH_FALLBACK"' in adapter
    assert 'install -D -o root -g root -m 0644 "$INSTALL_DIR/scripts/manubisguard-native-restore-safety.py" /usr/local/lib/pasarguard-scripts/pasarguard-restore-safety.py' in installer
    assert 'PASARGUARD_SAFETY_HELPER_URL="https://raw.githubusercontent.com/ManubisGuard/ManubisGuard-Panel/feature/amnezia-wg/scripts/manubisguard-native-restore-safety.py"' in cli
    assert '"safety|$PASARGUARD_SAFETY_HELPER_URL|manubisguard-native-restore-safety.py"' in cli
    assert 'install -o root -g root -m 0644 "$tmp_dir/manubisguard-native-restore-safety.py" /usr/local/lib/pasarguard-scripts/pasarguard-restore-safety.py' in cli


def test_native_restore_safety_patch_has_fail_closed_guards():
    patch = RESTORE_SAFETY.read_text()

    assert "manubisguard_prepare_restore_database_safety" in patch
    assert "pg_dump_all_user_databases" in patch
    assert "sha256sum -c safety-files.sha256" in patch
    assert 'flock -n "$restore_lock_fd"' in patch
    assert "manubisguard_rollback_restore_database_safety" in patch
    assert 'local admin_user="$4" admin_password="$5" safety_dir="$6" log_file="$7"' in patch
    assert '"$admin_user" "$admin_password" "$safety_dir/pg_dump" "$log_file"' in patch
    assert '"$safety_admin_user" "$safety_admin_password" "$database_safety_dir" "$log_file"' in patch
    assert 'local restore_lock_root="${PASARGUARD_RESTORE_SAFETY_DIR:-/var/backups/pasarguard/restore-safety}"' in patch
    assert 'local safety_parent="__DOLLAR_BRACE__{PASARGUARD_RESTORE_SAFETY_DIR:-/var/backups/pasarguard/restore-safety}"' in patch
    assert 'local restore_lock_root="${BACKUP_DIR:-$APP_DIR/backup}"' not in patch
    assert 'DATABASE_ROLLBACK=FAIL' in patch
    assert 'if [ "$rollback_safe" = true ] && [ "$services_stopped" = true ]' in patch
    assert 'database_restore_started=true' in patch
    assert 'sqlite_restore_started=true' in patch
    assert 'SQLITE_ROLLBACK=PASS' in patch
    assert 'SQLITE_ROLLBACK=FAIL' in patch
    assert 'sqlite_snapshot_looks_restorable "$sqlite_safety_backup"' in patch


def test_official_pasarguard_install_data_and_backup_paths_are_canonical():
    installer = INSTALLER.read_text()
    adapter = ADAPTER.read_text()
    compose = (ROOT / "docker-compose.yml").read_text()

    assert 'PASARGUARD_INSTALL_DIR:-${MANUBISGUARD_INSTALL_DIR:-/opt/pasarguard}' in installer
    assert 'PASARGUARD_DATA_DIR:-${MANUBISGUARD_DATA_DIR:-/var/lib/pasarguard}' in installer
    assert 'PASARGUARD_BACKUP_DIR:-$INSTALL_DIR/backup' in installer
    assert 'readonly PROJECT_DIR="/opt/pasarguard"' in adapter
    assert 'readonly DATA_DIR="/var/lib/pasarguard"' in adapter
    assert 'readonly BACKUP_DIR="/opt/pasarguard/backup"' in adapter
    assert '  pasarguard:' in compose
    assert '/var/lib/pasarguard/timescaledb:/var/lib/postgresql/data' in compose
    assert '/opt/pasarguard/backup:/opt/pasarguard/backup' in compose
