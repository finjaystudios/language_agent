import logging

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.config import CORSConfig
from app.api.errors import (
    APIError,
    api_error_handler,
    http_exception_handler,
    unexpected_exception_handler,
    validation_exception_handler,
)
from app.api.routes import router as api_router
from app.logging_config import configure_logging

SERVICE_NAME = "local-language-agent"
SERVICE_VERSION = "0.1.0"
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    configure_logging()
    logger.info(
        "fastapi_app_create_start service=%s version=%s",
        SERVICE_NAME,
        SERVICE_VERSION,
    )
    fastapi_app = FastAPI(
        title="Local Language Agent API",
        version=SERVICE_VERSION,
        description=(
            "HTTP API for the local language agent. The API exposes health "
            "metadata, full chat responses, and Server-Sent Events streaming "
            "without changing the existing CLI behavior."
        ),
    )

    cors_config = CORSConfig.from_env()
    if cors_config.allowed_origins:
        logger.info(
            "fastapi_cors_enabled allowed_origin_count=%d",
            len(cors_config.allowed_origins),
        )
        fastapi_app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_config.allowed_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "Accept", "X-API-Key"],
        )

    logger.debug("fastapi_exception_handlers_register_start")
    fastapi_app.add_exception_handler(APIError, api_error_handler)
    fastapi_app.add_exception_handler(HTTPException, http_exception_handler)
    fastapi_app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )
    fastapi_app.add_exception_handler(Exception, unexpected_exception_handler)

    @fastapi_app.get(
        "/health",
        tags=["system"],
        summary="Check service health",
        description="Returns a lightweight health status without initialising the LLM.",
    )
    async def health() -> dict[str, str]:
        logger.debug("health_check")
        return {"status": "ok"}

    @fastapi_app.get(
        "/",
        tags=["system"],
        summary="Get service metadata",
        description="Returns basic API metadata for clients and local tooling.",
    )
    async def root() -> dict[str, str]:
        logger.debug("service_metadata_requested")
        return {
            "service": SERVICE_NAME,
            "version": SERVICE_VERSION,
            "status": "ok",
        }

    fastapi_app.include_router(api_router)
    logger.info("fastapi_app_create_complete")

    return fastapi_app


app = create_app()
