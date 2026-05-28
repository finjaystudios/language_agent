import asyncio
import json
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="Fake Local Language Agent Backend")
REQUESTS: list[dict[str, Any]] = []
EXPECTED_API_KEY = os.getenv("FAKE_BACKEND_API_KEY", "e2e-test-secret")
DEFAULT_USERNAME = os.getenv("FAKE_BACKEND_USERNAME", "e2e-user")
DEFAULT_PASSWORD = os.getenv("FAKE_BACKEND_PASSWORD", "correct horse battery staple")
DEFAULT_DISPLAY_NAME = os.getenv("FAKE_BACKEND_DISPLAY_NAME", "E2E User")
SIGNUP_ENABLED = os.getenv("FAKE_BACKEND_SIGNUP_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
MIN_PASSWORD_LENGTH = int(os.getenv("FAKE_BACKEND_MIN_PASSWORD_LENGTH", "12"))
USERS: dict[str, dict[str, Any]] = {}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def seed_default_user() -> None:
    USERS.clear()
    USERS[DEFAULT_USERNAME] = {
        "user_id": 1,
        "username": DEFAULT_USERNAME,
        "display_name": DEFAULT_DISPLAY_NAME,
        "password": DEFAULT_PASSWORD,
        "role": "user",
        "is_admin": False,
        "preferred_language": "en",
        "ui_theme": "light",
        "is_active": True,
        "created_at": utc_now(),
        "last_login_at": None,
    }


seed_default_user()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(request: Request) -> dict[str, Any]:
    payload = await request.json()
    api_key_present = bool(request.headers.get("X-API-Key"))
    REQUESTS.append(
        {
            "endpoint": "/api/chat",
            "payload": payload,
            "api_key_present": api_key_present,
            "api_key_valid": request.headers.get("X-API-Key") == EXPECTED_API_KEY,
        }
    )
    if request.headers.get("X-API-Key") != EXPECTED_API_KEY:
        return authentication_error()

    mode = payload.get("mode") or "general"

    if mode == "definition":
        return {
            "mode": "definition",
            "response": "E2E definition response from fake backend.",
            "data": {
                "mode": "definition",
                "response": "E2E definition response from fake backend.",
                "term": "recursion",
                "language": "English",
                "part_of_speech": "noun",
                "pronunciation": "",
                "meaning": "E2E definition response from fake backend.",
                "examples": ["A function can call itself in a recursive solution."],
                "synonyms": ["self-reference"],
                "antonyms": ["iteration"],
                "etymology": "",
            },
            "metadata": {},
        }

    return {
        "mode": mode,
        "response": f"E2E full response from fake backend for {mode}.",
        "metadata": {},
    }


@app.post("/api/internal/auth/login")
async def internal_auth_login(request: Request) -> JSONResponse:
    payload = await request.json()
    REQUESTS.append(
        {
            "endpoint": "/api/internal/auth/login",
            "payload": payload,
            "api_key_valid": request.headers.get("X-API-Key") == EXPECTED_API_KEY,
        }
    )
    if request.headers.get("X-API-Key") != EXPECTED_API_KEY:
        return authentication_error()

    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    user = USERS.get(username)
    if (
        user is None
        or not user.get("is_active", True)
        or user.get("password") != password
    ):
        return JSONResponse(
            status_code=403,
            content={
                "error": "invalid_credentials",
                "message": "Invalid username or password.",
                "details": None,
            },
        )

    user["last_login_at"] = utc_now()
    return JSONResponse(
        status_code=200,
        content={
            "user_id": user["user_id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "role": user["role"],
            "is_admin": user["is_admin"],
            "preferred_language": user["preferred_language"],
            "ui_theme": user["ui_theme"],
        },
    )


@app.post("/api/auth/signup")
async def auth_signup(request: Request) -> JSONResponse:
    payload = await request.json()
    REQUESTS.append(
        {
            "endpoint": "/api/auth/signup",
            "payload": {
                key: value
                for key, value in payload.items()
                if key not in {"password", "confirm_password"}
            },
            "api_key_valid": request.headers.get("X-API-Key") == EXPECTED_API_KEY,
        }
    )
    if request.headers.get("X-API-Key") != EXPECTED_API_KEY:
        return authentication_error()
    if not SIGNUP_ENABLED:
        return JSONResponse(
            status_code=404,
            content={
                "error": "signup_disabled",
                "message": "Account sign-up is not available right now.",
                "details": None,
            },
        )

    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    confirm_password = str(payload.get("confirm_password", ""))
    display_name = str(payload.get("display_name", "")).strip() or None

    if not username:
        return invalid_signup("Username is required.")
    if password != confirm_password:
        return invalid_signup("Password confirmation does not match.")
    if len(password) < MIN_PASSWORD_LENGTH:
        return invalid_signup(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )
    if password.casefold() in {"password", "password123", "qwerty", "letmein"}:
        return invalid_signup(
            "Password is too weak. Use a longer unique password from a password manager."
        )
    if username in USERS:
        return JSONResponse(
            status_code=409,
            content={
                "error": "username_unavailable",
                "message": "That username is unavailable.",
                "details": None,
            },
        )

    user_id = max((user["user_id"] for user in USERS.values()), default=0) + 1
    created_at = utc_now()
    USERS[username] = {
        "user_id": user_id,
        "username": username,
        "display_name": display_name,
        "password": password,
        "role": "user",
        "is_admin": False,
        "preferred_language": None,
        "ui_theme": None,
        "is_active": True,
        "created_at": created_at,
        "last_login_at": None,
    }
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Account created. Please sign in.",
            "user_id": user_id,
            "username": username,
            "created_at": created_at,
        },
    )


@app.post("/api/chat/stream")
async def chat_stream(request: Request) -> StreamingResponse:
    payload = await request.json()
    api_key_present = bool(request.headers.get("X-API-Key"))
    REQUESTS.append(
        {
            "endpoint": "/api/chat/stream",
            "payload": payload,
            "api_key_present": api_key_present,
            "api_key_valid": request.headers.get("X-API-Key") == EXPECTED_API_KEY,
        }
    )
    if request.headers.get("X-API-Key") != EXPECTED_API_KEY:
        return authentication_error()

    mode = payload.get("mode") or "translation"

    async def events() -> AsyncIterator[str]:
        tokens = (
            ["Definition", " from", " fake", " stream."]
            if mode == "definition"
            else ["Bonjour", " from", " fake", " stream."]
        )
        for token in tokens:
            yield f"data: {json.dumps({'mode': mode, 'token': token})}\n\n"
            await asyncio.sleep(0.05)
        yield f"data: {json.dumps({'mode': mode, 'done': True})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


def authentication_error():
    return JSONResponse(
        status_code=401,
        content={
            "error": "authentication_failed",
            "message": "A valid API key is required.",
            "details": None,
        },
    )


def invalid_signup(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error": "invalid_signup",
            "message": message,
            "details": None,
        },
    )


@app.get("/test/requests")
async def test_requests() -> dict[str, Any]:
    return {"requests": REQUESTS}


@app.post("/test/reset")
async def test_reset() -> dict[str, str]:
    REQUESTS.clear()
    seed_default_user()
    return {"status": "ok"}
