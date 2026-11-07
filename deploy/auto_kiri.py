"""Deploy tested main commits to one Mac's Kiri; secrets/data stay on that Mac."""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request

SOURCE = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = Path.home() / 'Library/Application Support/PreptivaDeploy'
REPOSITORY = 'dervaag/preptiva2026'
SECRET_FILES = ('.env', '.env.kiri')


def run(args, cwd=None, capture=False):
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


@contextmanager
def locked(root):
    if root.is_symlink():
        raise RuntimeError('Direktori deployment tidak boleh symlink.')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    with (root / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def initialize(source, root):
    """Copy secrets once, preserving the credentials of existing database volumes."""
    shared = root / 'shared'
    shared.mkdir(mode=0o700, exist_ok=True)
    for name in SECRET_FILES:
        origin, destination = source / name, shared / name
        if destination.is_symlink() or origin.is_symlink():
            raise RuntimeError('File environment tidak boleh symlink.')
        if destination.exists():
            destination.chmod(0o600)
            continue
        if not origin.is_file():
            raise RuntimeError('Siapkan .env dan .env.kiri dengan deploy/kiri.sh config dulu.')
        with destination.open('xb') as target:
            os.chmod(destination, 0o600)
            target.write(origin.read_bytes())
    print('Environment deployment tersedia; kredensial yang sudah ada dipertahankan.')


def excluded(directory, names):
    return [name for name in names if name in {'.git', '__pycache__', '.DS_Store'}
            or name.startswith('.env') or name.endswith(('.pem', '.key', '.pyc'))]


def copy_source(source, release):
    # Only runtime inputs; no git metadata, private keys, test artifacts or user data.
    for name in ('Dockerfile', 'requirements.txt', '.dockerignore', 'compose.kiri.yaml',
                 'app', 'docs', 'deploy/kiri.sh', 'deploy/configure_kiri.py'):
        origin = source / name
        candidates = [origin] + (list(origin.rglob('*')) if origin.is_dir() else [])
        if any(path.is_symlink() for path in candidates):
            raise RuntimeError('Symlink pada sumber deployment tidak didukung.')
        destination = release / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if origin.is_dir():
            shutil.copytree(origin, destination, ignore=excluded)
        else:
            shutil.copy2(origin, destination)


def stage(source, root, revision):
    releases = root / 'releases'
    releases.mkdir(exist_ok=True, mode=0o700)
    release = Path(tempfile.mkdtemp(prefix=revision[:12] + '-', dir=releases))
    copy_source(source, release)
    for name in SECRET_FILES:
        origin = root / 'shared' / name
        if origin.is_symlink() or not origin.is_file():
            raise RuntimeError('Jalankan init; shared/.env dan shared/.env.kiri wajib tersedia.')
        shutil.copyfile(origin, release / name)
        (release / name).chmod(0o600)
    # Unique image per attempt, so a rebuild never replaces the previous release image.
    with (release / '.env.kiri').open('a') as file:
        file.write('\nPREPTIVA_IMAGE=preptiva:' + release.name + '\n')
    (release / 'revision').write_text(revision + '\n')
    return release


def compose(release, *args):
    run(['docker', '--context', 'kiri', 'compose', '--project-name', 'preptiva',
         '--env-file', '.env', '--env-file', '.env.kiri', '-f', 'compose.kiri.yaml', *args],
        cwd=release)


def latest_main(revision):
    """Fail closed on API errors; old queued jobs must not overwrite a newer main."""
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        return True
    if (os.environ.get('GITHUB_REPOSITORY') != REPOSITORY
            or os.environ.get('GITHUB_REF') != 'refs/heads/main'
            or os.environ.get('GITHUB_EVENT_NAME') not in ('push', 'workflow_dispatch')):
        raise RuntimeError('Deployment otomatis hanya menerima main dari repository yang ditetapkan.')
    request = urllib.request.Request(
        f'https://api.github.com/repos/{REPOSITORY}/git/ref/heads/main',
        headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                 'Accept': 'application/vnd.github+json', 'User-Agent': 'preptiva-deploy'})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)['object']['sha'] == revision


def current_release(root):
    pointer = root / 'current'
    if not pointer.exists():
        return None
    release = pointer.resolve()
    if release.parent != (root / 'releases').resolve():
        raise RuntimeError('Pointer release berada di luar direktori deployment.')
    return release


def activate(root, release):
    previous = current_release(root)
    try:
        compose(release, 'up', '-d', '--no-build', '--wait', '--wait-timeout', '180')
    except subprocess.CalledProcessError:
        if previous:
            print('Healthcheck gagal; memulihkan container dari release sebelumnya.', flush=True)
            compose(previous, 'up', '-d', '--no-build', '--wait', '--wait-timeout', '180')
        else:
            print('Belum ada release otomatis sebelumnya; periksa service dengan deploy/kiri.sh ps.')
        raise
    temporary = root / 'current.next'
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(release)
    temporary.replace(root / 'current')


def deploy(source, root, revision):
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise RuntimeError('Revision harus berupa commit SHA lengkap.')
    if run(['git', 'rev-parse', 'HEAD'], cwd=source, capture=True).strip() != revision:
        raise RuntimeError('Checkout berbeda dari commit yang sudah dites.')
    run(['git', 'diff', '--exit-code', '--quiet', 'HEAD', '--'], cwd=source)
    if not latest_main(revision):
        print('Dilewati: commit ini sudah digantikan oleh main yang lebih baru.')
        return
    release = stage(source, root, revision)
    compose(release, 'config', '--quiet')
    compose(release, 'build', 'web')
    if not latest_main(revision):
        print('Dilewati: main berubah selama build; menunggu workflow commit terbaru.')
        return
    activate(root, release)
    print('Deployment healthy:', revision)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'deploy', 'status'])
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--revision')
    args = parser.parse_args()
    args.root = args.root.expanduser().absolute()
    with locked(args.root):
        if args.command == 'init':
            initialize(SOURCE, args.root)
        elif args.command == 'status':
            release = current_release(args.root)
            print('Release aktif:', release.name if release else 'belum ada deployment otomatis')
            if release:
                compose(release, 'ps')
        else:
            if not args.revision:
                parser.error('--revision wajib untuk deploy')
            deploy(SOURCE, args.root, args.revision)


if __name__ == '__main__':
    main()
