import ast
import hashlib
import shlex
import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAFETY_PATCH = ROOT / "scripts" / "manubisguard-native-restore-safety.py"


def _sqlite_rollback_snippet() -> str:
    tree = ast.parse(SAFETY_PATCH.read_text())
    cleanup_insert = next(
        ast.literal_eval(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "cleanup_insert" for target in node.targets)
    )
    start = '        if [ "$sqlite_restore_started" = true ]; then\n'
    end = '        if [ -n "$safety_data_dir" ] && [ -d "$safety_data_dir" ]; then\n'
    return cleanup_insert[cleanup_insert.index(start) : cleanup_insert.index(end)]


def _create_db(path: Path, value: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE fixture (value TEXT NOT NULL)")
        connection.execute("INSERT INTO fixture(value) VALUES (?)", (value,))


def _read_db(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT value FROM fixture").fetchone()[0]


def _run_rollback(tmp_path: Path, target: Path, snapshot: str, expected_safe: bool) -> str:
    log = tmp_path / "restore.log"
    validator = r'''sqlite_snapshot_looks_restorable() {
    python3 -c 'import sqlite3,sys
try:
 c=sqlite3.connect(sys.argv[1]); result=c.execute("PRAGMA integrity_check").fetchone()[0]; c.close(); sys.exit(0 if result == "ok" else 1)
except Exception: sys.exit(1)' "$1" 2>/dev/null
}
colorized_echo() { :; }
'''
    script = "\n".join(
        [
            "set -euo pipefail",
            f"sqlite_file={shlex.quote(str(target))}",
            f"sqlite_safety_backup={shlex.quote(snapshot)}",
            f"log_file={shlex.quote(str(log))}",
            "sqlite_restore_started=true",
            "rollback_safe=true",
            validator,
            _sqlite_rollback_snippet(),
            f'test "$rollback_safe" = {"true" if expected_safe else "false"}',
            "",
        ]
    )
    script_path = tmp_path / "run-sqlite-rollback.sh"
    script_path.write_text(script)
    subprocess.run(["bash", str(script_path)], check=True, capture_output=True, text=True)
    return log.read_text()


def test_sqlite_restore_failure_rolls_back_verified_snapshot(tmp_path: Path) -> None:
    target = tmp_path / "target.sqlite"
    snapshot = tmp_path / "snapshot.sqlite"
    _create_db(target, "before")
    snapshot.write_bytes(target.read_bytes())
    with sqlite3.connect(target) as connection:
        connection.execute("UPDATE fixture SET value = 'mutated'")

    log = _run_rollback(tmp_path, target, str(snapshot), expected_safe=True)

    assert _read_db(target) == "before"
    assert "SQLITE_ROLLBACK=PASS" in log


def test_sqlite_restore_failure_fails_closed_on_corrupt_snapshot(tmp_path: Path) -> None:
    target = tmp_path / "target.sqlite"
    snapshot = tmp_path / "snapshot.sqlite"
    _create_db(target, "mutated")
    snapshot.write_text("not a SQLite database")

    log = _run_rollback(tmp_path, target, str(snapshot), expected_safe=False)

    assert _read_db(target) == "mutated"
    assert "SQLITE_ROLLBACK=FAIL" in log


def test_sqlite_restore_failure_removes_partial_database_when_none_existed(tmp_path: Path) -> None:
    target = tmp_path / "target.sqlite"
    target.write_text("partial database")

    log = _run_rollback(tmp_path, target, "", expected_safe=True)

    assert not target.exists()
    assert "SQLITE_ROLLBACK=PASS" in log


def test_restore_safety_patch_rejects_stale_marked_library(tmp_path: Path) -> None:
    stale_library = tmp_path / "stale-restore.sh"
    stale_library.write_text(
        "# MANUBISGUARD_RESTORE_SAFETY_V2_HELPERS\\n"
        "manubisguard_rollback_restore_database_safety\\n"
        "DATABASE_ROLLBACK=PASS\\n"
        "MANUBISGUARD_RESTORE_SAFETY_V1_LOCK\\n"
        "sqlite_restore_started=true\\n"
        "SQLITE_ROLLBACK=PASS\\n"
    )

    result = subprocess.run(
        ["python3", str(SAFETY_PATCH), str(stale_library)], capture_output=True, text=True, check=False
    )

    assert result.returncode != 0
    assert "partial or inconsistent restore safety patch marker" in result.stderr


def test_postgres_rollback_forwards_distinct_admin_credentials(tmp_path: Path) -> None:
    library = tmp_path / "pasarguard-restore.sh"
    library.write_text((ROOT / "lib" / "pasarguard-restore.sh").read_text())
    subprocess.run(["python3", str(SAFETY_PATCH), str(library)], check=True, capture_output=True, text=True)
    patched_contents = library.read_text()
    second_patch = subprocess.run(
        ["python3", str(SAFETY_PATCH), str(library)], check=True, capture_output=True, text=True
    )
    assert "already applied" in second_patch.stdout
    assert library.read_text() == patched_contents

    snapshot = tmp_path / "snapshot"
    dump_dir = snapshot / "pg_dump"
    dump_dir.mkdir(parents=True)
    (dump_dir / "db-001.sql").write_text(
        "-- PostgreSQL database dump\nCREATE TABLE public.fixture (id integer);\n"
        "-- PostgreSQL database dump complete\n"
    )
    (dump_dir / "globals.sql").write_text("-- PostgreSQL database cluster dump complete\n")
    (dump_dir / "manifest.tsv").write_text("fixture_db\tfixture_owner\t0\tdb-001.sql\t\n")
    checksum_paths = sorted(path for path in dump_dir.iterdir() if path.is_file())
    (snapshot / "safety-files.sha256").write_text(
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  pg_dump/{path.name}\n"
            for path in checksum_paths
        )
    )
    (snapshot / "SAFETY_SNAPSHOT_VALIDATED").write_text("")
    log_file = tmp_path / "rollback.log"
    captured_args = tmp_path / "rollback-args.txt"

    script = '''set -euo pipefail
source "$1"
export CAPTURE_ARGS="$4"
pg_restore_all_user_databases() { printf '%s\\n' "$@" > "$CAPTURE_ARGS"; }
manubisguard_rollback_restore_database_safety \\
  test-container restore-user restore-pass admin-user admin-pass "$2" "$3"
'''
    subprocess.run(
        ["bash", "-c", script, "_", str(library), str(snapshot), str(log_file), str(captured_args)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert captured_args.read_text().splitlines() == [
        "test-container",
        "restore-user",
        "restore-pass",
        "admin-user",
        "admin-pass",
        str(dump_dir),
        str(log_file),
    ]
