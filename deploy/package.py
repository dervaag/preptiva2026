"""Build a source-only VM deployment archive using an explicit allowlist.

Run from the repository root: python3 deploy/package.py
Secrets, SSH keys, Git history, local databases and test artifacts are never included.
"""
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/deploy/preptiva-source.tar.gz'
FILES = ('Dockerfile', 'compose.yaml', 'requirements.txt', '.dockerignore', 'README.md', '.env.example', 'deploy/nginx.conf')
DIRECTORIES = ('app', 'docs')
BLOCKED_SUFFIXES = {'.pem', '.key', '.pyc', '.pyo', '.db', '.sqlite', '.sqlite3'}


def allowed(path):
    relative = path.relative_to(ROOT)
    return (path.is_file() and not path.is_symlink() and path.suffix.lower() not in BLOCKED_SUFFIXES
            and '__pycache__' not in relative.parts
            and not any(part.startswith('.') for part in relative.parts if part not in ('.dockerignore', '.env.example')))


def main():
    candidates = [ROOT / name for name in FILES]
    for name in DIRECTORIES:
        candidates.extend((ROOT / name).rglob('*'))
    members = sorted({path for path in candidates if allowed(path)})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(OUTPUT, 'w:gz') as archive:
        for path in members:
            archive.add(path, arcname=path.relative_to(ROOT), recursive=False)
    with tarfile.open(OUTPUT, 'r:gz') as archive:
        names = archive.getnames()
        assert all(not name.endswith(('.pem', '.key')) for name in names)
        assert '.env' not in names and not any(name.startswith(('.git/', 'data/', 'artifacts/')) for name in names)
    print(f'Paket source: {OUTPUT.relative_to(ROOT)} ({len(members)} file, {OUTPUT.stat().st_size:,} byte)')
    print('Tanpa .env, private key, riwayat Git, database, atau artefak pengujian.')


if __name__ == '__main__':
    main()
