#!/usr/bin/env python3
"""Safely merge runtime settings from a legacy PasarGuard backup into ManubisGuard.

Deployment files are never imported. The current database connection is always
preserved because the migrated database name/user/password belong to ManubisGuard.
"""

from __future__ import annotations

import argparse
import os
import posixpath
import re
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path


# Runtime settings that are meaningful across PasarGuard/ManubisGuard.
# DB identity is deliberately excluded and restored separately by the caller.
DENY_KEYS = {
    "SQLALCHEMY_DATABASE_URL",
    "DB_USER",
    "DB_NAME",
    "DB_PASSWORD",
    "POSTGRES_PASSWORD",
    "PGADMIN_EMAIL",
    "PGADMIN_PASSWORD",
    "PGHOST",
    "PGPORT",
    "PGUSER",
    "PGDATABASE",
    "PGPASSWORD",
    "PGSERVICE",
    "PGSERVICEFILE",
    "POSTGRES_USER",
    "POSTGRES_DB",
    "POSTGRES_HOST",
    "DB_HOST",
    "DB_PORT",
    "DATABASE_URL",
}

# Deployment/build controls must never come from a backup.
DENY_PREFIXES = ("DOCKER_", "COMPOSE_", "IMAGE_", "CONTAINER_")

ENV_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def parse_env(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = ENV_RE.match(raw)
        if not match:
            continue
        key, value = match.groups()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        result[key] = value
    return result


def quote_env(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:@%+,-]+", value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def merge_env(current: str, legacy: str) -> tuple[str, list[str]]:
    current_map = parse_env(current)
    legacy_map = parse_env(legacy)
    imported: list[str] = []

    for key, value in legacy_map.items():
        if key in DENY_KEYS or any(key.startswith(p) for p in DENY_PREFIXES):
            continue
        # Only import actual legacy settings. Do not import arbitrary malformed
        # lines or empty values that could accidentally disable a setting.
        if value == "":
            continue
        current_map[key] = value
        imported.append(key)

    lines = []
    emitted: set[str] = set()
    for raw in current.splitlines():
        match = ENV_RE.match(raw)
        if match:
            key = match.group(1)
            if key in current_map and key not in emitted:
                lines.append(f"{key}={quote_env(current_map[key])}")
                emitted.add(key)
            else:
                lines.append(raw)
        else:
            lines.append(raw)

    for key in sorted(current_map):
        if key not in emitted:
            lines.append(f"{key}={quote_env(current_map[key])}")

    return "\n".join(lines).rstrip() + "\n", sorted(imported)


def safe_member(name: str) -> str | None:
    name = name.replace("\\", "/")
    if name.startswith("/") or name.startswith("\\") or ":" in name.split("/")[0]:
        return None
    normalized = posixpath.normpath(name)
    if normalized in (".", "") or normalized == ".." or normalized.startswith("../"):
        return None
    return normalized


def read_archive_member(archive: Path, wanted: str) -> bytes | None:
    suffix = archive.name.lower()
    with tempfile.TemporaryDirectory(prefix="manubisguard-env-"):
        if suffix.endswith(".zip"):
            with zipfile.ZipFile(archive) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    mode = (info.external_attr >> 16) & 0o170000
                    if mode == 0o120000 or (mode and mode != 0o100000):
                        raise ValueError("archive contains a link or special file")
                    name = safe_member(info.filename)
                    if name == wanted:
                        return zf.read(info)
            return None
        if suffix.endswith((".tar", ".tar.gz", ".tgz")):
            with tarfile.open(archive, "r:*") as tf:
                for member in tf.getmembers():
                    name = safe_member(member.name)
                    if name == wanted and member.isfile():
                        fh = tf.extractfile(member)
                        return fh.read() if fh else None
            return None
        raise ValueError("Environment restore currently supports ZIP/TAR backups only.")


def extract_archive_tree(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="manubisguard-env-tree-") as td:
        root = Path(td)
        suffix = archive.name.lower()
        if suffix.endswith(".zip"):
            with zipfile.ZipFile(archive) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    mode = (info.external_attr >> 16) & 0o170000
                    if mode == 0o120000 or (mode and mode != 0o100000):
                        raise ValueError("archive contains a link or special file")
                    name = safe_member(info.filename)
                    if not name:
                        continue
                    target = root / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if info.is_dir():
                        target.mkdir(exist_ok=True)
                    else:
                        target.write_bytes(zf.read(info))
        elif suffix.endswith((".tar", ".tar.gz", ".tgz")):
            with tarfile.open(archive, "r:*") as tf:
                for member in tf.getmembers():
                    name = safe_member(member.name)
                    if not name or member.issym() or member.islnk():
                        continue
                    target = root / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if member.isfile():
                        fh = tf.extractfile(member)
                        if fh:
                            target.write_bytes(fh.read())
        else:
            raise ValueError("Environment restore currently supports ZIP/TAR backups only.")
        shutil.copytree(root, destination, dirs_exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup")
    parser.add_argument("current_env")
    parser.add_argument("candidate_env")
    parser.add_argument("--runtime-root", default="/var/lib/pasarguard")
    parser.add_argument(
        "--asset-stage-root",
        default="",
        help="Stage referenced runtime certificate/key assets under this work directory.",
    )
    parser.add_argument("--cert-dest", default="")
    args = parser.parse_args()

    backup = Path(args.backup).resolve()
    current = Path(args.current_env)
    candidate = Path(args.candidate_env)

    if not backup.is_file() or not current.is_file():
        raise SystemExit("backup and current .env must be regular files")

    raw = read_archive_member(backup, ".env")
    if raw is None:
        print("ENV_SOURCE=missing")
        shutil.copy2(current, candidate)
        return 0

    legacy = raw.decode("utf-8-sig", errors="strict")
    merged, imported = merge_env(current.read_text(encoding="utf-8"), legacy)
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text(merged, encoding="utf-8")
    os.chmod(candidate, 0o600)

    print("ENV_SOURCE=legacy")
    print("IMPORTED_KEYS=" + ",".join(imported))

    env_map = parse_env(merged)
    cert_keys = ("UVICORN_SSL_CERTFILE", "UVICORN_SSL_KEYFILE")

    if args.asset_stage_root:
        runtime_root = Path(args.runtime_root).resolve()
        stage_root = Path(args.asset_stage_root).resolve()
        staged = 0
        for key in cert_keys:
            value = env_map.get(key, "")
            if not value:
                continue
            resolved = Path(value).resolve()
            try:
                rel = resolved.relative_to(runtime_root)
            except ValueError:
                print(f"ASSET_SKIPPED_OUTSIDE_RUNTIME={key}")
                continue
            member = "pasarguard_data/" + rel.as_posix()
            payload = read_archive_member(backup, member)
            if payload is None:
                print(f"ASSET_SOURCE_MISSING={key}")
                continue
            target = stage_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            os.chmod(target, 0o600)
            staged += 1
            print(f"ASSET_STAGED={key}:{rel.as_posix()}")
        print(f"ASSET_STAGED_COUNT={staged}")

    if args.cert_dest:
        runtime_root = Path(args.runtime_root).resolve()
        cert_dest = Path(args.cert_dest).resolve()
        if runtime_root != cert_dest and runtime_root not in cert_dest.parents:
            raise SystemExit("cert destination must remain under runtime root")
        # Only restore certificate files explicitly referenced by the merged env.
        env_map = parse_env(merged)
        cert_keys = ("UVICORN_SSL_CERTFILE", "UVICORN_SSL_KEYFILE")
        with tempfile.TemporaryDirectory(prefix="manubisguard-cert-") as td:
            tree = Path(td) / "tree"
            extract_archive_tree(backup, tree)
            for key in cert_keys:
                value = env_map.get(key, "")
                if not value.startswith(str(runtime_root) + "/"):
                    continue
                rel = Path(value).relative_to(runtime_root)
                source = tree / "pasarguard_data" / rel
                if not source.is_file():
                    print(f"CERT_SOURCE_MISSING={key}")
                    continue
                target = cert_dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                os.chmod(target, 0o600)
                print(f"CERT_IMPORTED={key}:{rel}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
