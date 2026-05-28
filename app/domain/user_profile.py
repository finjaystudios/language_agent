from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class UsernameAlreadyExistsError(ValueError):
    pass


@dataclass(frozen=True)
class UserProfile:
    id: int
    username: str
    display_name: str | None
    password_hash: str
    role: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None
    preferred_language: str | None = None
    ui_theme: str | None = None
    profile_metadata: dict[str, Any] = field(default_factory=dict)
