from __future__ import annotations

import asyncio
import os
from threading import Lock
import time
from urllib.parse import urlparse

from middleware.rate_limiting_middleware import (
    MemoryRateLimitStore,
    RateLimitDecision,
)


class RedisClient:
    """Minimal async Redis client for the commands used by backend middleware."""

    def __init__(self, redis_url: str) -> None:
        parsed = urlparse(redis_url)
        if parsed.scheme not in {"redis", "rediss"}:
            raise ValueError("REDIS_URL must start with redis:// or rediss://")

        self.host = parsed.hostname or "localhost"
        self.port = parsed.port or 6379
        self.password = parsed.password
        self.db = int((parsed.path or "/0").lstrip("/") or "0")
        self.use_ssl = parsed.scheme == "rediss"
        self._reader = None
        self._writer = None
        self._lock = asyncio.Lock()

    async def ttl(self, key: str) -> int:
        result = await self.execute("TTL", key)
        return int(result)

    async def incr(self, key: str) -> int:
        result = await self.execute("INCR", key)
        return int(result)

    async def expire(self, key: str, seconds: int) -> bool:
        result = await self.execute("EXPIRE", key, seconds)
        return bool(result)

    async def set(self, key: str, value: str, *, ex: int | None = None) -> bool:
        command: list[str | int] = ["SET", key, value]
        if ex is not None:
            command.extend(["EX", ex])
        result = await self.execute(*command)
        return result == "OK"

    async def execute(self, *parts: str | int) -> object:
        async with self._lock:
            try:
                await self._ensure_connection()
                assert self._writer is not None
                assert self._reader is not None
                self._writer.write(self._encode_command(*parts))
                await self._writer.drain()
                return await self._read_response(self._reader)
            except Exception:
                await self._close_connection()
                raise

    async def _ensure_connection(self) -> None:
        if self._writer is not None and not self._writer.is_closing():
            return

        self._reader, self._writer = await asyncio.open_connection(
            self.host,
            self.port,
            ssl=self.use_ssl,
        )

        if self.password:
            auth_response = await self._execute_without_lock("AUTH", self.password)
            if auth_response != "OK":
                raise ConnectionError("Redis AUTH failed")

        if self.db:
            select_response = await self._execute_without_lock("SELECT", self.db)
            if select_response != "OK":
                raise ConnectionError("Redis SELECT failed")

    async def _execute_without_lock(self, *parts: str | int) -> object:
        assert self._writer is not None
        assert self._reader is not None
        self._writer.write(self._encode_command(*parts))
        await self._writer.drain()
        return await self._read_response(self._reader)

    async def _close_connection(self) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None

    def _encode_command(self, *parts: str | int) -> bytes:
        encoded = [f"*{len(parts)}\r\n".encode("utf-8")]
        for part in parts:
            value = str(part).encode("utf-8")
            encoded.append(f"${len(value)}\r\n".encode("utf-8"))
            encoded.append(value + b"\r\n")
        return b"".join(encoded)

    async def _read_response(self, reader) -> object:
        prefix = await reader.readexactly(1)
        if prefix == b"+":
            return (await reader.readline()).decode("utf-8").rstrip("\r\n")
        if prefix == b":":
            return int((await reader.readline()).decode("utf-8").rstrip("\r\n"))
        if prefix == b"$":
            length = int((await reader.readline()).decode("utf-8").rstrip("\r\n"))
            if length == -1:
                return None
            data = await reader.readexactly(length)
            await reader.readexactly(2)
            return data.decode("utf-8")
        if prefix == b"-":
            message = (await reader.readline()).decode("utf-8").rstrip("\r\n")
            raise RuntimeError(f"Redis error: {message}")
        if prefix == b"*":
            count = int((await reader.readline()).decode("utf-8").rstrip("\r\n"))
            return [await self._read_response(reader) for _ in range(count)]
        raise RuntimeError("Unsupported Redis response type")


class RedisRateLimitStore:
    """Shared Redis-backed rate limit store for multi-instance deployments."""

    def __init__(self, redis_url: str, *, namespace: str = "fraudsentinel") -> None:
        self.namespace = namespace
        self.client = RedisClient(redis_url)

    async def register_request(
        self,
        *,
        key: str,
        calls: int,
        window_seconds: int,
        block_duration_seconds: int,
    ) -> RateLimitDecision:
        now_epoch = time.time()
        blocked_key = f"{self.namespace}:blocked:{key}"
        blocked_ttl = await self.client.ttl(blocked_key)
        if blocked_ttl and blocked_ttl > 0:
            return RateLimitDecision(
                allowed=False,
                remaining=0,
                reset_timestamp=int(now_epoch + blocked_ttl),
                retry_after=int(blocked_ttl),
            )

        window_bucket = int(now_epoch // window_seconds)
        counter_key = f"{self.namespace}:window:{window_bucket}:{key}"
        request_count = await self.client.incr(counter_key)
        if request_count == 1:
            await self.client.expire(counter_key, window_seconds)

        window_reset = int((window_bucket + 1) * window_seconds)
        if request_count > calls:
            await self.client.set(blocked_key, "1", ex=block_duration_seconds)
            return RateLimitDecision(
                allowed=False,
                remaining=0,
                reset_timestamp=int(now_epoch + block_duration_seconds),
                retry_after=block_duration_seconds,
            )

        return RateLimitDecision(
            allowed=True,
            remaining=max(0, calls - request_count),
            reset_timestamp=window_reset,
        )


_STORE_LOCK = Lock()
_STORE_CACHE: dict[str, object] = {}


def get_redis_url() -> str | None:
    return os.getenv("REDIS_URL")


def build_rate_limit_store(namespace: str):
    """Return a shared rate-limit store backed by Redis when configured."""
    redis_url = get_redis_url()
    cache_key = f"{namespace}:{redis_url or 'memory'}"

    with _STORE_LOCK:
        if cache_key in _STORE_CACHE:
            return _STORE_CACHE[cache_key]

        if redis_url:
            store = RedisRateLimitStore(redis_url, namespace=namespace)
        else:
            store = MemoryRateLimitStore()

        _STORE_CACHE[cache_key] = store
        return store


__all__ = [
    "RedisClient",
    "RedisRateLimitStore",
    "get_redis_url",
    "build_rate_limit_store",
]
