import pytest

from app.migration.pasarguard_backup import parse_manifest_tsv


def test_parse_pasarguard_manifest():
    manifest = parse_manifest_tsv(
        "appdb\tappuser\t1\tdb-001.sql\t2.27.2\n"
        "otherdb\totheruser\t0\tdb-002.sql\n"
    )

    assert len(manifest.databases) == 2
    assert manifest.databases[0].name == "appdb"
    assert manifest.databases[0].timescale
    assert manifest.databases[0].timescale_version == "2.27.2"
    assert manifest.databases[1].timescale is False
    assert manifest.databases[1].timescale_version is None


@pytest.mark.parametrize(
    "manifest",
    [
        "appdb\tappuser\t2\tdb-001.sql",
        "appdb\tappuser\t1\tdb-001.sql",
        "appdb\tappuser\t0\tdb-001.sql\t2.27.2",
        "appdb\tappuser\tdb-001.sql",
        "",
    ],
)
def test_manifest_rejects_malformed_rows(manifest: str):
    with pytest.raises(ValueError):
        parse_manifest_tsv(manifest)


def test_manifest_ignores_blank_and_comment_lines():
    manifest = parse_manifest_tsv(
        "# PasarGuard backup\n\n"
        "appdb\tappuser\t1\tdb-001.sql\t2.28.2\n"
    )

    assert [entry.name for entry in manifest.databases] == ["appdb"]
