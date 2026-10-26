from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_script(module_name: str, relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_full_backup_hash_helpers_are_incremental(tmp_path):
    full_backup = load_script("full_backup_streaming_test", "scripts/manubisguard-full-backup.py")
    payload = (b"backup-payload-" * 100_000) + b"end"
    file_path = tmp_path / "large-payload.bin"
    file_path.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()

    assert full_backup.sha256_file(file_path) == expected
    with file_path.open("rb") as stream:
        assert full_backup.sha256_stream(stream, chunk_size=4096) == expected


def test_native_restore_hashes_zip_members_incrementally(tmp_path):
    native_restore = load_script("native_restore_hash_streaming_test", "scripts/manubisguard-native-restore.py")
    payload = (b"custom-pg-dump-" * 100_000) + b"end"
    archive_path = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("database.dump", payload)

    with zipfile.ZipFile(archive_path) as archive:
        assert native_restore.sha256_zip_member(archive, "database.dump") == hashlib.sha256(payload).hexdigest()


def test_native_restore_passes_disk_backed_dump_to_pg_restore(monkeypatch):
    native_restore = load_script("native_restore_stream_input_test", "scripts/manubisguard-native-restore.py")
    payload = (b"custom-pg-dump-" * 100_000) + b"end"
    captured = {}

    def fake_run(command, **kwargs):
        source = kwargs["stdin"]
        captured["has_file_descriptor"] = callable(getattr(source, "fileno", None))
        captured["has_input_bytes"] = "input" in kwargs
        captured["length"] = len(source.read())
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(native_restore.shutil, "which", lambda _name: "/usr/bin/pg_restore")
    monkeypatch.setattr(native_restore.subprocess, "run", fake_run)

    with tempfile.TemporaryFile(mode="w+b") as stream:
        stream.write(payload)
        stream.seek(0)
        ok, detail = native_restore.check_database_dump(stream)

    assert ok, detail
    assert captured["has_file_descriptor"]
    assert not captured["has_input_bytes"]
    assert captured["length"] == len(payload)
