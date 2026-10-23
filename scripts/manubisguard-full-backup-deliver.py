#!/usr/bin/env python3
import os, subprocess, sys
from pathlib import Path

PROJECT = Path("/opt/manubisguard-panel")
BACKUP = Path("/usr/local/sbin/manubisguard-full-backup.py")
KEY = Path("/etc/manubisguard/full-backup.key")
OUT = Path("/var/lib/manubisguard/backups/full")
SENDER_SOURCE = PROJECT / "scripts/send-full-backup-telegram.py"
def retention_count():
    value = 3
    policy = Path("/etc/manubisguard/full-backup.conf")
    if policy.is_file():
        for line in policy.read_text(errors="replace").splitlines():
            if line.strip().startswith("RETENTION_COUNT="):
                try:
                    candidate = int(line.split("=", 1)[1].strip())
                    if candidate >= 1:
                        value = candidate
                except ValueError:
                    pass
    return value

def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)

def main():
    if os.geteuid() != 0:
        raise RuntimeError("Run as root")
    if not KEY.is_file() or KEY.stat().st_mode & 0o077:
        raise RuntimeError("Encryption key missing or permissions are too broad")
    run([str(BACKUP)])
    archives = sorted(OUT.glob("manubisguard-full-*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not archives:
        raise RuntimeError("No full backup archive found")
    archive = archives[0]
    encrypted = archive.with_suffix(archive.suffix + ".enc")
    run(["openssl", "enc", "-aes-256-cbc", "-salt", "-pbkdf2", "-iter", "600000",
         "-pass", "file:" + str(KEY), "-in", str(archive), "-out", str(encrypted)])
    encrypted.chmod(0o600)
    if not SENDER_SOURCE.is_file():
        raise RuntimeError("Sender helper missing")
    result = subprocess.run(
        ["docker", "compose", "-f", str(PROJECT / "docker-compose.yml"),
         "exec", "-T", "manubisguard", "python", "-", str(encrypted)],
        input=SENDER_SOURCE.read_bytes(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False
    )
    output = result.stdout.decode("utf-8", errors="replace")
    print(output, end="")
    if result.returncode != 0:
        raise RuntimeError("Encrypted archive remains local; delivery failed")
    encrypted_archives = sorted(OUT.glob("manubisguard-full-*.zip.enc"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in encrypted_archives[retention_count():]:
        old.unlink(missing_ok=True)
    print("encrypted_file=" + str(encrypted))
    print("encryption=AES-256-CBC with PBKDF2")
    print("key_file=" + str(KEY))

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("FULL BACKUP DELIVERY FAILED: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
