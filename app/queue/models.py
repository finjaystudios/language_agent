from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class LLMCallJob(BaseModel):
    job_id: str
    call_type: Literal["structured_json", "text_generation"]
    prompt: str | None = None
    messages: list[dict[str, str]]
    mode: str | None = None
    generation_parameters: dict[str, Any] = Field(default_factory=dict)
    response_schema: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: Literal["queued", "started", "completed", "failed"] = "queued"
    result: dict[str, Any] | str | None = None
    error: str | None = None
