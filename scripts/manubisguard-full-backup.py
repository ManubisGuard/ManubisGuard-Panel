#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

PROJECT = Path('/opt/manubisguard-panel')
BACKUP_ROOT = Path('/opt/manubisguard/backup')
OUT = BACKUP_ROOT / 'full'
COMPOSE = PROJECT / 'docker-compose.yml'
DEFAULT_RETENTION = 3
POLICY_FILE = Path('/etc/manubisguard/full-backup.conf')

def retention_count():
    value = DEFAULT_RETENTION
    if POLICY_FILE.is_file():
        for line in POLICY_FILE.read_text(errors='replace').splitlines():
            if line.strip().startswith('RETENTION_COUNT='):
                try:
                    candidate = int(line.split('=', 1)[1].strip())
                    if candidate >= 1:
                        value = candidate
                except ValueError:
                    pass
    return value
EXCLUDES = {
    'var/lib/manubisguard/timescaledb',
    'var/lib/manubisguard/backups',
    'opt/manubisguard-panel/backup',
    # Prevent recursively embedding archives stored beneath the canonical root.
    'opt/manubisguard/backup',
}
PATHS = [
    '/opt/manubisguard-panel', '/opt/manubisguard', '/opt/pg-node',
    '/opt/direct', '/opt/pasarguardbot', '/var/lib/manubisguard',
    '/var/lib/pg-node', '/var/lib/direct', '/etc/nginx',
    '/etc/letsencrypt', '/etc/manubisguard',
    '/usr/local/bin/manubis', '/usr/local/bin/manubisguard-restore-agent',
    '/usr/local/bin/manubisguard-migrate',
    '/etc/systemd/system',
    '/etc/docker/daemon.json', '/etc/cron.d',
]

