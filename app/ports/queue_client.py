from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from app.domain.jobs import QueueStatusSnapshot


class QueueClient(Protocol):
    def enqueue(
        self,
        payload: dict[str, Any],
        *,
        job_id: str,
        result_ttl: int,
        job_timeout: int,
        retry_max: int,
    ) -> Any: ...

    def get_job(self, job_id: str) -> Any: ...

    def get_job_status(self, job_id: str) -> str: ...

    def get_job_position(self, job_id: str) -> int | None: ...

    def remove(self, job_id: str) -> None: ...

    def get_queue_depth(self) -> int: ...

    def get_active_job_count(self) -> int: ...

    def get_failed_job_count(self) -> int: ...

    def get_worker_heartbeats(self) -> list[datetime]: ...

    def ping(self) -> bool: ...

    def build_queue_status(
        self,
        *,
        redis_connected: bool,
        average_wait_time_seconds: float | None,
        estimated_wait_time_seconds: float | None,
    ) -> QueueStatusSnapshot: ...
