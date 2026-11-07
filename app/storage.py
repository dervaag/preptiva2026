"""Session-scoped audio storage, with cross-process deletion/write exclusion."""
from contextlib import contextmanager, nullcontext
from datetime import timezone
import fcntl
import hashlib
import os
from pathlib import Path
import re
import shutil
from uuid import uuid4

from app.config import ROOT


class SessionStorageDeleted(RuntimeError):
    pass


def _session_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,100}', value):
        raise ValueError('Identitas penyimpanan sesi tidak valid.')
    return value


def _safe_directory(path, create=False):
    base = ROOT / 'data'
    if base.is_symlink():
        raise ValueError('Symlink penyimpanan tidak didukung.')
    relative = path.relative_to(base)
    current = base
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Symlink penyimpanan tidak didukung.')
    if create:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def _marker(uuid):
    digest = hashlib.sha256(_session_id(uuid).encode()).hexdigest()
    return _safe_directory(ROOT / 'data/privacy_deleted') / digest


def _assert_live(uuid):
    marker = _marker(uuid)
    if marker.exists() or marker.is_symlink():
        raise SessionStorageDeleted('Penyimpanan sesi sudah dihapus.')


@contextmanager
def _guard(uuid):
    digest = hashlib.sha256(_session_id(uuid).encode()).hexdigest()
    directory = _safe_directory(ROOT / 'data/privacy_locks', create=True)
    descriptor = os.open(directory / digest, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _audio_path(uuid, name, cache=False, create=False):
    _session_id(uuid)
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]+\.mp3', name):
        raise ValueError('Nama audio tidak valid.')
    directory = ROOT / 'data/audio' / uuid
    if cache:
        directory /= 'cache'
    path = _safe_directory(directory, create=create) / name
    if path.is_symlink():
        raise ValueError('Symlink audio tidak didukung.')
    return path


def audio_dir(uuid):
    """Compatibility for fixtures; production writes use write_session_audio."""
    with _guard(uuid):
        _assert_live(uuid)
        return _safe_directory(ROOT / 'data/audio' / _session_id(uuid), create=True)


def safe_audio_path(uuid, name):
    # Read endpoints never recreate missing audio directories.
    try:
        _assert_live(uuid)
        path = _audio_path(uuid, name)
        return path if path.is_file() else None
    except (ValueError, SessionStorageDeleted):
        return None


def session_cache_path(uuid, key):
    name = key if key.endswith('.mp3') else key + '.mp3'
    _assert_live(uuid)
    return _audio_path(uuid, name, cache=True)


def read_session_audio(uuid, name, cache=False):
    with _guard(uuid):
        _assert_live(uuid)
        path = _audio_path(uuid, name, cache=cache)
        return path.read_bytes() if path.is_file() else None


def write_session_audio(uuid, name, content, cache=False):
    """The final write and deletion marker share a file lock across web/worker."""
    with _guard(uuid):
        _assert_live(uuid)
        target = _audio_path(uuid, name, cache=cache, create=True)
        temporary = target.parent / ('.write-' + uuid4().hex + '.tmp')
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'wb') as output:
                output.write(content)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        return target


def _remove_tree(directory):
    if directory.is_symlink():
        directory.unlink()
        return 1
    if not directory.exists():
        return 0
    count = sum(len(files) + sum(Path(root, d).is_symlink() for d in dirs)
                for root, dirs, files in os.walk(directory, followlinks=False))
    shutil.rmtree(directory)
    return count


def mark_session_deleted(uuid):
    """Content-free hashed tombstones survive receipts to reject delayed writers."""
    with _guard(uuid):
        marker = _marker(uuid)
        _safe_directory(marker.parent, create=True)
        descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'wb') as output:
            output.write(b'deleted\n')
            output.flush()
            os.fsync(output.fileno())
        # A session-directory symlink can be unlinked safely, but an audio-root
        # symlink must never let rmtree traverse into an external parent.
        _safe_directory(ROOT / 'data/audio')
        return _remove_tree(ROOT / 'data/audio' / _session_id(uuid))


def purge_session_files(uuid):
    return mark_session_deleted(uuid)


def purge_legacy_caches():
    """Old global TTS caches have no owner map and cannot be selectively retained."""
    with _guard('legacy-cache-cleanup'):
        return sum(_remove_tree(ROOT / 'data' / name)
                   for name in ('tts_cache', 'tts_stream_cache'))


def expire_audio(before, *, apply=False):
    """Remove old audio/cache files by mtime; do not follow filesystem links."""
    base = _safe_directory(ROOT / 'data/audio')
    if not base.exists():
        return 0
    count = 0
    deadline = before.replace(tzinfo=timezone.utc).timestamp() if before.tzinfo is None else before.timestamp()
    for directory in base.iterdir():
        if not directory.is_dir() or directory.is_symlink():
            continue
        try:
            _session_id(directory.name)
        except ValueError:
            continue
        with _guard(directory.name) if apply else nullcontext():
            for root, dirs, files in os.walk(directory, topdown=False, followlinks=False):
                for name in files:
                    path = Path(root) / name
                    if path.is_symlink() or path.stat().st_mtime >= deadline:
                        continue
                    count += 1
                    if apply:
                        path.unlink(missing_ok=True)
                if apply:
                    for name in dirs:
                        path = Path(root) / name
                        if not path.is_symlink():
                            try:
                                path.rmdir()
                            except OSError:
                                pass
            if apply:
                try:
                    directory.rmdir()
                except OSError:
                    pass
    return count
