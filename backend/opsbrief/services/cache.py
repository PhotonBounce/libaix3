"""OpsBrief — Redis caching layer.

Wraps redis-py for simple get/set with JSON serialization.
Gracefully degrades to in-memory dict if Redis is unavailable.
"""

from __future__ import annotations

import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

try:
    import redis
except ImportError:
    redis = None  # type: ignore

from ..config import settings

logger = logging.getLogger(__name__)

MAX_MEMORY_KEYS = 1000


@dataclass
class _MemoryEntry:
    value: Any
    expires_at: float


class Cache:
    """Simple cache with Redis backend and in-memory fallback."""

    def __init__(self) -> None:
        self._redis: Any | None = None
        self._memory: OrderedDict[str, _MemoryEntry] = OrderedDict()
        self._redis_available = False

        if redis is None:
            logger.warning("redis package not installed; using in-memory cache")
            return

        try:
            self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
            self._redis.ping()
            self._redis_available = True
            logger.info("Redis cache connected")
        except Exception as exc:
            logger.warning(f"Redis unavailable ({exc}); using in-memory cache")
            self._redis = None

    def _evict_if_needed(self) -> None:
        now = time.time()
        expired_keys = [k for k, v in self._memory.items() if v.expires_at < now]
        for k in expired_keys:
            del self._memory[k]
        if len(self._memory) >= MAX_MEMORY_KEYS:
            # Evict oldest by insertion order (LRU approximation)
            oldest = next(iter(self._memory))
            del self._memory[oldest]

    def get(self, key: str) -> Any | None:
        if self._redis_available and self._redis:
            try:
                raw = self._redis.get(key)
                if raw is not None:
                    return json.loads(raw)
            except Exception as exc:
                logger.debug(f"Redis get failed: {exc}")
        entry = self._memory.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.time():
            self._memory.pop(key, None)
            return None
        self._memory.move_to_end(key)
        return entry.value

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        serialized = json.dumps(value, default=str)
        if self._redis_available and self._redis:
            try:
                self._redis.setex(key, ttl, serialized)
                return
            except Exception as exc:
                logger.debug(f"Redis set failed: {exc}")
        self._evict_if_needed()
        self._memory[key] = _MemoryEntry(value=value, expires_at=time.time() + ttl)

    def delete(self, key: str) -> None:
        if self._redis_available and self._redis:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        self._memory.pop(key, None)

    def delete_pattern(self, pattern: str) -> None:
        # In-memory: iterate and delete matching keys
        for key in list(self._memory.keys()):
            if key.startswith(pattern):
                del self._memory[key]
        # Redis: use SCAN + DELETE
        if self._redis_available and self._redis:
            try:
                for key in self._redis.scan_iter(match=f"{pattern}*"):
                    self._redis.delete(key)
            except Exception:
                pass

    def flush(self) -> None:
        self._memory.clear()
        if self._redis_available and self._redis:
            try:
                self._redis.flushdb()
            except Exception:
                pass


# singleton
cache = Cache()
