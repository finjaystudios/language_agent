from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.data_models.intent_result import IntentResult
from app.data_models.mode_responses import (
    DefinitionResponse,
    LearningResponse,
    TranslationResponse,
)


class ApiMode(StrEnum):
    translation = "translation"
    definition = "definition"
    learning = "learning"
    general = "general"


class RequestMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: str | None = Field(
        default=None,
        description="Client-provided session identifier for future stateful requests.",
    )
    client: str | None = Field(
        default=None,
        description="Optional client name or UI surface making the request.",
    )


class ResponseMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: str | None = Field(
        default=None,
        description="Session identifier associated with the response, if available.",
    )


class ChatRequest(BaseModel):
    """Request body for a single non-streaming chat turn."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        min_length=1,
        description="User input to process through the language agent.",
    )
    mode: ApiMode | None = Field(
        default=None,
        description="Optional mode override. Omit to let intent routing choose.",
    )
    metadata: RequestMetadata | None = Field(
        default=None,
        description="Optional request metadata for future UI/session handling.",
    )


class StreamChatRequest(ChatRequest):
    """Request body for a streaming chat turn."""

    stream: Literal[True] = Field(
        default=True,
        description="Marks the request as intended for a streaming response.",
    )


class IntentClassificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        min_length=1,
        description="User input to classify without generating a mode response.",
    )
    active_mode: ApiMode = Field(
        default=ApiMode.general,
        description="Current active mode used as context for intent routing.",
    )
    conversation_history: str = Field(
        default="",
        description="Formatted recent conversation history used by the router.",
    )
    metadata: RequestMetadata | None = Field(
        default=None,
        description="Optional request metadata for future UI/session handling.",
    )


class IntentClassificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: IntentResult = Field(description="Structured intent routing result.")
    metadata: ResponseMetadata | None = Field(
        default=None,
        description="Optional response metadata for future UI/session handling.",
    )


ModeResponsePayload = TranslationResponse | DefinitionResponse | LearningResponse


class ChatResponse(BaseModel):
    """Complete response returned by the non-streaming chat endpoint."""

    model_config = ConfigDict(extra="forbid")

    mode: ApiMode = Field(description="Mode used to produce the response.")
    response: str = Field(description="User-facing assistant response text.")
    intent: IntentResult | None = Field(
        default=None,
        description="Intent routing result, when available.",
    )
    data: ModeResponsePayload | None = Field(
        default=None,
        description="Mode-specific structured response payload for full responses.",
    )
    metadata: ResponseMetadata | None = Field(
        default=None,
        description="Optional response metadata for future UI/session handling.",
    )


class ErrorResponse(BaseModel):
    """Stable error response returned by API exception handlers."""

    model_config = ConfigDict(extra="forbid")

    error: str = Field(description="Machine-readable error code.")
    message: str = Field(description="Human-readable error message.")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Optional structured details about the error.",
    )
