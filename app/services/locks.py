import asyncio
from weakref import WeakValueDictionary

_locks = WeakValueDictionary()


def local_lock(key):
    """Serialize local SQLite work; PostgreSQL additionally uses row locks."""
    lock = _locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _locks[key] = lock
    return lock
