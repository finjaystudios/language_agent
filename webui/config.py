from __future__ import annotations

import os
from dataclasses import dataclass


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
    database_url: str | None
    chainlit_auth_secret: str | None
    chainlit_cookie_samesite: str
    session_cookie_secure: bool

    @classmethod
    def from_env(cls) -> WebUISettings:
        samesite = os.getenv("CHAINLIT_COOKIE_SAMESITE", "lax").strip().lower()
        if samesite not in {"lax", "strict", "none"}:
            samesite = "lax"

        return cls(
            auth_enabled=parse_bool(os.getenv("AUTH_ENABLED", "true"), default=True),
            database_url=os.getenv("WEBUI_DATABASE_URL") or os.getenv("DATABASE_URL"),
            chainlit_auth_secret=os.getenv("CHAINLIT_AUTH_SECRET"),
            chainlit_cookie_samesite=samesite,
            session_cookie_secure=samesite == "none",
        )

    def validate_for_auth(self) -> None:
        if not self.auth_enabled:
            return
        if not self.database_url:
            raise RuntimeError(
                "WEBUI_DATABASE_URL or DATABASE_URL must be configured when Chainlit password auth is enabled."
            )
        if not self.chainlit_auth_secret:
            raise RuntimeError(
                "CHAINLIT_AUTH_SECRET must be configured when Chainlit password auth is enabled."
            )
