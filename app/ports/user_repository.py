from __future__ import annotations

from typing import Protocol

from app.domain.user_profile import UserProfile


class UserRepository(Protocol):
    def get_by_username(self, username: str) -> UserProfile | None: ...

    def get_by_id(self, user_id: int) -> UserProfile | None: ...

    def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        display_name: str | None = None,
        role: str = "user",
        is_active: bool = True,
        is_admin: bool = False,
        preferred_language: str | None = None,
        ui_theme: str | None = None,
        profile_metadata: dict[str, object] | None = None,
    ) -> UserProfile: ...

    def update_last_login(self, user_id: int) -> UserProfile | None: ...

    def list_users(self) -> list[UserProfile]: ...
