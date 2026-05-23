import asyncio
import json

from app.api.dependencies import get_agent_service
from app.api.errors import (
    LLMServiceError,
    UnsupportedModeError,
    api_error_handler,
    http_exception_handler,
    unexpected_exception_handler,
    validation_exception_handler,
)
from app.services.agent_service import AgentService
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError


def response_body(response):
    return json.loads(response.body.decode())


def test_unsupported_mode_handler_returns_error_response():
    response = asyncio.run(api_error_handler(None, UnsupportedModeError("definition")))

    assert response.status_code == 400
    assert response_body(response) == {
        "error": "unsupported_mode",
        "message": "Mode 'definition' is not supported for this operation.",
        "details": None,
    }


def test_llm_service_handler_does_not_leak_stack_trace():
    response = asyncio.run(api_error_handler(None, LLMServiceError("Model failed.")))

    body = response_body(response)
    assert response.status_code == 500
    assert body["error"] == "llm_service_error"
    assert body["message"] == "Model failed."
    assert "Traceback" not in json.dumps(body)


def test_http_exception_handler_returns_error_response():
    response = asyncio.run(
        http_exception_handler(None, HTTPException(status_code=400, detail="Bad mode."))
    )

    assert response.status_code == 400
    assert response_body(response)["message"] == "Bad mode."


def test_validation_handler_maps_invalid_mode_to_bad_request():
    exc = RequestValidationError(
        [
            {
                "type": "enum",
                "loc": ("body", "mode"),
                "msg": "Input should be a supported mode",
                "input": "bad",
            }
        ]
    )

    response = asyncio.run(validation_exception_handler(None, exc))

    assert response.status_code == 400
    assert response_body(response)["error"] == "validation_error"


def test_validation_handler_preserves_schema_failures_as_unprocessable_entity():
    exc = RequestValidationError(
        [
            {
                "type": "string_too_short",
                "loc": ("body", "message"),
                "msg": "String should have at least 1 character",
                "input": "",
            }
        ]
    )

    response = asyncio.run(validation_exception_handler(None, exc))

    assert response.status_code == 422
    assert response_body(response)["error"] == "validation_error"


def test_unexpected_exception_handler_returns_internal_error():
    response = asyncio.run(unexpected_exception_handler(None, RuntimeError("boom")))

    body = response_body(response)
    assert response.status_code == 500
    assert body["error"] == "internal_error"
    assert "boom" not in json.dumps(body)


def test_agent_dependency_wraps_initialisation_failure(monkeypatch):
    get_agent_service.cache_clear()

    def fail_initialisation():
        raise RuntimeError("Redis not available")

    monkeypatch.setattr(AgentService, "from_queue", fail_initialisation)

    try:
        try:
            get_agent_service()
        except LLMServiceError as error:
            assert "Redis not available" in str(error)
        else:
            raise AssertionError("Expected LLMServiceError")
    finally:
        get_agent_service.cache_clear()
