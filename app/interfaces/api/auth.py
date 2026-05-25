import os
import secrets
from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import APIKeyHeader

from app.core.config import parse_bool
from app.core.errors import APIError

API_KEY_HEADER_NAME = "X-API-Key"

api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


class AuthenticationError(APIError):
    status_code = 401
    error = "authentication_failed"
    message = "A valid API key is required."


class AuthConfigurationError(APIError):
    status_code = 500
    error = "auth_configuration_error"
    message = "API authentication is not configured correctly."


@dataclass(frozen=True)
class AuthConfig:
    enabled: bool
    api_key: str | None

    @classmethod
    def from_env(cls) -> "AuthConfig":
        return cls(
            enabled=parse_bool(os.getenv("AUTH_ENABLED", "true"), default=True),
            api_key=os.getenv("FASTAPI_API_KEY"),
        )


def validate_api_key(provided_key: str | None, config: AuthConfig) -> None:
    if not config.enabled:
        return

    expected_key = config.api_key or ""
    if not expected_key:
        raise AuthConfigurationError()

    if not provided_key:
        raise AuthenticationError()

    if not secrets.compare_digest(provided_key, expected_key):
        raise AuthenticationError()


async def require_api_key(
    provided_key: str | None = Depends(api_key_header),
) -> None:
    validate_api_key(provided_key, AuthConfig.from_env())
