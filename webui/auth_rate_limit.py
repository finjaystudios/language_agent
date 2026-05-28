from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from app.infrastructure.redis.connection import (
    close_async_redis_connection,
    get_async_redis_connection,
)
from redis.asyncio import Redis
from webui.config import WebUISettings


class AuthAttemptStore(Protocol):
    async def is_locked(self, username: str) -> bool: ...

    async def record_failure(self, username: str) -> int: ...

    async def clear(self, username: str) -> None: ...


@dataclass(frozen=True)
class AuthRateLimitSettings:
    max_failed_attempts: int
    lockout_seconds: int
    rate_limit_window_seconds: int


class RedisAuthAttemptStore:
    def __init__(
        self,
        connection: Redis,
        settings: AuthRateLimitSettings,
    ) -> None:
        self._connection = connection
        self._settings = settings

    async def is_locked(self, username: str) -> bool:
        return bool(await self._connection.exists(self._lockout_key(username)))

    async def record_failure(self, username: str) -> int:
        counter_key = self._counter_key(username)
        failures = int(await self._connection.incr(counter_key))
        if failures == 1:
            await self._connection.expire(
                counter_key,
                self._settings.rate_limit_window_seconds,
            )
        if failures >= self._settings.max_failed_attempts:
            await self._connection.set(
                self._lockout_key(username),
                "1",
                ex=self._settings.lockout_seconds,
            )
        return failures

    async def clear(self, username: str) -> None:
        await self._connection.delete(
            self._counter_key(username),
            self._lockout_key(username),
        )

    @staticmethod
    def _counter_key(username: str) -> str:
        return f"auth:failures:{username}"

    @staticmethod
    def _lockout_key(username: str) -> str:
        return f"auth:lockout:{username}"


class InMemoryAuthAttemptStore:
    def __init__(
        self,
        settings: AuthRateLimitSettings,
        *,
        now: Callable[[], float] | None = None,
    ) -> None:
        self._settings = settings
        self._now = now or time.monotonic
        self._failure_counts: dict[str, int] = {}
        self._failure_expires_at: dict[str, float] = {}
        self._locked_until: dict[str, float] = {}

    async def is_locked(self, username: str) -> bool:
        self._purge_expired(username)
        return self._locked_until.get(username, 0) > self._now()

    async def record_failure(self, username: str) -> int:
        self._purge_expired(username)
        now = self._now()
        if self._failure_expires_at.get(username, 0) <= now:
            self._failure_counts[username] = 0
            self._failure_expires_at[username] = (
                now + self._settings.rate_limit_window_seconds
            )

        failures = self._failure_counts.get(username, 0) + 1
        self._failure_counts[username] = failures
        if failures >= self._settings.max_failed_attempts:
            self._locked_until[username] = now + self._settings.lockout_seconds
        return failures

    async def clear(self, username: str) -> None:
        self._failure_counts.pop(username, None)
        self._failure_expires_at.pop(username, None)
        self._locked_until.pop(username, None)

    def _purge_expired(self, username: str) -> None:
        now = self._now()
        if self._failure_expires_at.get(username, 0) <= now:
            self._failure_counts.pop(username, None)
            self._failure_expires_at.pop(username, None)
        if self._locked_until.get(username, 0) <= now:
            self._locked_until.pop(username, None)


def build_auth_rate_limit_settings(
    settings: WebUISettings,
) -> AuthRateLimitSettings:
    return AuthRateLimitSettings(
        max_failed_attempts=max(1, settings.auth_max_failed_attempts),
        lockout_seconds=max(1, settings.auth_lockout_seconds),
        rate_limit_window_seconds=max(1, settings.auth_rate_limit_window_seconds),
    )


@lru_cache(maxsize=1)
def get_auth_attempt_store() -> AuthAttemptStore:
    settings = WebUISettings.from_env()
    rate_limit_settings = build_auth_rate_limit_settings(settings)
    if settings.redis_url:
        return RedisAuthAttemptStore(
            get_async_redis_connection(settings.redis_url),
            rate_limit_settings,
        )
    return InMemoryAuthAttemptStore(rate_limit_settings)


async def close_auth_attempt_store() -> None:
    store = get_auth_attempt_store()
    if isinstance(store, RedisAuthAttemptStore):
        await close_async_redis_connection(store._connection)
    get_auth_attempt_store.cache_clear()
