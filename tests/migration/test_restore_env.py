from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "manubisguard-restore-env.py"


def load_module():
    spec = importlib.util.spec_from_file_location("restore_env", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_merge_env_preserves_database_identity_and_imports_runtime_settings():
    mod = load_module()
    current = (
        "UVICORN_PORT=8000\n"
        "SQLALCHEMY_DATABASE_URL=postgresql+asyncpg://current:secret@127.0.0.1:5432/pasarguard\n"
        "POSTGRES_PASSWORD=current-db-secret\n"
        "MANUBISGUARD_FEATURE_X=true\n"
    )
    legacy = (
        "UVICORN_PORT = 8443\n"
        "UVICORN_SSL_CERTFILE=/var/lib/pasarguard/certs/fullchain.pem\n"
        "UVICORN_SSL_KEYFILE=/var/lib/pasarguard/certs/privkey.pem\n"
        "SQLALCHEMY_DATABASE_URL=postgresql+asyncpg://legacy:secret@old-host:5432/pasarguard\n"
        "POSTGRES_PASSWORD=legacy-secret\n"
        "BACKUP_SERVICE_ENABLED=true\n"
    )
    merged, imported = mod.merge_env(current, legacy)

    values = mod.parse_env(merged)
    assert values["UVICORN_PORT"] == "8443"
    assert values["UVICORN_SSL_CERTFILE"].endswith("/fullchain.pem")
    assert values["UVICORN_SSL_KEYFILE"].endswith("/privkey.pem")
    assert values["BACKUP_SERVICE_ENABLED"] == "true"
    assert values["SQLALCHEMY_DATABASE_URL"].startswith("postgresql+asyncpg://current:")
    assert values["POSTGRES_PASSWORD"] == "current-db-secret"
    assert values["MANUBISGUARD_FEATURE_X"] == "true"
    assert "UVICORN_PORT" in imported
    assert "SQLALCHEMY_DATABASE_URL" not in imported


def test_merge_env_does_not_import_deployment_controls():
    mod = load_module()
    current = "UVICORN_PORT=8000\n"
    legacy = (
        "UVICORN_PORT=9000\n"
        "DOCKER_IMAGE=attacker/image:latest\n"
        "COMPOSE_PROJECT_NAME=legacy\n"
    )
    merged, _ = mod.merge_env(current, legacy)
    values = mod.parse_env(merged)
    assert values["UVICORN_PORT"] == "9000"
    assert "DOCKER_IMAGE" not in values
    assert "COMPOSE_PROJECT_NAME" not in values


def test_archive_env_reader_reads_only_exact_env_member(tmp_path: Path):
    mod = load_module()
    backup = tmp_path / "backup.zip"
    import zipfile
    with zipfile.ZipFile(backup, "w") as zf:
        zf.writestr(".env", "UVICORN_PORT=8443\n")
        zf.writestr(".env.old", "UVICORN_PORT=1234\n")
    assert mod.read_archive_member(backup, ".env") == b"UVICORN_PORT=8443\n"
