from pathlib import Path
import zipfile

from app.migration.detector import BackupDetection
from app.migration.preflight import preflight_backup


def test_unknown_custom_dump_is_rechecked_before_product_gate(monkeypatch, tmp_path: Path):
    backup = tmp_path / "backup.dump"
    backup.write_bytes(b"PGDMP" + b"\x00" * 20)

    def fake_detect(path):
        return BackupDetection(
            path=str(path),
            format="pg_dump_custom",
            source_product="unknown",
            confidence="low",
            evidence=("PGDMP",),
        )

    def fake_inspect(path):
        return BackupDetection(
            path=str(path),
            format="pg_dump_custom",
            source_product="pasarguard",
            confidence="high",
            evidence=("PGDMP", "pg_restore TOC inspection completed"),
        )

    monkeypatch.setattr("app.migration.preflight.detect_backup", fake_detect)
    monkeypatch.setattr("app.migration.preflight.inspect_pg_dump_custom", fake_inspect)

    result = preflight_backup(backup)

    assert result.ok is True
    assert result.detection.is_pasarguard is True
    assert not result.blocking_errors


def _pasarguard_detection(path: Path) -> BackupDetection:
    return BackupDetection(
        path=str(path),
        format="zip",
        source_product="pasarguard",
        confidence="high",
        evidence=("manifest.tsv", "PasarGuard"),
    )


def test_preflight_parses_pasarguard_manifest(monkeypatch, tmp_path: Path):
    backup = tmp_path / "pasarguard.zip"
    with zipfile.ZipFile(backup, "w") as archive:
        archive.writestr(
            "manifest.tsv",
            "appdb\tappuser\t1\tpg_dump/db-001.sql\t2.28.2\n",
        )
        archive.writestr("pg_dump/db-001.sql", "-- PostgreSQL dump\n")

    monkeypatch.setattr(
        "app.migration.preflight.detect_backup",
        _pasarguard_detection,
    )

    result = preflight_backup(backup)

    assert result.ok is True
    assert result.pasarguard_manifest is not None
    assert result.pasarguard_manifest.databases[0].timescale_version == "2.28.2"
    assert not result.blocking_errors


def test_preflight_blocks_invalid_pasarguard_manifest(monkeypatch, tmp_path: Path):
    backup = tmp_path / "pasarguard.zip"
    with zipfile.ZipFile(backup, "w") as archive:
        archive.writestr(
            "manifest.tsv",
            "appdb\tappuser\t1\tpg_dump/missing.sql\n",
        )

    monkeypatch.setattr(
        "app.migration.preflight.detect_backup",
        _pasarguard_detection,
    )

    result = preflight_backup(backup)

    assert result.ok is False
    assert any("Timescale version is required" in error for error in result.blocking_errors)


def test_preflight_warns_when_pasarguard_manifest_is_absent(monkeypatch, tmp_path: Path):
    backup = tmp_path / "pasarguard.zip"
    with zipfile.ZipFile(backup, "w") as archive:
        archive.writestr("pasarguard/db-001.sql", "-- PostgreSQL dump\n")

    monkeypatch.setattr(
        "app.migration.preflight.detect_backup",
        _pasarguard_detection,
    )

    result = preflight_backup(backup)

    assert result.ok is True
    assert result.pasarguard_manifest is None
    assert any("manifest.tsv was not found" in warning for warning in result.warnings)
