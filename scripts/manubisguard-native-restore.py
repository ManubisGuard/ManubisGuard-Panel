#!/usr/bin/env python3
"""Read-only validator for native ManubisGuard full-system backup archives.

Production apply is intentionally fail-closed until the staged native restore and
rollback implementation is available. This tool never extracts into live paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

BACKUP_ROOT = Path("/opt/manubisguard/backup/full").resolve()
REQUIRED = {"database.dump", "filesystem.tar.gz", "manifest.json", "runtime-inventory.json"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_stream(stream, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def sha256_zip_member(archive: zipfile.ZipFile, name: str) -> str:
    with archive.open(name, "r") as stream:
        return sha256_stream(stream)


def safe_member_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and "\x00" not in name


def validate_tar_member(member: tarfile.TarInfo) -> str | None:
    if not safe_member_name(member.name):
        return f"unsafe filesystem archive path: {member.name!r}"
    if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
        return f"unsupported special filesystem member: {member.name!r}"
    if member.issym() or member.islnk():
        target = member.linkname
        if not target:
            return f"empty link target: {member.name!r}"
        # Absolute symlinks are common in host config snapshots (e.g. /etc/ssl).
        # They are recorded only; the future restore engine must never follow them
        # while staging/extracting. Hardlinks are archive-relative and must stay inside.
        if member.islnk():
            if posixpath.isabs(target):
                return f"absolute hardlink target: {member.name!r}"
            resolved = posixpath.normpath(target)
            if resolved == ".." or resolved.startswith("../"):
                return f"hardlink escapes archive root: {member.name!r}"
        elif not posixpath.isabs(target):
            base = posixpath.dirname(member.name)
            resolved = posixpath.normpath(posixpath.join(base, target))
            if resolved == ".." or resolved.startswith("../"):
                return f"symlink escapes archive root: {member.name!r}"
    return None


def check_database_dump(stream) -> tuple[bool, str]:
    """Inspect a streamed dump without materializing the entire archive in RAM.

    Never exec into the live database container during preflight. The fallback
    container has no network, a read-only root filesystem, and no mounted data.
    """
    local = shutil.which("pg_restore")
    if local:
        command = [local, "--list"]
    else:
        command = [
            "docker", "run", "--rm", "-i", "--network", "none", "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
            "--entrypoint", "pg_restore", "timescale/timescaledb:latest-pg16", "--list",
        ]
    try:
        stream.seek(0)
        result = subprocess.run(command, stdin=stream, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, check=False, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"isolated pg_restore validation could not run: {exc}"
    if result.returncode != 0:
        return False, result.stderr.decode("utf-8", errors="replace")[-1200:]
    return True, "pg_restore catalog readable (local or isolated offline container)"


def validate_certificates(tar: tarfile.TarFile, manifest: dict) -> list[str]:
    errors: list[str] = []
    certs = manifest.get("certificate_files", [])
    if not isinstance(certs, list):
        return ["manifest certificate_files must be a list"]
    extracted: dict[str, bytes] = {}
    for item in certs:
        if not isinstance(item, dict):
            errors.append("malformed certificate inventory entry")
            continue
        member_name = str(item.get("resolved_path", "")).lstrip("/")
        try:
            member = tar.getmember(member_name) if member_name else None
        except KeyError:
            member = None
        if member is None or not member.isfile():
            errors.append("required TLS file missing from filesystem archive: " + str(item.get("configured_path", member_name)))
            continue
        stream = tar.extractfile(member)
        if stream is None:
            errors.append("cannot read archived TLS file: " + member_name)
            continue
        data = stream.read()
        if sha256_bytes(data) != item.get("sha256"):
            errors.append("TLS checksum mismatch: " + str(item.get("configured_path", member_name)))
            continue
        extracted[member_name] = data

    keys = [x for x in certs if isinstance(x, dict) and x.get("kind") == "private-key"]
    cert_entries = [x for x in certs if isinstance(x, dict) and x.get("kind") == "certificate-or-chain"]
    if keys and not cert_entries:
        errors.append("TLS private key inventory has no certificate/chain")
    for index, key in enumerate(keys):
        key_member = str(key.get("resolved_path", "")).lstrip("/")
        key_data = extracted.get(key_member)
        if key_data is None:
            continue
        with tempfile.TemporaryDirectory(prefix="manubisguard-cert-check-") as td:
            key_path = Path(td) / f"key-{index}.pem"
            key_path.write_bytes(key_data)
            key_pub = subprocess.run(["openssl", "pkey", "-in", str(key_path), "-pubout"], capture_output=True, check=False)
            if key_pub.returncode != 0:
                errors.append("cannot validate archived private key: " + str(key.get("configured_path", key_member)))
                continue
            matched = False
            for cert_index, cert in enumerate(cert_entries):
                cert_member = str(cert.get("resolved_path", "")).lstrip("/")
                cert_data = extracted.get(cert_member)
                if cert_data is None:
                    continue
                cert_path = Path(td) / f"cert-{cert_index}.pem"
                cert_path.write_bytes(cert_data)
                cert_pub = subprocess.run(["openssl", "x509", "-in", str(cert_path), "-pubkey", "-noout"], capture_output=True, check=False)
                if cert_pub.returncode == 0 and cert_pub.stdout == key_pub.stdout:
                    matched = True
                    break
            if not matched:
                errors.append("no archived certificate matches private key: " + str(key.get("configured_path", key_member)))
    return errors


def validate_archive(path: Path) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    if not path.is_file() or path.suffix.lower() != ".zip":
        print("ERROR: expected an existing native full-backup ZIP archive", file=sys.stderr)
        return 2
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                errors.append("duplicate ZIP member names")
            missing = REQUIRED - set(names)
            if missing:
                errors.append("required ZIP members missing: " + ", ".join(sorted(missing)))
            bad = archive.testzip()
            if bad:
                errors.append("ZIP CRC failure in member: " + bad)
            if errors:
                raise ValueError("; ".join(errors))
            manifest = json.loads(archive.read("manifest.json"))
            if not isinstance(manifest, dict):
                errors.append("manifest root must be a JSON object")
                raise TypeError("invalid manifest root")
            if manifest.get("product") != "ManubisGuard" or manifest.get("kind") != "full-host-panel-backup":
                errors.append("archive is not a native ManubisGuard full-host backup")
            if manifest.get("manifest_version", 1) >= 2:
                if "globals.sql" not in names:
                    errors.append("manifest v2 archive is missing PostgreSQL globals.sql")
                catalog = manifest.get("database_catalog")
                if not isinstance(catalog, list) or not catalog:
                    errors.append("manifest v2 archive is missing database_catalog")
                else:
                    catalog_members = set()
                    for entry in catalog:
                        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not isinstance(entry.get("archive_member"), str):
                            errors.append("malformed database_catalog entry")
                            continue
                        member_name = entry["archive_member"]
                        if not safe_member_name(member_name) or member_name not in names:
                            errors.append("unsafe or missing database archive member: " + member_name)
                        catalog_members.add(member_name)
                    if "database.dump" not in catalog_members:
                        errors.append("database_catalog does not map the configured database.dump")
                    if isinstance(manifest.get("payload_sha256"), dict):
                        for member_name in catalog_members:
                            if member_name not in manifest["payload_sha256"]:
                                errors.append("database archive member missing from payload checksum inventory: " + member_name)
                    extra_database_members = {name for name in names if name.startswith("databases/")} - catalog_members
                    if extra_database_members:
                        errors.append("database archive members are not represented in database_catalog: " + ", ".join(sorted(extra_database_members)))
            if manifest.get("database_dump_sha256") != sha256_zip_member(archive, "database.dump"):
                errors.append("database.dump SHA-256 mismatch")
            if manifest.get("filesystem_archive_sha256") != sha256_zip_member(archive, "filesystem.tar.gz"):
                errors.append("filesystem.tar.gz SHA-256 mismatch")
            if manifest.get("manifest_version", 1) >= 2:
                payload_checksums = manifest.get("payload_sha256")
                if not isinstance(payload_checksums, dict):
                    errors.append("manifest v2 requires payload_sha256 inventory")
                else:
                    for payload_name, expected_digest in payload_checksums.items():
                        if not isinstance(payload_name, str) or not safe_member_name(payload_name) or payload_name not in names:
                            errors.append("unsafe or missing payload in checksum inventory: " + str(payload_name))
                            continue
                        if not isinstance(expected_digest, str) or expected_digest != sha256_zip_member(archive, payload_name):
                            errors.append(f"payload SHA-256 inventory mismatch: {payload_name}")
                    for payload_name in ("database.dump", "globals.sql", "filesystem.tar.gz", "runtime-inventory.json"):
                        if payload_name not in payload_checksums:
                            errors.append("payload SHA-256 inventory missing: " + payload_name)
                versions = manifest.get("database_versions")
                if not isinstance(versions, dict) or not versions.get("server_version_num") or not versions.get("timescaledb_extension_version"):
                    errors.append("manifest v2 is missing PostgreSQL/TimescaleDB source version metadata")
                if not isinstance(manifest.get("filesystem_members"), list):
                    errors.append("manifest v2 is missing filesystem member inventory")
                image_inventory = manifest.get("image_inventory")
                if not isinstance(image_inventory, list) or not image_inventory:
                    errors.append("manifest v2 is missing running-container image inventory")
                else:
                    for image in image_inventory:
                        if not isinstance(image, dict) or not str(image.get("image_id", "")).startswith("sha256:") or not image.get("configured_image"):
                            errors.append("malformed running-container image inventory entry")
                            break
            database_members = {"database.dump"}
            if manifest.get("manifest_version", 1) >= 2 and isinstance(manifest.get("database_catalog"), list):
                database_members.update(entry.get("archive_member") for entry in manifest["database_catalog"] if isinstance(entry, dict) and isinstance(entry.get("archive_member"), str))
            for database_member in sorted(database_members):
                if database_member not in names:
                    continue
                with tempfile.TemporaryFile(mode="w+b") as database_stream:
                    with archive.open(database_member, "r") as archive_stream:
                        shutil.copyfileobj(archive_stream, database_stream, length=1024 * 1024)
                    database_stream.seek(0)
                    db_ok, db_detail = check_database_dump(database_stream)
                if not db_ok:
                    errors.append(f"database archive unreadable ({database_member}): " + db_detail)
                else:
                    print(f"PASS: {database_member}: {db_detail}")
            with tempfile.TemporaryFile(mode="w+b") as fs:
                with archive.open("filesystem.tar.gz", "r") as filesystem_stream:
                    shutil.copyfileobj(filesystem_stream, fs, length=1024 * 1024)
                fs.seek(0)
                with tarfile.open(fileobj=fs, mode="r:gz") as tar:
                    seen: set[str] = set()
                    actual_inventory = []
                    for member in tar:
                        if member.name in seen:
                            errors.append("duplicate filesystem member: " + member.name)
                        seen.add(member.name)
                        problem = validate_tar_member(member)
                        if problem:
                            errors.append(problem)
                        if manifest.get("manifest_version", 1) >= 2:
                            item = {"path": member.name, "type": "file" if member.isfile() else "directory" if member.isdir() else "symlink" if member.issym() else "hardlink" if member.islnk() else "other", "mode": member.mode, "uid": member.uid, "gid": member.gid, "size": member.size}
                            if member.isfile():
                                stream = tar.extractfile(member)
                                if stream is None:
                                    errors.append("cannot checksum filesystem member: " + member.name)
                                else:
                                    digest = hashlib.sha256()
                                    with stream:
                                        while True:
                                            chunk = stream.read(1024 * 1024)
                                            if not chunk:
                                                break
                                            digest.update(chunk)
                                    item["sha256"] = digest.hexdigest()
                            elif member.issym() or member.islnk():
                                item["link_target"] = member.linkname
                            actual_inventory.append(item)
                    if manifest.get("manifest_version", 1) >= 2 and actual_inventory != manifest.get("filesystem_members"):
                        errors.append("filesystem member inventory or per-file SHA-256 mismatch")
                    errors.extend(validate_certificates(tar, manifest))
                    total_unpacked = sum(max(0, m.size) for m in tar.getmembers() if m.isfile())
            database_payload_bytes = sum(archive.getinfo(name).file_size for name in database_members if name in names)
            globals_payload_bytes = archive.getinfo("globals.sql").file_size if "globals.sql" in names else 0
            required_free = total_unpacked + database_payload_bytes + globals_payload_bytes + (1024 * 1024 * 1024)
            free = shutil.disk_usage(BACKUP_ROOT if BACKUP_ROOT.exists() else path.parent).free
            if free < required_free:
                errors.append(f"insufficient free disk for safe staging: need at least {required_free} bytes, have {free}")
            print(f"Archive: {path}")
            print(f"Archive size: {path.stat().st_size} bytes")
            print(f"Filesystem expanded size: {total_unpacked} bytes")
            print(f"TLS inventory entries: {len(manifest.get('certificate_files', []))}")
            print(f"Available disk: {free} bytes")
            print(f"Required staging headroom: {required_free} bytes")
    except (OSError, zipfile.BadZipFile, tarfile.TarError, json.JSONDecodeError, ValueError, KeyError) as exc:
        errors.append(str(exc))

    if errors:
        print("NATIVE RESTORE PREFLIGHT: FAIL")
        for error in errors:
            print("ERROR: " + error)
        return 1
    for warning in warnings:
        print("WARNING: " + warning)
    print("NATIVE RESTORE PREFLIGHT: PASS (read-only; no files extracted, no services changed)")
    return 0


def stage_filesystem_archive(tar_path: Path, destination: Path) -> tuple[int, int, int]:
    """Reconstruct a disposable rootfs without following archived symlinks."""
    regular: list[tarfile.TarInfo] = []
    directories: list[tarfile.TarInfo] = []
    symlinks: list[tarfile.TarInfo] = []
    hardlinks: list[tarfile.TarInfo] = []
    with tarfile.open(tar_path, "r:gz") as tar:
        members = tar.getmembers()
        names: set[str] = set()
        for member in members:
            if member.name in names:
                raise ValueError(f"duplicate filesystem member during staging: {member.name}")
            names.add(member.name)
            problem = validate_tar_member(member)
            if problem:
                raise ValueError(problem)
            if member.isfile(): regular.append(member)
            elif member.isdir(): directories.append(member)
            elif member.issym(): symlinks.append(member)
            elif member.islnk(): hardlinks.append(member)

        for member in sorted(directories, key=lambda m: len(PurePosixPath(m.name).parts)):
            target = destination.joinpath(*PurePosixPath(member.name).parts)
            target.mkdir(parents=True, exist_ok=True)
        for member in regular:
            relative = PurePosixPath(member.name)
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            # Never allow an earlier archived link to become a parent path.
            current = destination
            for part in relative.parts[:-1]:
                current = current / part
                if current.is_symlink():
                    raise ValueError(f"archive file traverses a symlink parent: {member.name}")
            source = tar.extractfile(member)
            if source is None:
                raise ValueError(f"cannot read staged archive file: {member.name}")
            with source, target.open("xb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            target.chmod(member.mode & 0o777)
        for member in hardlinks:
            relative = PurePosixPath(member.name)
            target = destination.joinpath(*relative.parts)
            source_rel = PurePosixPath(member.linkname)
            source = destination.joinpath(*source_rel.parts)
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"hardlink source is not a staged regular file: {member.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(source, target)
        for member in symlinks:
            relative = PurePosixPath(member.name)
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            current = destination
            for part in relative.parts[:-1]:
                current = current / part
                if current.is_symlink():
                    raise ValueError(f"archive symlink traverses a symlink parent: {member.name}")
            if target.exists() or target.is_symlink():
                raise ValueError(f"staged symlink target already exists: {member.name}")
            os.symlink(member.linkname, target)
    return len(regular), sum(member.size for member in regular), len(symlinks) + len(hardlinks)


def isolated_database_restore(dump_path: Path, container_name: str, source_versions: dict | None = None, globals_path: Path | None = None, database_catalog: list | None = None) -> tuple[int, int]:
    """Restore into a new network-isolated, tmpfs-only PostgreSQL container."""
    image = "timescale/timescaledb:latest-pg16"
    inspect = subprocess.run(["docker", "image", "inspect", image], stdout=subprocess.DEVNULL,
                             stderr=subprocess.PIPE, check=False, timeout=30)
    if inspect.returncode != 0:
        raise RuntimeError(f"required local test image unavailable: {image}")
    run = subprocess.run([
        "docker", "run", "-d", "--rm", "--name", container_name, "--network", "none",
        "--tmpfs", "/var/lib/postgresql/data:rw,size=768m,mode=0700",
        "-e", "POSTGRES_USER=restore_admin", "-e", "POSTGRES_DB=postgres",
        "-e", "POSTGRES_PASSWORD=staging-only-not-production", image,
    ], capture_output=True, text=True, check=False, timeout=60)
    if run.returncode != 0:
        raise RuntimeError("could not start isolated PostgreSQL test container: " + run.stderr[-1200:])
    try:
        ready = False
        for _ in range(90):
            logs = subprocess.run(["docker", "logs", container_name], stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, check=False, timeout=10).stdout
            if "PostgreSQL init process complete; ready for start up." in logs:
                probe = subprocess.run(["docker", "exec", container_name, "pg_isready", "-U",
                                        "restore_admin", "-d", "postgres"], stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, check=False, timeout=10)
                if probe.returncode == 0:
                    ready = True
                    break
            import time
            time.sleep(1)
        if not ready:
            raise RuntimeError("isolated PostgreSQL did not become ready; production services were not touched")
        if source_versions:
            probe_sql = "SELECT current_setting('server_version_num'), coalesce((SELECT default_version FROM pg_available_extensions WHERE name='timescaledb'), '')"
            probe = subprocess.run(["docker", "exec", container_name, "psql", "-U", "restore_admin", "-d", "postgres", "-At", "-F", "|", "-c", probe_sql], capture_output=True, text=True, check=False, timeout=30)
            if probe.returncode != 0:
                raise RuntimeError("could not inspect isolated target database versions: " + probe.stderr[-1200:])
            target_parts = probe.stdout.strip().split("|")
            target_num = target_parts[0] if target_parts else ""
            target_major = int(target_num) // 10000 if target_num.isdigit() else None
            target_ts = target_parts[1] if len(target_parts) > 1 else ""
            version_entries = [source_versions]
            if database_catalog:
                version_entries = [entry.get("versions", {}) for entry in database_catalog if isinstance(entry, dict)]
            for versions in version_entries:
                if not isinstance(versions, dict):
                    raise TypeError("malformed source database version metadata; refusing isolated restore")
                source_num = str(versions.get("server_version_num", ""))
                source_major = int(source_num) // 10000 if source_num.isdigit() else None
                if source_major is None or target_major is None or source_major != target_major:
                    raise RuntimeError(f"PostgreSQL major-version mismatch: source={source_num} target={target_num}; refusing isolated restore")
                source_ts = str(versions.get("timescaledb_extension_version") or "")
                if source_ts and (not target_ts or source_ts != target_ts):
                    raise RuntimeError(f"TimescaleDB extension version mismatch: source={source_ts!r} target_available={target_ts!r}; refusing isolated restore")
        if globals_path is not None:
            with globals_path.open("rb") as source:
                globals_result = subprocess.run(["docker", "exec", "-i", container_name, "psql", "-v", "ON_ERROR_STOP=1", "-U", "restore_admin", "-d", "postgres"], stdin=source, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False, timeout=180)
            if globals_result.returncode != 0:
                raise RuntimeError("isolated PostgreSQL globals restore failed: " + globals_result.stderr.decode("utf-8", errors="replace")[-1600:])
        entries = database_catalog or [{"name": "manubisguard", "archive_member": "database.dump", "versions": source_versions or {}}]
        total_tables = total_extensions = 0
        for entry in entries:
            dbname = entry.get("name")
            member_name = entry.get("archive_member", "database.dump")
            if not isinstance(dbname, str) or not dbname or not isinstance(member_name, str):
                raise RuntimeError("invalid database catalog entry in staged restore")
            create = subprocess.run(["docker", "exec", container_name, "createdb", "-U", "restore_admin", "--", dbname], capture_output=True, text=True, check=False, timeout=30)
            if create.returncode != 0:
                raise RuntimeError(f"could not create isolated restore database {dbname!r}: " + create.stderr[-1200:])
            member_path = dump_path.parent / member_name
            if not member_path.is_file():
                raise RuntimeError("isolated database dump file missing: " + member_name)
            with member_path.open("rb") as source:
                restored = subprocess.run(["docker", "exec", "-i", container_name, "pg_restore", "-U", "restore_admin", "-d", dbname, "--exit-on-error", "--no-owner", "--no-acl"], stdin=source, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=False, check=False, timeout=900)
            if restored.returncode != 0:
                detail = restored.stderr.decode("utf-8", errors="replace")[-2000:]
                raise RuntimeError(f"isolated database restore failed for {dbname!r}: " + detail)
            query = "SELECT (SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema'))::text || ' ' || (SELECT count(*) FROM pg_extension)::text"
            result = subprocess.run(["docker", "exec", container_name, "psql", "-U", "restore_admin", "-d", dbname, "-Atqc", query], capture_output=True, text=True, check=False, timeout=30)
            if result.returncode != 0:
                raise RuntimeError(f"could not verify isolated database {dbname!r}: " + result.stderr[-1200:])
            parts = result.stdout.strip().split()
            if len(parts) != 2 or int(parts[0]) < 0 or int(parts[1]) < 0:
                raise RuntimeError(f"isolated database {dbname!r} returned invalid verification counts")
            total_tables += int(parts[0]); total_extensions += int(parts[1])
        return total_tables, total_extensions
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False, timeout=30)


def run_stage_test(path: Path) -> int:
    checked = validate_archive(path)
    if checked != 0:
        return checked
    with zipfile.ZipFile(path, "r") as source_archive:
        source_manifest = json.loads(source_archive.read("manifest.json"))
    source_versions = source_manifest.get("database_versions") if source_manifest.get("manifest_version", 1) >= 2 else None
    database_catalog = source_manifest.get("database_catalog") if source_manifest.get("manifest_version", 1) >= 2 else None
    BACKUP_ROOT.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix=".native-stage-", dir=str(BACKUP_ROOT.parent)) as td:
        workspace = Path(td)
        workspace.chmod(0o700)
        rootfs = workspace / "rootfs"
        rootfs.mkdir(mode=0o700)
        tar_path = workspace / "filesystem.tar.gz"
        dump_path = workspace / "database.dump"
        globals_path = workspace / "globals.sql"
        with zipfile.ZipFile(path, "r") as archive:
            extraction_members = ["filesystem.tar.gz", "database.dump"]
            if source_manifest.get("manifest_version", 1) >= 2:
                extraction_members.append("globals.sql")
                extraction_members.extend(entry["archive_member"] for entry in database_catalog if entry["archive_member"] != "database.dump")
            staged_paths = {"filesystem.tar.gz": tar_path, "database.dump": dump_path, "globals.sql": globals_path}
            for member_name in extraction_members:
                if not safe_member_name(member_name):
                    raise ValueError("unsafe staged payload path: " + member_name)
                target = staged_paths.get(member_name)
                if target is None:
                    target = workspace.joinpath(*PurePosixPath(member_name).parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    staged_paths[member_name] = target
                with archive.open(member_name) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                target.chmod(0o600)
        file_count, byte_count, link_count = stage_filesystem_archive(tar_path, rootfs)
        container_name = "manubisguard-restore-test-" + workspace.name.rsplit("-", 1)[-1]
        table_count, extension_count = isolated_database_restore(dump_path, container_name, source_versions, globals_path if globals_path.exists() else None, database_catalog)
        print("NATIVE STAGED RESTORE TEST: PASS")
        print("Filesystem stage: temporary isolated directory; auto-cleaned")
        print(f"Regular files staged: {file_count}")
        print(f"Regular file bytes staged: {byte_count}")
        print(f"Links reconstructed without following targets: {link_count}")
        print(f"Database restore: isolated container, tables={table_count}, extensions={extension_count}")
        print("Live panel containers, database, configuration and services were not used or changed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate/test a native ManubisGuard full backup safely.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="perform read-only archive and compatibility checks")
    mode.add_argument("--stage-test", action="store_true", help="test a full restore in temporary filesystem and isolated PostgreSQL; never applies to live paths")
    mode.add_argument("--apply", action="store_true", help="production restore (disabled until rollback and destination-preservation gates are implemented)")
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    path = args.archive.expanduser().resolve()
    if BACKUP_ROOT not in path.parents:
        print(f"ERROR: native restore archives must be stored under {BACKUP_ROOT}; no changes made.", file=sys.stderr)
        return 2
    if args.check:
        return validate_archive(path)
    if args.stage_test:
        try:
            return run_stage_test(path)
        except Exception as exc:
            print(f"NATIVE STAGED RESTORE TEST: FAIL: {exc}", file=sys.stderr)
            return 1
    print("ERROR: native production restore is not enabled: staged restore, safety backup and rollback gates are not yet implemented. No changes made.", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