def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Hash large backup artifacts incrementally without loading them into RAM."""
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_stream(stream, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def run(args, *, stdout=None, input_data=None):
    return subprocess.run(args, stdout=stdout, input=input_data, stderr=subprocess.PIPE, check=False)

def env_value(name, default):
    envfile = PROJECT / '.env'
    if envfile.is_file():
        for line in envfile.read_text(errors='replace').splitlines():
            line = line.strip()
            if line.startswith(name + '='):
                value = line.split('=', 1)[1].strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                    value = value[1:-1]
                return value
    return default

def discover_certificate_files():
    """Find active proxy and panel TLS files without printing their contents."""
    configured = set()
    nginx = shutil.which('nginx')
    if nginx:
        result = subprocess.run([nginx, '-T'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, text=True)
        if result.returncode != 0:
            raise RuntimeError('Could not inspect active Nginx configuration; refusing to create an unverified TLS backup.')
        for line in result.stdout.splitlines():
            match = re.match(r'\s*ssl_certificate(?:_key)?\s+([^;\s]+)\s*;', line)
            if match:
                configured.add(match.group(1))

    envfile = PROJECT / '.env'
    if envfile.is_file():
        for line in envfile.read_text(errors='replace').splitlines():
            match = re.match(r'\s*(?:UVICORN_SSL_CERTFILE|UVICORN_SSL_KEYFILE)\s*=\s*["\']?([^"\'#\s]+)', line)
            if match:
                configured.add(match.group(1))

    inventory, extra_paths = [], set()
    covered_roots = [Path(p) for p in PATHS if Path(p).is_dir()]
    for raw in sorted(configured):
        candidate = Path(raw)
        if not candidate.is_absolute():
            inventory.append({'configured_path': raw, 'exists': False, 'error': 'TLS path is not absolute'})
            raise RuntimeError(f'Configured TLS path is not absolute: {raw}')
        if not candidate.exists() or not candidate.is_file():
            inventory.append({'configured_path': raw, 'exists': False})
            raise RuntimeError(f'Configured TLS file is missing: {raw}')
        resolved = candidate.resolve(strict=True)
        digest = sha256_file(resolved)
        inventory.append({
            'configured_path': str(candidate),
            'resolved_path': str(resolved),
            'sha256': digest,
            'size': resolved.stat().st_size,
            'kind': 'private-key' if 'key' in candidate.name.lower() or 'privkey' in candidate.name.lower() else 'certificate-or-chain',
        })
        if not any(candidate == root or root in candidate.parents for root in covered_roots):
            extra_paths.add(candidate)
        if not any(resolved == root or root in resolved.parents for root in covered_roots):
            extra_paths.add(resolved)
    return inventory, sorted(extra_paths, key=str)


def validate_certificate_pairs(inventory):
    """Fail closed unless every configured private key matches a configured certificate."""
    keys = [item for item in inventory if item['kind'] == 'private-key']
    certs = [item for item in inventory if item['kind'] == 'certificate-or-chain']
    if not keys:
        return
    if not certs:
        raise RuntimeError('TLS private key was discovered but no certificate/chain was discovered.')
    for key in keys:
        key_path = key['resolved_path']
        key_pub = subprocess.run(['openssl', 'pkey', '-in', key_path, '-pubout'], capture_output=True, check=False)
        if key_pub.returncode != 0:
            raise RuntimeError('Could not validate a configured TLS private key: ' + key['configured_path'])
        matched = False
        for cert in certs:
            cert_pub = subprocess.run(['openssl', 'x509', '-in', cert['resolved_path'], '-pubkey', '-noout'], capture_output=True, check=False)
            if cert_pub.returncode == 0 and cert_pub.stdout == key_pub.stdout:
                matched = True
                break
        if not matched:
            raise RuntimeError('No configured TLS certificate matches private key: ' + key['configured_path'])


def inventory_filesystem_archive(tar_path):
    inventory = []
    with tarfile.open(tar_path, 'r:gz') as tar:
        for member in tar:
            item = {'path': member.name, 'type': 'file' if member.isfile() else 'directory' if member.isdir() else 'symlink' if member.issym() else 'hardlink' if member.islnk() else 'other', 'mode': member.mode, 'uid': member.uid, 'gid': member.gid, 'size': member.size}
            if member.isfile():
                stream = tar.extractfile(member)
                if stream is None:
                    raise RuntimeError('Could not read filesystem member for checksum inventory: ' + member.name)
                digest = hashlib.sha256()
                with stream:
                    while True:
                        chunk = stream.read(1024 * 1024)
                        if not chunk:
                            break
                        digest.update(chunk)
                item['sha256'] = digest.hexdigest()
            elif member.issym() or member.islnk():
                item['link_target'] = member.linkname
            inventory.append(item)
    return inventory

def filter_member(member):
    name = member.name.lstrip('./')
    for blocked in EXCLUDES:
        if name == blocked or name.startswith(blocked + '/'):
            return None
    if any(part in {'__pycache__', '.pytest_cache', '.mypy_cache'} for part in Path(name).parts):
        return None
    return member

def main():
    if os.geteuid() != 0:
        raise SystemExit('Run as root.')
    if not PROJECT.is_dir() or not COMPOSE.is_file():
        raise SystemExit('Panel project or Compose file not found; no changes made.')
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    BACKUP_ROOT.chmod(0o700)
    OUT.mkdir(parents=True, exist_ok=True, mode=0o700)
    OUT.chmod(0o700)
    if BACKUP_ROOT.stat().st_uid != 0 or OUT.stat().st_uid != 0:
        raise SystemExit('Backup directories must be owned by root.')
    free = shutil.disk_usage(OUT).free
    if free < 1024 * 1024 * 1024:
        raise SystemExit('Less than 1 GiB free; refusing to start backup.')
    stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')
    filename = f'manubisguard-full-{stamp}.zip'
    final = OUT / filename
    temp_zip = OUT / ('.' + filename + '.tmp')
    if final.exists() or final.with_suffix('.zip.sha256').exists():
        raise SystemExit('Refusing to overwrite an existing backup or checksum sidecar.')
    db_dump = None
    tar_path = None
    try:
        with tempfile.TemporaryDirectory(prefix='manubisguard-full-') as td:
            work = Path(td)
            db_dump = work / 'database.dump'
            tar_path = work / 'filesystem.tar.gz'
            user = env_value('POSTGRES_USER', 'manubisguard')
            dbname = env_value('POSTGRES_DB', 'manubisguard')
            version_sql = "SELECT json_build_object('server_version_num', current_setting('server_version_num'), 'server_version', version(), 'timescaledb_extension_version', (SELECT extversion FROM pg_extension WHERE extname='timescaledb'))::text"
            version_result = run(['docker', 'compose', '-f', str(COMPOSE), 'exec', '-T', 'timescaledb', 'psql', '-U', user, '-d', dbname, '-Atqc', version_sql], stdout=subprocess.PIPE)
            if version_result.returncode != 0:
                raise RuntimeError('Could not record source PostgreSQL/TimescaleDB versions; refusing an unversioned backup: ' + version_result.stderr.decode(errors='replace')[-1000:])
            try:
                database_versions = json.loads(version_result.stdout.decode().strip())
            except (ValueError, TypeError) as exc:
                raise RuntimeError('Source database version metadata was not valid JSON.') from exc
            if not isinstance(database_versions, dict) or not database_versions.get('server_version_num') or not database_versions.get('timescaledb_extension_version'):
                raise RuntimeError('Source database version metadata is incomplete; refusing backup.')
            catalog_sql = "SELECT coalesce(json_agg(datname ORDER BY datname), '[]'::json)::text FROM pg_database WHERE datallowconn AND NOT datistemplate AND datname <> 'postgres'"
            catalog_result = run(['docker', 'compose', '-f', str(COMPOSE), 'exec', '-T', 'timescaledb', 'psql', '-U', user, '-d', dbname, '-Atqc', catalog_sql], stdout=subprocess.PIPE)
            if catalog_result.returncode != 0:
                raise RuntimeError('Could not enumerate database catalog; refusing incomplete backup: ' + catalog_result.stderr.decode(errors='replace')[-1000:])
            try:
                database_names = json.loads(catalog_result.stdout.decode().strip())
            except (ValueError, TypeError) as exc:
                raise RuntimeError('Database catalog was not valid JSON.') from exc
            if not isinstance(database_names, list) or not database_names or dbname not in database_names or any(not isinstance(n, str) or not n for n in database_names):
                raise RuntimeError('Database catalog is incomplete or does not include configured POSTGRES_DB.')
            globals_dump = work / 'globals.sql'
            with globals_dump.open('wb') as globals_handle:
                globals_result = run(['docker', 'compose', '-f', str(COMPOSE), 'exec', '-T', 'timescaledb', 'pg_dumpall', '-U', user, '--globals-only'], stdout=globals_handle)
            if globals_result.returncode != 0 or not globals_dump.stat().st_size:
                raise RuntimeError('PostgreSQL global roles/settings dump failed: ' + globals_result.stderr.decode(errors='replace')[-1500:])
            globals_dump.chmod(0o600)
            database_catalog = []
            database_dumps = {}
            for index, database_name in enumerate(database_names):
                target_dump = db_dump if database_name == dbname else work / f'database-{index:04d}.dump'
                with target_dump.open('wb') as handle:
                    proc = run(['docker', 'compose', '-f', str(COMPOSE), 'exec', '-T', 'timescaledb', 'pg_dump', '-U', user, '-d', database_name, '-Fc', '--no-owner', '--no-acl'], stdout=handle)
                if proc.returncode != 0 or target_dump.stat().st_size == 0:
                    raise RuntimeError(f'Database dump failed for {database_name!r}: ' + proc.stderr.decode(errors='replace')[-1500:])
                check = run(['docker', 'run', '--rm', '-i', '--network', 'none', '--read-only', '--tmpfs', '/tmp:rw,noexec,nosuid,size=16m', '--entrypoint', 'pg_restore', 'timescale/timescaledb:latest-pg16', '--list'], input_data=target_dump.read_bytes(), stdout=subprocess.DEVNULL)
                if check.returncode != 0:
                    raise RuntimeError(f'Database archive validation failed for {database_name!r}: ' + check.stderr.decode(errors='replace')[-1000:])
                member_name = 'database.dump' if database_name == dbname else f'databases/{index:04d}.dump'
                database_dumps[member_name] = target_dump
                db_version_sql = "SELECT json_build_object('server_version_num', current_setting('server_version_num'), 'timescaledb_extension_version', (SELECT extversion FROM pg_extension WHERE extname='timescaledb'))::text"
                db_version_result = run(['docker', 'compose', '-f', str(COMPOSE), 'exec', '-T', 'timescaledb', 'psql', '-U', user, '-d', database_name, '-Atqc', db_version_sql], stdout=subprocess.PIPE)
                if db_version_result.returncode != 0:
                    raise RuntimeError(f'Could not record version metadata for database {database_name!r}.')
                database_catalog.append({'name': database_name, 'archive_member': member_name, 'versions': json.loads(db_version_result.stdout.decode().strip())})
            certificate_files, extra_certificate_paths = discover_certificate_files()
            validate_certificate_pairs(certificate_files)
            container_ids_result = subprocess.run(['docker', 'ps', '-q'], capture_output=True, text=True, check=False)
            if container_ids_result.returncode != 0 or not container_ids_result.stdout.strip():
                raise RuntimeError('Could not enumerate running Docker containers for the recovery inventory.')
            inspect_result = subprocess.run(['docker', 'inspect', *container_ids_result.stdout.split()], capture_output=True, text=True, check=False)
            if inspect_result.returncode != 0:
                raise RuntimeError('Could not capture exact running-container image metadata: ' + inspect_result.stderr[-1200:])
            try:
                inspected_containers = json.loads(inspect_result.stdout)
            except (ValueError, TypeError) as exc:
                raise RuntimeError('Docker inspect image metadata was not valid JSON.') from exc
            image_ids = sorted({item.get('Image', '') for item in inspected_containers if item.get('Image')})
            image_inspect_result = subprocess.run(['docker', 'image', 'inspect', *image_ids], capture_output=True, text=True, check=False)
            if image_inspect_result.returncode != 0:
                raise RuntimeError('Could not capture immutable Docker image digests: ' + image_inspect_result.stderr[-1200:])
            try:
                inspected_images = json.loads(image_inspect_result.stdout)
            except (ValueError, TypeError) as exc:
                raise RuntimeError('Docker image inspect metadata was not valid JSON.') from exc
            image_meta_by_id = {image.get('Id'): image for image in inspected_images if image.get('Id')}
            image_inventory = []
            for item in inspected_containers:
                config = item.get('Config') or {}
                image_meta = image_meta_by_id.get(item.get('Image'), {})
                repo_digests = image_meta.get('RepoDigests') or []
                image_inventory.append({
                    'container_name': (item.get('Name') or '').lstrip('/'),
                    'configured_image': config.get('Image') or '',
                    'image_id': item.get('Image') or '',
                    'repo_digests': sorted({x for x in repo_digests if isinstance(x, str)}),
                    'digest_pinned': bool(repo_digests),
                })
            if not image_inventory or any(not item['image_id'].startswith('sha256:') or not item['configured_image'] for item in image_inventory):
                raise RuntimeError('Running-container image inventory is incomplete; refusing an unverifiable backup.')
            included, missing = [], []
            with tarfile.open(tar_path, 'w:gz', compresslevel=3) as tar:
                for raw in PATHS:
                    path = Path(raw)
                    if not path.exists() and not path.is_symlink():
                        missing.append(raw)
                        continue
                    tar.add(str(path), arcname=str(path).lstrip('/'), recursive=True, filter=filter_member)
                    included.append(raw)
                for path in extra_certificate_paths:
                    tar.add(str(path), arcname=str(path).lstrip('/'), recursive=True, filter=filter_member)
                    included.append(str(path))
                runtime = {
                    'created_at_utc': datetime.now(UTC).isoformat(),
                    'hostname': subprocess.run(['hostname'], capture_output=True, text=True, check=False).stdout.strip(),
                    'docker_ps': subprocess.run(['docker', 'ps', '--no-trunc'], capture_output=True, text=True, check=False).stdout,
                    'images': subprocess.run(['docker', 'images', '--digests', '--no-trunc'], capture_output=True, text=True, check=False).stdout,
                    'docker_inspect_json': inspect_result.stdout,
                    'image_inventory': image_inventory,
                    'systemd_units': subprocess.run(['systemctl', 'list-unit-files', '--no-pager'], capture_output=True, text=True, check=False).stdout,
                    'included_paths': included,
                    'paths_not_present': missing,
                    'excluded_paths': sorted(EXCLUDES),
                    'certificate_files': certificate_files,
                    'database': dbname,
                    'database_user': user,
                    'database_dump_format': 'Per-database PostgreSQL custom archives; each validated with pg_restore --list',
                    'database_catalog': database_catalog,
                    'globals_dump': 'globals.sql',
                    'notes': ['Live database data directory is intentionally excluded; logical dumps and PostgreSQL globals are included instead.', 'Each database dump is internally consistent, but PostgreSQL does not provide a single atomic snapshot across multiple databases; coordinate maintenance if cross-database consistency is required.', 'Remote hosts are not backed up by this archive; only node data and configuration present on this host are included.']
                }
            with tarfile.open(tar_path, 'r:gz') as verify_tar:
                members = {member.name: member for member in verify_tar.getmembers()}
                for cert in certificate_files:
                    resolved_member = cert['resolved_path'].lstrip('/')
                    member = members.get(resolved_member)
                    if member is None or not member.isfile():
                        raise RuntimeError('Required TLS file is not present as a regular archive member: ' + cert['resolved_path'])
                    extracted = verify_tar.extractfile(member)
                    if extracted is None or sha256_stream(extracted) != cert['sha256']:
                        raise RuntimeError('TLS file archive checksum mismatch: ' + cert['configured_path'])
            filesystem_inventory = inventory_filesystem_archive(tar_path)
            payload_checksums = {
                'database.dump': sha256_file(db_dump),
                'globals.sql': sha256_file(globals_dump),
                'filesystem.tar.gz': sha256_file(tar_path),
                'runtime-inventory.json': hashlib.sha256(json.dumps(runtime, indent=2, sort_keys=True).encode()).hexdigest(),
            }
            for member_name, dump_path in database_dumps.items():
                payload_checksums[member_name] = sha256_file(dump_path)
            manifest = {
                'manifest_version': 2,
                'product': 'ManubisGuard', 'kind': 'full-host-panel-backup',
                'created_at_utc': datetime.now(UTC).isoformat(),
                'hostname': subprocess.run(['hostname'], capture_output=True, text=True, check=False).stdout.strip(),
                'database_dump': 'database.dump', 'filesystem_archive': 'filesystem.tar.gz',
                'database_versions': database_versions,
                'database_catalog': database_catalog,
                'image_inventory': image_inventory,
                'globals_dump': 'globals.sql',
                'payload_sha256': payload_checksums,
                'filesystem_members': filesystem_inventory,
                'database_dump_sha256': hashlib.sha256(db_dump.read_bytes()).hexdigest(),
                'filesystem_archive_sha256': hashlib.sha256(tar_path.read_bytes()).hexdigest(),
                'included_paths': included, 'paths_not_present': missing,
                'excluded_paths': sorted(EXCLUDES),
                'certificate_files': certificate_files,
                'backup_root': str(BACKUP_ROOT),
                'validation': {'pg_restore_list': 'passed', 'tls_files_archived_and_sha256_verified': True, 'zip_integrity': 'checked after write'},
                'security': 'Contains secrets and private keys. Keep archive restricted to root.'
            }
            with zipfile.ZipFile(temp_zip, 'w', compression=zipfile.ZIP_STORED) as z:
                z.write(db_dump, 'database.dump')
                z.write(globals_dump, 'globals.sql')
                for member_name, dump_path in database_dumps.items():
                    if member_name != 'database.dump':
                        z.write(dump_path, member_name)
                z.write(tar_path, 'filesystem.tar.gz')
                z.writestr('manifest.json', json.dumps(manifest, indent=2, sort_keys=True))
                z.writestr('runtime-inventory.json', json.dumps(runtime, indent=2, sort_keys=True))
            with zipfile.ZipFile(temp_zip, 'r') as z:
                bad = z.testzip()
                required = {'database.dump', 'globals.sql', 'filesystem.tar.gz', 'manifest.json', 'runtime-inventory.json'} | set(database_dumps)
                if bad or not required.issubset(set(z.namelist())):
                    raise RuntimeError(f'ZIP verification failed: {bad or "required member missing"}')
            os.chmod(temp_zip, 0o600)
            try:
                os.link(temp_zip, final)  # atomic create; fails rather than replacing an existing archive
            except FileExistsError as exc:
                raise RuntimeError('Refusing to overwrite an existing full backup archive.') from exc
            temp_zip.unlink()
            final.chmod(0o600)
            digest = sha256_file(final)
            sidecar = final.with_suffix('.zip.sha256')
            sidecar.write_text(f'{digest}  {final.name}\n')
            sidecar.chmod(0o600)
        archives = sorted(OUT.glob('manubisguard-full-*.zip'), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in archives[retention_count():]:
            old.unlink(missing_ok=True)
            old.with_suffix('.zip.sha256').unlink(missing_ok=True)
        print('FULL BACKUP OK')
        print(f'file={final}')
        print(f'size={final.stat().st_size}')
        print(f'sha256={digest}')
        print(f'included_paths={len(included)}')
        print(f'paths_not_present={len(missing)}')
    finally:
        if temp_zip.exists():
            temp_zip.unlink()

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'FULL BACKUP FAILED: {exc}', file=sys.stderr)
        raise SystemExit(1)
