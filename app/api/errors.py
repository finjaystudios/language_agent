import logging

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.models import ErrorResponse

logger = logging.getLogger(__name__)


class APIError(Exception):
    status_code = 500
    error = "internal_error"
    message = "An internal service error occurred."
    headers: dict[str, str] | None = None

    def __init__(
        self,
        message: str | None = None,
        details: dict | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.message = message or self.message
        self.details = details
        self.headers = headers
        super().__init__(self.message)


class UnsupportedModeError(APIError):
    status_code = 400
    error = "unsupported_mode"

    def __init__(self, mode: str):
        self.mode = mode
        super().__init__(f"Mode '{mode}' is not supported for this operation.")


class LLMServiceError(APIError):
    status_code = 500
    error = "llm_service_error"
    message = "The language model service failed."


def error_response(
    status_code: int,
    error: str,
    message: str,
    details: dict | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(error=error, message=message, details=details)
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(),
        headers=headers,
    )


def _validation_status_code(exc: RequestValidationError) -> int:
    for validation_error in exc.errors():
        loc = validation_error.get("loc", ())
        error_type = validation_error.get("type", "")
        if loc and loc[-1] == "mode" and "enum" in error_type:
            return 400
    return 422


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    logger.warning(
        "api_error status_code=%d error=%s message=%s",
        exc.status_code,
        exc.error,
        exc.message,
    )
    return error_response(
        status_code=exc.status_code,
        error=exc.error,
        message=exc.message,
        details=exc.details,
        headers=exc.headers,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "HTTP request failed."
    logger.warning("http_error status_code=%d message=%s", exc.status_code, message)
    return error_response(
        status_code=exc.status_code,
        error="http_error",
        message=message,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    status_code = _validation_status_code(exc)
    logger.warning(
        "validation_error status_code=%d error_count=%d",
        status_code,
        len(exc.errors()),
    )
    return error_response(
        status_code=status_code,
        error="validation_error",
        message="Request validation failed.",
        details={"errors": exc.errors()},
    )


async def unexpected_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception("unexpected_internal_error")
    return error_response(
        status_code=500,
        error="internal_error",
        message="An unexpected internal error occurred.",
    )
