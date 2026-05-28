from __future__ import annotations

import os
from dataclasses import dataclass

from app.core.config import build_database_url


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
    database_scheme: str
    database_host: str
    database_port: int
    database_name: str
    database_user: str
    database_password: str
    database_url: str
    chainlit_auth_secret: str | None
    chainlit_cookie_samesite: str
    session_cookie_secure: bool

    @classmethod
    def from_env(cls) -> WebUISettings:
        samesite = os.getenv("CHAINLIT_COOKIE_SAMESITE", "lax").strip().lower()
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
            chainlit_auth_secret=os.getenv("CHAINLIT_AUTH_SECRET"),
            chainlit_cookie_samesite=samesite,
            session_cookie_secure=samesite == "none",
        )

    def validate_for_auth(self) -> None:
        if not self.auth_enabled:
            return
        if not self.chainlit_auth_secret:
            raise RuntimeError(
                "CHAINLIT_AUTH_SECRET must be configured when Chainlit password auth is enabled."
            )
