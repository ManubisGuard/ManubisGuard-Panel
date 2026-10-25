from __future__ import annotations

import importlib.util
import tarfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "manubisguard-native-restore.py"
SPEC = importlib.util.spec_from_file_location("manubisguard_native_restore", SCRIPT)
assert SPEC and SPEC.loader
native_restore = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native_restore)


def member(name: str, *, kind: str = "file", linkname: str = "") -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    if kind == "file":
        info.type = tarfile.REGTYPE
        info.size = 0
    elif kind == "symlink":
        info.type = tarfile.SYMTYPE
        info.linkname = linkname
    elif kind == "hardlink":
        info.type = tarfile.LNKTYPE
        info.linkname = linkname
    elif kind == "fifo":
        info.type = tarfile.FIFOTYPE
    return info


def test_safe_member_name_rejects_absolute_and_parent_paths():
    assert native_restore.safe_member_name("etc/nginx/nginx.conf")
    assert not native_restore.safe_member_name("/etc/shadow")
    assert not native_restore.safe_member_name("etc/../shadow")
    assert not native_restore.safe_member_name("../outside")


def test_tar_member_rejects_path_traversal_and_special_files():
    assert native_restore.validate_tar_member(member("../outside")) is not None
    assert native_restore.validate_tar_member(member("etc/passwd", kind="fifo")) is not None
    assert native_restore.validate_tar_member(member("etc/link", kind="symlink", linkname="../../../../outside")) is not None


def test_tar_member_allows_safe_relative_symlinks():
    assert native_restore.validate_tar_member(
        member("etc/letsencrypt/live/example/fullchain.pem", kind="symlink", linkname="../../archive/example/fullchain1.pem")
    ) is None


def test_native_restore_apply_is_disabled_without_mutating_anything(capsys):
    # The CLI's apply branch is intentionally fail-closed until rollback support exists.
    # This source-level contract guards against accidental fallback to the migration runner.
    source = SCRIPT.read_text()
    assert "native production restore is not enabled" in source
    assert '"/usr/local/bin/manubisguard-migrate"' not in source


def test_database_and_full_backup_directories_are_separated():
    backup_script = (SCRIPT.parent / "manubisguard-full-backup.py").read_text()
    db_script = (SCRIPT.parent / "backup-db.sh").read_text()
    assert "BACKUP_ROOT = Path('/opt/manubisguard/backup')" in backup_script
    assert "OUT = BACKUP_ROOT / 'full'" in backup_script
    assert "/opt/manubisguard/backup/database" in db_script
    assert "'opt/manubisguard/backup'" in backup_script


def test_manifest_v2_requires_global_dump_and_database_catalog():
    source = SCRIPT.read_text()
    backup_source = (SCRIPT.parent / "manubisguard-full-backup.py").read_text()
    assert '"globals.sql" not in names' in source
    assert 'manifest.get("database_catalog")' in source
    assert 'manifest.get("image_inventory")' in source
    assert 'database archive member missing from payload checksum inventory' in source
    assert "pg_dumpall" in backup_source and "--globals-only" in backup_source
    assert "database_catalog" in backup_source and "databases/" in backup_source
    assert "docker', 'image', 'inspect" in backup_source


def test_stage_restore_imports_globals_and_catalogued_databases_in_isolation():
    source = SCRIPT.read_text()
    assert '"--network", "none"' in source
    assert '"--tmpfs", "/var/lib/postgresql/data:rw,size=768m,mode=0700"' in source
    assert '"globals.sql"' in source and 'entry["archive_member"]' in source
    assert 'native production restore is not enabled' in source
