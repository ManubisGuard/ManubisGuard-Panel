#!/usr/bin/env python3
from __future__ import annotations

import hmac
import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = int(os.environ.get("MANUBISGUARD_RESTORE_AGENT_PORT", "8765"))
KEY_FILE = Path("/etc/manubisguard/restore-agent.key")
BACKUP_ROOT = Path("/var/lib/manubisguard/backups").resolve()
MIGRATE = "/usr/local/bin/manubisguard-migrate"
_lock = threading.Lock()


def read_key() -> bytes:
    return KEY_FILE.read_bytes().strip()


class Handler(BaseHTTPRequestHandler):
    server_version = "ManubisGuardRestoreAgent/1"

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/restore":
            self._send(404, {"error": "not found"})
            return
        expected = read_key()
        supplied = self.headers.get("Authorization", "")
        if not hmac.compare_digest(supplied, "Bearer " + expected.decode()):
            self._send(401, {"error": "unauthorized"})
            return
        if not _lock.acquire(blocking=False):
            self._send(409, {"error": "a production restore is already running"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 4096:
                self._send(400, {"error": "invalid request body"})
                return
            data = json.loads(self.rfile.read(length))
            backup = Path(str(data.get("backup_path", ""))).resolve()
            if backup.suffix.lower() != ".zip" or BACKUP_ROOT not in backup.parents or not backup.is_file():
                self._send(400, {"error": "backup_path must be an existing ZIP under the backup directory"})
                return
            if data.get("confirmation") != "RESTORE_PRODUCTION":
                self._send(400, {"error": "production restore confirmation required"})
                return
            proc = subprocess.run(
                [MIGRATE, str(backup), "--apply"],
                cwd="/opt/manubisguard-panel",
                text=True,
                capture_output=True,
                timeout=7200,
                check=False,
            )
            output = (proc.stdout + "\n" + proc.stderr).strip()
            self._send(
                200 if proc.returncode == 0 else 500,
                {"ok": proc.returncode == 0, "returncode": proc.returncode, "output": output[-12000:]},
            )
        except subprocess.TimeoutExpired:
            self._send(504, {"error": "production restore timed out; inspect migration workspace logs"})
        except Exception as exc:
            self._send(500, {"error": str(exc)})
        finally:
            _lock.release()

    def log_message(self, fmt: str, *args) -> None:
        return


if __name__ == "__main__":
    KEY_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not KEY_FILE.is_file():
        raise SystemExit("restore-agent key is missing")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
