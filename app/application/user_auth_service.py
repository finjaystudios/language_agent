from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.user_profile import UsernameAlreadyExistsError, UserProfile
from app.infrastructure.security.password_policy import validate_password_strength
from app.infrastructure.security.passwords import hash_password, verify_password
from app.ports.user_repository import UserRepository

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 64
DISPLAY_NAME_MAX_LENGTH = 80
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._@-]{1,62}[A-Za-z0-9])?$")


@dataclass(frozen=True)
class UserSignupCommand:
    username: str
    password: str
    confirm_password: str | None = None
    display_name: str | None = None
    preferred_language: str | None = None


def normalize_username(username: str) -> str:
    return username.strip()


def validate_username(username: str) -> None:
    if not username:
        raise ValueError("Username is required.")
    if len(username) < USERNAME_MIN_LENGTH or len(username) > USERNAME_MAX_LENGTH:
        raise ValueError(
            f"Username must be between {USERNAME_MIN_LENGTH} and {USERNAME_MAX_LENGTH} characters long."
        )
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError(
            "Username may use letters, numbers, dots, underscores, hyphens, or @."
        )


def validate_display_name(display_name: str | None) -> str | None:
    if display_name is None:
        return None
    normalized_display_name = display_name.strip()
    if not normalized_display_name:
        return None
    if len(normalized_display_name) > DISPLAY_NAME_MAX_LENGTH:
        raise ValueError(
            f"Display name must be {DISPLAY_NAME_MAX_LENGTH} characters or fewer."
        )
    return normalized_display_name


async def authenticate_password_user(
    username: str,
    password: str,
    user_repository: UserRepository,
) -> UserProfile | None:
    normalized_username = normalize_username(username)
    user = await user_repository.get_by_username(normalized_username)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return await user_repository.update_last_login(user.id) or user


async def signup_user(
    command: UserSignupCommand,
    user_repository: UserRepository,
    *,
    require_strong_password: bool,
    min_password_length: int,
    default_role: str,
    require_admin_approval: bool,
) -> UserProfile:
    normalized_username = normalize_username(command.username)
    validate_username(normalized_username)
    normalized_display_name = validate_display_name(command.display_name)

    if (
        command.confirm_password is not None
        and command.password != command.confirm_password
    ):
        raise ValueError("Password confirmation does not match.")

    validate_password_strength(
        command.password,
        username=normalized_username,
        require_strong_password=require_strong_password,
        min_password_length=min_password_length,
    )

    return await user_repository.create_user(
        username=normalized_username,
        password_hash=hash_password(command.password),
        display_name=normalized_display_name,
        role=default_role,
        is_active=not require_admin_approval,
        preferred_language=(command.preferred_language or "").strip() or None,
    )


__all__ = [
    "DISPLAY_NAME_MAX_LENGTH",
    "USERNAME_MAX_LENGTH",
    "USERNAME_MIN_LENGTH",
    "UserSignupCommand",
    "UsernameAlreadyExistsError",
    "authenticate_password_user",
    "normalize_username",
    "signup_user",
    "validate_display_name",
    "validate_username",
]
