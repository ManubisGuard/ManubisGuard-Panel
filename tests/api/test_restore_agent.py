import importlib.util
import json
import threading
from http.client import HTTPConnection
from pathlib import Path
from tempfile import TemporaryDirectory

_SPEC = importlib.util.spec_from_file_location(
    "restore_agent", Path(__file__).parents[2] / "scripts/manubisguard-restore-agent.py"
)
agent = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(agent)


def test_restore_agent_rejects_unauthorized_and_invalid_path(monkeypatch):
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        key = root / "key"
        key.write_text("test-key", encoding="utf-8")
        backup_root = root / "backups"
        backup_root.mkdir()
        monkeypatch.setattr(agent, "KEY_FILE", key)
        monkeypatch.setattr(agent, "BACKUP_ROOT", backup_root.resolve())
        server = agent.ThreadingHTTPServer(("127.0.0.1", 0), agent.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            conn = HTTPConnection(host, port, timeout=5)
            conn.request(
                "POST",
                "/restore",
                body=json.dumps({"backup_path": str(backup_root / "x.zip"), "confirmation": "RESTORE_PRODUCTION"}),
                headers={"Authorization": "Bearer wrong", "Content-Type": "application/json"},
            )
            assert conn.getresponse().status == 401
            conn.close()
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


def test_restore_agent_runs_apply_only_for_confirmed_backup(monkeypatch):
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        key = root / "key"
        key.write_text("test-key", encoding="utf-8")
        backup_root = root / "backups"
        backup_root.mkdir()
        backup = backup_root / "sample.zip"
        backup.write_bytes(b"test")
        fake = root / "migrate"
        fake.write_text("#!/bin/sh\nprintf 'APPLY_OK\\n'\n", encoding="utf-8")
        fake.chmod(0o755)
        monkeypatch.setattr(agent, "KEY_FILE", key)
        monkeypatch.setattr(agent, "BACKUP_ROOT", backup_root.resolve())
        monkeypatch.setattr(agent, "MIGRATE", str(fake))
        server = agent.ThreadingHTTPServer(("127.0.0.1", 0), agent.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            conn = HTTPConnection(host, port, timeout=5)
            body = json.dumps({"backup_path": str(backup), "confirmation": "RESTORE_PRODUCTION"})
            conn.request(
                "POST",
                "/restore",
                body=body,
                headers={"Authorization": "Bearer test-key", "Content-Type": "application/json"},
            )
            response = conn.getresponse()
            payload = json.loads(response.read())
            assert response.status == 200
            assert payload["ok"] is True
            assert payload["returncode"] == 0
            assert "APPLY_OK" in payload["output"]
            conn.close()
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
