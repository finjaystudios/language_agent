from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.intent_result import IntentResult


class RequestMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: str | None = None
    client: str | None = None


class ResponseMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: str | None = None


class ChatCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1)
    mode: str | None = None
    metadata: RequestMetadata | None = None


class ChatResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    response: str
    intent: IntentResult | None = None
    data: dict[str, Any] | None = None
    metadata: ResponseMetadata | None = None
