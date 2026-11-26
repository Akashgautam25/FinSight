"""
FinSight AI — Cache Utilities
Uses Redis when REDIS_URL is configured and reachable; otherwise an in-process
TTL cache. Cache failures never break a request — they just behave like a miss.
"""

import fnmatch
import json
import logging
import time
from typing import Any, Dict, Optional, Tuple

from app.config import settings

logger = logging.getLogger("finsight.cache")


class _MemoryCache:
    """Minimal async-compatible TTL cache (single process)."""

    def __init__(self, max_items: int = 5000):
        self._store: Dict[str, Tuple[float, str]] = {}
        self._max_items = max_items

    async def get(self, key: str) -> Optional[str]:
        item = self._store.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at < time.monotonic():
            self._store.pop(key, None)
            return None
        return value

    async def setex(self, key: str, ttl: int, value: str) -> None:
        if len(self._store) >= self._max_items:
            # Drop expired entries first, then the oldest-expiring ones.
            now = time.monotonic()
            for k in [k for k, (exp, _) in self._store.items() if exp < now]:
                self._store.pop(k, None)
            if len(self._store) >= self._max_items:
                for k, _ in sorted(self._store.items(), key=lambda kv: kv[1][0])[: self._max_items // 10]:
                    self._store.pop(k, None)
        self._store[key] = (time.monotonic() + ttl, value)

    async def delete(self, *keys: str) -> None:
        for k in keys:
            self._store.pop(k, None)

    async def keys(self, pattern: str):
        return [k for k in self._store if fnmatch.fnmatch(k, pattern)]

    async def flushall(self) -> None:
        self._store.clear()


_backend: Any = None
backend_name = "memory"


async def get_cache():
    """Return the active cache backend, connecting to Redis lazily."""
    global _backend, backend_name
    if _backend is not None:
        return _backend

    if settings.redis_url:
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
            )
            await client.ping()
            _backend, backend_name = client, "redis"
            logger.info("Cache: connected to Redis at %s", settings.redis_url)
            return _backend
        except Exception as exc:  # pragma: no cover - depends on environment
            logger.warning("Cache: Redis unavailable (%s) — using in-memory cache", exc)

    _backend, backend_name = _MemoryCache(), "memory"
    return _backend


async def cache_get(key: str) -> Optional[Any]:
    try:
        value = await (await get_cache()).get(key)
    except Exception as exc:
        logger.debug("cache_get failed for %s: %s", key, exc)
        return None
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    try:
        await (await get_cache()).setex(key, ttl, json.dumps(value, default=str))
    except Exception as exc:
        logger.debug("cache_set failed for %s: %s", key, exc)


async def cache_delete(key: str) -> None:
    try:
        await (await get_cache()).delete(key)
    except Exception:
        pass


async def cache_delete_pattern(pattern: str) -> None:
    try:
        cache = await get_cache()
        keys = await cache.keys(pattern)
        if keys:
            await cache.delete(*keys)
    except Exception:
        pass


async def cache_clear() -> None:
    """Clear everything (used by tests)."""
    try:
        cache = await get_cache()
        if isinstance(cache, _MemoryCache):
            await cache.flushall()
    except Exception:
        pass
