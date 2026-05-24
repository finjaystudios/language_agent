from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class LLMCallJob(BaseModel):
    job_id: str
    call_type: Literal[
        "structured_json", "text_generation", "streaming_text_generation"
    ]
    prompt: str | None = None
    messages: list[dict[str, str]]
    mode: str | None = None
    generation_parameters: dict[str, Any] = Field(default_factory=dict)
    response_schema: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: Literal[
        "queued",
        "processing",
        "streaming",
        "completed",
        "failed",
        "cancelled",
    ] = "queued"
    cancel_requested: bool = False
    queue_position: int | None = None
    elapsed_seconds: float | None = None
    stream_channel: str | None = None
    retry_count: int = 0
    last_error: str | None = None
    result: dict[str, Any] | str | None = None
    error: str | None = None


class QueueStatusSnapshot(BaseModel):
    redis_connected: bool
    queue_depth: int
    active_job_count: int
    failed_job_count: int
    worker_count: int
    worker_heartbeat_age_seconds: float | None = None
    average_wait_time_seconds: float | None = None
    estimated_wait_time_seconds: float | None = None
