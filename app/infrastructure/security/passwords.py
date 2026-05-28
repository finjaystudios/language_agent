from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from bcrypt import checkpw, gensalt, hashpw

from app.core.config import AppSettings

_argon2_hasher = PasswordHasher()


def hash_password(password: str, *, scheme: str | None = None) -> str:
    selected_scheme = _normalize_scheme(scheme)
    if selected_scheme == "argon2id":
        return _argon2_hasher.hash(password)
    return hashpw(password.encode("utf-8"), gensalt()).decode("utf-8")


def verify_password(
    password: str,
    password_hash: str,
    *,
    scheme: str | None = None,
) -> bool:
    selected_scheme = _normalize_scheme(scheme, password_hash=password_hash)
    if selected_scheme == "argon2id":
        try:
            return _argon2_hasher.verify(password_hash, password)
        except (InvalidHashError, VerifyMismatchError):
            return False
    try:
        return checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _normalize_scheme(
    scheme: str | None,
    *,
    password_hash: str | None = None,
) -> str:
    if scheme is None and password_hash:
        if password_hash.startswith("$argon2id$"):
            return "argon2id"
        if password_hash.startswith("$2"):
            return "bcrypt"

    configured = (scheme or AppSettings.from_env().password_hash_scheme).strip().lower()
    if configured not in {"argon2id", "bcrypt"}:
        raise ValueError(f"Unsupported password hash scheme: {configured}")
    return configured
