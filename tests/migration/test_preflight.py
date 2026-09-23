from pathlib import Path

from app.migration.preflight import preflight_backup


def test_unknown_custom_dump_is_rechecked_before_product_gate(monkeypatch, tmp_path: Path):
    backup = tmp_path / "backup.dump"
    backup.write_bytes(b"PGDMP" + b"\x00" * 20)

    def fake_detect(path):
        from app.migration.detector import BackupDetection
        return BackupDetection(
            path=str(path),
            format="pg_dump_custom",
            source_product="unknown",
            confidence="low",
            evidence=("PGDMP",),
        )

    def fake_inspect(path):
        from app.migration.detector import BackupDetection
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
