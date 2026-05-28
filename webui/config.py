from __future__ import annotations

import os
from dataclasses import dataclass

from app.core.config import build_chainlit_database_url, build_database_url


def parse_bool(value: str, *, default: bool) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


@dataclass(frozen=True)
class WebUISettings:
    auth_enabled: bool
    auth_max_failed_attempts: int
    auth_lockout_seconds: int
    auth_rate_limit_window_seconds: int
    auth_require_strong_password: bool
    chainlit_history_enabled: bool
    database_scheme: str
    database_host: str
    database_port: int
    database_name: str
    database_user: str
    database_password: str
    database_url: str
    chainlit_database_url: str
    redis_url: str
    chainlit_auth_secret: str | None
    chainlit_cookie_samesite: str
    session_cookie_samesite: str
    session_cookie_secure: bool

    @classmethod
    def from_env(cls) -> WebUISettings:
        samesite = (
            os.getenv(
                "SESSION_COOKIE_SAMESITE",
                os.getenv("CHAINLIT_COOKIE_SAMESITE", "lax"),
            )
            .strip()
            .lower()
        )
        if samesite not in {"lax", "strict", "none"}:
            samesite = "lax"
        database_scheme = os.getenv("DATABASE_SCHEME", "postgresql+asyncpg")
        database_host = os.getenv("DATABASE_HOST", "127.0.0.1")
        database_port = int(os.getenv("DATABASE_PORT", "5432"))
        database_name = os.getenv("DATABASE_NAME", "language_agent")
        database_user = os.getenv("DATABASE_USER", "language_agent")
        database_password = os.getenv("DATABASE_PASSWORD", "change-me")

        return cls(
            auth_enabled=parse_bool(os.getenv("AUTH_ENABLED", "true"), default=True),
            auth_max_failed_attempts=int(os.getenv("AUTH_MAX_FAILED_ATTEMPTS", "5")),
            auth_lockout_seconds=int(os.getenv("AUTH_LOCKOUT_SECONDS", "300")),
            auth_rate_limit_window_seconds=int(
                os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "300")
            ),
            auth_require_strong_password=parse_bool(
                os.getenv("AUTH_REQUIRE_STRONG_PASSWORD", "true"),
                default=True,
            ),
            chainlit_history_enabled=parse_bool(
                os.getenv("CHAINLIT_HISTORY_ENABLED", "true"),
                default=True,
            ),
            database_scheme=database_scheme,
            database_host=database_host,
            database_port=database_port,
            database_name=database_name,
            database_user=database_user,
            database_password=database_password,
            database_url=build_database_url(
                scheme=database_scheme,
                host=database_host,
                port=database_port,
                name=database_name,
                username=database_user,
                password=database_password,
            ),
            chainlit_database_url=build_chainlit_database_url(
                scheme=database_scheme,
                host=database_host,
                port=database_port,
                name=database_name,
                username=database_user,
                password=database_password,
            ),
            redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
            chainlit_auth_secret=os.getenv("CHAINLIT_AUTH_SECRET"),
            chainlit_cookie_samesite=samesite,
            session_cookie_samesite=samesite,
            session_cookie_secure=parse_bool(
                os.getenv(
                    "SESSION_COOKIE_SECURE",
                    "true" if samesite == "none" else "false",
                ),
                default=samesite == "none",
            ),
        )

    def validate_for_auth(self) -> None:
        if not self.auth_enabled:
            return
        if not self.chainlit_auth_secret:
            raise RuntimeError(
                "CHAINLIT_AUTH_SECRET must be configured when Chainlit password auth is enabled."
            )
        if self.session_cookie_samesite == "none" and not self.session_cookie_secure:
            raise RuntimeError(
                "SESSION_COOKIE_SECURE must be true when SESSION_COOKIE_SAMESITE=none."
            )
