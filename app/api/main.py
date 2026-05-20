from fastapi import FastAPI

from app.api.routes import router as api_router

SERVICE_NAME = "local-language-agent"
SERVICE_VERSION = "0.1.0"


def create_app() -> FastAPI:
    fastapi_app = FastAPI(
        title="Local Language Agent API",
        version=SERVICE_VERSION,
        description="HTTP API foundation for the local language agent.",
    )

    @fastapi_app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @fastapi_app.get("/", tags=["system"])
    async def root() -> dict[str, str]:
        return {
            "service": SERVICE_NAME,
            "version": SERVICE_VERSION,
            "status": "ok",
        }

    fastapi_app.include_router(api_router)

    return fastapi_app


app = create_app()
