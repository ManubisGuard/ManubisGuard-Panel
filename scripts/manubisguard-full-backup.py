#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, shutil, subprocess, sys, tempfile, zipfile
from datetime import datetime, timezone
from pathlib import Path
import tarfile

PROJECT = Path('/opt/manubisguard-panel')
OUT = Path('/var/lib/manubisguard/backups/full')
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
    OUT.mkdir(parents=True, exist_ok=True, mode=0o700)
    OUT.chmod(0o700)
    free = shutil.disk_usage(OUT).free
    if free < 1024 * 1024 * 1024:
        raise SystemExit('Less than 1 GiB free; refusing to start backup.')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    filename = f'manubisguard-full-{stamp}.zip'
    final = OUT / filename
    temp_zip = OUT / ('.' + filename + '.tmp')
    db_dump = None
    tar_path = None
    try:
        with tempfile.TemporaryDirectory(prefix='manubisguard-full-') as td:
            work = Path(td)
            db_dump = work / 'database.dump'
            tar_path = work / 'filesystem.tar.gz'
            user = env_value('POSTGRES_USER', 'manubisguard')
            dbname = env_value('POSTGRES_DB', 'manubisguard')
            with db_dump.open('wb') as handle:
                proc = run(['docker', 'compose', '-f', str(COMPOSE), 'exec', '-T', 'timescaledb', 'pg_dump', '-U', user, '-d', dbname, '-Fc', '--no-owner', '--no-acl'], stdout=handle)
            if proc.returncode != 0 or db_dump.stat().st_size == 0:
                raise RuntimeError('Database dump failed: ' + proc.stderr.decode(errors='replace')[-1500:])
            check = run(['docker', 'compose', '-f', str(COMPOSE), 'exec', '-T', 'timescaledb', 'pg_restore', '--list'], input_data=db_dump.read_bytes(), stdout=subprocess.DEVNULL)
            if check.returncode != 0:
                raise RuntimeError('Database archive validation failed: ' + check.stderr.decode(errors='replace')[-1500:])
            included, missing = [], []
            with tarfile.open(tar_path, 'w:gz', compresslevel=3) as tar:
                for raw in PATHS:
                    path = Path(raw)
                    if not path.exists() and not path.is_symlink():
                        missing.append(raw)
                        continue
                    tar.add(str(path), arcname=str(path).lstrip('/'), recursive=True, filter=filter_member)
                    included.append(raw)
                runtime = {
                    'created_at_utc': datetime.now(timezone.utc).isoformat(),
                    'hostname': subprocess.run(['hostname'], capture_output=True, text=True).stdout.strip(),
                    'docker_ps': subprocess.run(['docker', 'ps', '--no-trunc'], capture_output=True, text=True).stdout,
                    'images': subprocess.run(['docker', 'images', '--digests', '--no-trunc'], capture_output=True, text=True).stdout,
                    'docker_inspect_json': subprocess.run(['docker', 'inspect', *subprocess.run(['docker', 'ps', '-q'], capture_output=True, text=True).stdout.split()], capture_output=True, text=True).stdout,
                    'systemd_units': subprocess.run(['systemctl', 'list-unit-files', '--no-pager'], capture_output=True, text=True).stdout,
                    'included_paths': included,
                    'paths_not_present': missing,
                    'excluded_paths': sorted(EXCLUDES),
                    'database': dbname,
                    'database_user': user,
                    'database_dump_format': 'PostgreSQL custom archive; validated with pg_restore --list',
                    'notes': ['Live database data directory is intentionally excluded; a consistent logical dump is included instead.', 'Remote hosts are not backed up by this archive; only node data and configuration present on this host are included.']
                }
            manifest = {
                'product': 'ManubisGuard', 'kind': 'full-host-panel-backup',
                'created_at_utc': datetime.now(timezone.utc).isoformat(),
                'hostname': subprocess.run(['hostname'], capture_output=True, text=True).stdout.strip(),
                'database_dump': 'database.dump', 'filesystem_archive': 'filesystem.tar.gz',
                'database_dump_sha256': hashlib.sha256(db_dump.read_bytes()).hexdigest(),
                'filesystem_archive_sha256': hashlib.sha256(tar_path.read_bytes()).hexdigest(),
                'included_paths': included, 'paths_not_present': missing,
                'excluded_paths': sorted(EXCLUDES),
                'validation': {'pg_restore_list': 'passed', 'zip_integrity': 'checked after write'},
                'security': 'Contains secrets and private keys. Keep archive restricted to root.'
            }
            with zipfile.ZipFile(temp_zip, 'w', compression=zipfile.ZIP_STORED) as z:
                z.write(db_dump, 'database.dump')
                z.write(tar_path, 'filesystem.tar.gz')
                z.writestr('manifest.json', json.dumps(manifest, indent=2, sort_keys=True))
                z.writestr('runtime-inventory.json', json.dumps(runtime, indent=2, sort_keys=True))
            with zipfile.ZipFile(temp_zip, 'r') as z:
                bad = z.testzip()
                required = {'database.dump', 'filesystem.tar.gz', 'manifest.json', 'runtime-inventory.json'}
                if bad or not required.issubset(set(z.namelist())):
                    raise RuntimeError(f'ZIP verification failed: {bad or "required member missing"}')
            os.chmod(temp_zip, 0o600)
            os.replace(temp_zip, final)
            final.chmod(0o600)
            digest = hashlib.sha256(final.read_bytes()).hexdigest()
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
