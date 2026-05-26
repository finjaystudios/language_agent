import asyncio

from app.interfaces.api.main import create_app


def route_response(app, path: str) -> dict[str, str]:
    route = next(route for route in app.routes if getattr(route, "path", None) == path)
    return asyncio.run(route.endpoint())


def test_health_endpoint_returns_ok():
    app = create_app()

    assert route_response(app, "/health") == {"status": "ok"}


def test_root_endpoint_returns_service_metadata():
    app = create_app()

    assert route_response(app, "/") == {
        "service": "local-language-agent",
        "version": "0.1.0",
        "status": "ok",
    }
