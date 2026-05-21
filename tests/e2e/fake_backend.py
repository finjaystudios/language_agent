import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI(title="Fake Local Language Agent Backend")
REQUESTS: list[dict[str, Any]] = []


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(request: Request) -> dict[str, Any]:
    payload = await request.json()
    REQUESTS.append(
        {
            "endpoint": "/api/chat",
            "payload": payload,
            "api_key_present": bool(request.headers.get("X-API-Key")),
        }
    )
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


@app.post("/api/chat/stream")
async def chat_stream(request: Request) -> StreamingResponse:
    payload = await request.json()
    REQUESTS.append(
        {
            "endpoint": "/api/chat/stream",
            "payload": payload,
            "api_key_present": bool(request.headers.get("X-API-Key")),
        }
    )
    mode = payload.get("mode") or "translation"

    async def events() -> AsyncIterator[str]:
        for token in ["Bonjour", " from", " fake", " stream."]:
            yield f"data: {json.dumps({'mode': mode, 'token': token})}\n\n"
            await asyncio.sleep(0.05)
        yield f"data: {json.dumps({'mode': mode, 'done': True})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/test/requests")
async def test_requests() -> dict[str, Any]:
    return {"requests": REQUESTS}


@app.post("/test/reset")
async def test_reset() -> dict[str, str]:
    REQUESTS.clear()
    return {"status": "ok"}
