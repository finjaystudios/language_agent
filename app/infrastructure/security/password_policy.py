from __future__ import annotations

MIN_PASSWORD_LENGTH = 12
_OBVIOUS_PASSWORDS = {
    "password",
    "password123",
    "12345678",
    "123456789",
    "1234567890",
    "qwerty",
    "qwerty123",
    "letmein",
    "admin",
    "changeme",
    "welcome",
}


def validate_password_strength(
    password: str,
    *,
    username: str | None = None,
    require_strong_password: bool = True,
    min_password_length: int = MIN_PASSWORD_LENGTH,
) -> None:
    if not require_strong_password:
        if not password or not password.strip():
            raise ValueError("Password must not be empty.")
        return

    normalized_password = password.strip()
    if not normalized_password:
        raise ValueError("Password must not be empty.")
    lowered_password = password.casefold()
    if lowered_password in _OBVIOUS_PASSWORDS:
        raise ValueError(
            "Password is too weak. Use a longer unique password from a password manager."
        )

    normalized_username = (username or "").strip().casefold()
    if normalized_username and lowered_password == normalized_username:
        raise ValueError("Password must not match the username.")
    if len(password) < min_password_length:
        raise ValueError(
            f"Password must be at least {min_password_length} characters long."
        )
