from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "manubis"
ADAPTER = ROOT / "scripts" / "manubisguard-native-backup.sh"
INSTALLER = ROOT / "install-manubisguard.sh"


def test_native_restore_uses_the_pinned_pasarguard_engine():
    adapter = ADAPTER.read_text()
    cli = CLI.read_text()

    assert 'UPSTREAM_COMMIT="21f64e42e0cc2f9a7c4f633642e9b8f6365ea5a7"' in adapter
    assert 'restore) bash "$work/pasarguard.sh" restore "$@" ;;' in adapter
    assert 'backup) bash "$work/pasarguard.sh" backup "$@" ;;' in adapter
    assert '/usr/local/bin/manubisguard-native-backup" restore' in cli
    assert not (ROOT / "scripts" / "manubisguard-native-restore.py").exists()


def test_restore_options_are_forwarded_to_upstream_without_custom_validator():
    adapter = ADAPTER.read_text()
    cli = CLI.read_text()

    assert 'restore) bash "$work/pasarguard.sh" restore "$@" ;;' in adapter
    assert 'manubisguard-native-restore.py --apply' not in cli
    assert 'exec /usr/local/bin/manubisguard-migrate' in cli


def test_in_place_update_refuses_to_discard_tracked_local_edits():
    installer = INSTALLER.read_text()

    assert 'In-place update refused: tracked local changes exist' in installer
    assert 'git -C "$INSTALL_DIR" diff --quiet' in installer
    assert 'git -C "$INSTALL_DIR" diff --cached --quiet' in installer
