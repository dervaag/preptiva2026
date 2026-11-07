"""Manage the per-user macOS Kiri Share service and its changing public origin."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile

ROOT = Path.home() / 'Library/Application Support/PreptivaDeploy'
LABEL = 'com.preptiva.kiri-share'
KIRI = Path.home() / '.kiri/bin/kiri'
PLIST = Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')


def atomic_write(path, content):
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.share-')
    try:
        with os.fdopen(descriptor, 'w') as file:
            file.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def deployment_lock(root):
    # Same lock as auto_kiri.py: changing the origin must not race a deployment.
    with (root / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def active_directory(root):
    if (root / 'current').exists():
        release = (root / 'current').resolve()
        if release.parent != (root / 'releases').resolve():
            raise RuntimeError('Invalid release directory')
        return release
    return root / 'share/bootstrap'


def compose_up(directory):
    subprocess.run(['docker', '--context', 'kiri', 'compose', '--project-name', 'preptiva',
                    '--env-file', '.env', '--env-file', '.env.kiri', '-f', 'compose.kiri.yaml',
                    'up', '-d', '--no-build', '--wait', '--wait-timeout', '180'],
                   cwd=directory, check=True, timeout=240)


def apply_origin(root, url):
    # Accept only actual Kiri Share origins, never arbitrary event strings or wildcards.
    if not re.fullmatch(r'https://[a-z0-9]+(?:-[a-z0-9]+)*\.runkiri\.cloud', url):
        raise ValueError('Unexpected Kiri Share URL')
    with deployment_lock(root):
        active = active_directory(root)
        paths = {root / 'shared/.env.kiri', root / 'share/bootstrap/.env.kiri', active / '.env.kiri'}
        for path in paths:
            if not path.is_file() or path.is_symlink():
                raise RuntimeError('Missing or unsafe deployment environment')
            lines = [line for line in path.read_text().splitlines() if not line.startswith('PUBLIC_ORIGIN=')]
            content = '\n'.join(lines + ['PUBLIC_ORIGIN=' + url]) + '\n'
            if content != path.read_text():
                atomic_write(path, content)
        compose_up(active)


def state(root, status, url=None):
    atomic_write(root / 'share/status.json', json.dumps({
        'status': status, 'url': url,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }, indent=2) + '\n')


def serve(root):
    child = None

    def stop(signum, frame):
        if child is not None and child.poll() is None:
            child.terminate()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    state(root, 'starting')
    try:
        with deployment_lock(root):
            compose_up(active_directory(root))
        child = subprocess.Popen([str(KIRI), 'share', '127.0.0.1:18080', '--json'],
                                 stdout=subprocess.PIPE, text=True, bufsize=1)
        for line in child.stdout:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get('event') == 'live':
                url = event['url']
                apply_origin(root, url)
                state(root, 'ready', url)
                print('Share ready:', url, flush=True)
            elif event.get('event') in ('connecting', 'reconnecting', 'ended'):
                state(root, event['event'])
        child.wait()
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        state(root, 'stopped')


def install(root):
    source = Path(__file__).resolve().parents[1]
    share = root / 'share'
    share.mkdir(parents=True, exist_ok=True, mode=0o700)
    share.chmod(0o700)
    bootstrap = share / 'bootstrap'
    bootstrap.mkdir(exist_ok=True, mode=0o700)
    with deployment_lock(root):
        for name in ('.env', '.env.kiri'):
            original = root / 'shared' / name
            if not original.is_file() or original.is_symlink():
                raise RuntimeError('Run auto_kiri.py init first')
            if not (bootstrap / name).exists():
                atomic_write(bootstrap / name, original.read_text())
        shutil.copy2(source / 'compose.kiri.yaml', bootstrap / 'compose.kiri.yaml')
        shutil.copy2(Path(__file__), share / 'service.py')
    for name in ('stdout.log', 'stderr.log'):
        path = share / name
        path.touch(mode=0o600, exist_ok=True)
        path.chmod(0o600)
    configuration = {
        'Label': LABEL,
        'ProgramArguments': [sys.executable, '-u', str(share / 'service.py'), 'serve'],
        'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 30,
        'WorkingDirectory': str(share),
        'StandardOutPath': str(share / 'stdout.log'),
        'StandardErrorPath': str(share / 'stderr.log'),
        'EnvironmentVariables': {'PATH': str(KIRI.parent) + ':/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin'},
    }
    if PLIST.exists() and plistlib.loads(PLIST.read_bytes()) != configuration:
        raise RuntimeError('Existing LaunchAgent differs; not overwritten')
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(PLIST, plistlib.dumps(configuration).decode())
    service = f'gui/{os.getuid()}/{LABEL}'
    exists = subprocess.run(['launchctl', 'print', service], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if exists.returncode:
        subprocess.run(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(PLIST)], check=True)
    print('Autostart installed:', LABEL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['install', 'serve', 'status', 'stop', 'restart'])
    args = parser.parse_args()
    service = f'gui/{os.getuid()}/{LABEL}'
    if args.command == 'install':
        install(ROOT)
    elif args.command == 'serve':
        serve(ROOT)
    elif args.command == 'stop':
        subprocess.run(['launchctl', 'bootout', service], check=True)
        print('Share stopped for this login; remove the plist to disable future login autostart.')
    elif args.command == 'restart':
        subprocess.run(['launchctl', 'kickstart', '-k', service], check=True)
    else:
        result = subprocess.run(['launchctl', 'print', service], capture_output=True, text=True)
        print('LaunchAgent loaded:', result.returncode == 0)
        path = ROOT / 'share/status.json'
        if path.exists():
            print(path.read_text())


if __name__ == '__main__':
    main()
