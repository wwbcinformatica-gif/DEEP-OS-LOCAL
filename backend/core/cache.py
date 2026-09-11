import threading
import time
from typing import Any

_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()
DEFAULT_TTL = 60


def get(key: str) -> Any | None:
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        expires, value = entry
        if time.monotonic() > expires:
            del _cache[key]
            return None
        return value


def set(key: str, value: Any, ttl: int = DEFAULT_TTL):
    with _cache_lock:
        _cache[key] = (time.monotonic() + ttl, value)


def invalidate(key: str):
    with _cache_lock:
        _cache.pop(key, None)


def clear():
    with _cache_lock:
        _cache.clear()
