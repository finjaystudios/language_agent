from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from redis import Redis
from rq import Queue, Retry
from rq.job import Job
from rq.registry import FailedJobRegistry, StartedJobRegistry
from rq.worker import Worker

from app.core.config import AppSettings
from app.domain.jobs import QueueStatusSnapshot
from app.infrastructure.redis.connection import get_redis_connection
from app.infrastructure.redis.errors import QueueSaturatedError
from app.ports.queue_client import QueueClient


class RQQueueClient(QueueClient):
    def __init__(
        self,
        settings: AppSettings,
        connection: Redis | None = None,
    ) -> None:
        self.settings = settings
        self.connection = connection or get_redis_connection(settings.redis_url)

    def _queue(self) -> Queue:
        return Queue(
            name=self.settings.llm_queue_name,
            connection=self.connection,
            default_timeout=self.settings.llm_queue_timeout_seconds,
        )

    def _started_registry(self) -> StartedJobRegistry:
        return StartedJobRegistry(
            name=self.settings.llm_queue_name,
            connection=self.connection,
        )

    def _failed_registry(self) -> FailedJobRegistry:
        return FailedJobRegistry(
            name=self.settings.llm_queue_name,
            connection=self.connection,
        )

    def enqueue(
        self,
        payload: dict[str, Any],
        *,
        job_id: str,
        result_ttl: int,
        job_timeout: int,
        retry_max: int,
    ) -> Job:
        queue = self._queue()
        retry = Retry(max=retry_max, interval=0) if retry_max > 0 else None
        return queue.enqueue(
            "app.worker.jobs.process_llm_call",
            payload,
            job_id=job_id,
            result_ttl=result_ttl,
            job_timeout=job_timeout,
            retry=retry,
        )

    def get_job(self, job_id: str) -> Job:
        return Job.fetch(job_id, connection=self.connection)

    def get_job_status(self, job_id: str) -> str:
        return str(self.get_job(job_id).get_status(refresh=True))

    def get_job_position(self, job_id: str) -> int | None:
        try:
            return self._queue().get_job_position(job_id)
        except Exception:
            return None

    def remove(self, job_id: str) -> None:
        self._queue().remove(job_id)

    def get_queue_depth(self) -> int:
        return self._queue().count

    def get_active_job_count(self) -> int:
        return self._started_registry().count

    def get_failed_job_count(self) -> int:
        return self._failed_registry().count

    def get_worker_heartbeats(self) -> list[datetime]:
        workers = Worker.all(connection=self.connection, queue=self._queue())
        return [
            heartbeat
            for worker in workers
            if (heartbeat := getattr(worker, "last_heartbeat", None)) is not None
        ]

    def ping(self) -> bool:
        try:
            return bool(self.connection.ping())
        except Exception:
            return False

    def build_queue_status(
        self,
        *,
        redis_connected: bool,
        average_wait_time_seconds: float | None,
        estimated_wait_time_seconds: float | None,
    ) -> QueueStatusSnapshot:
        if not redis_connected:
            return QueueStatusSnapshot(
                redis_connected=False,
                queue_depth=0,
                active_job_count=0,
                failed_job_count=0,
                worker_count=0,
            )

        workers = Worker.all(connection=self.connection, queue=self._queue())
        heartbeats = [
            heartbeat
            for worker in workers
            if (heartbeat := getattr(worker, "last_heartbeat", None)) is not None
        ]
        worker_heartbeat_age_seconds: float | None = None
        if heartbeats:
            now = datetime.now(UTC)
            worker_heartbeat_age_seconds = min(
                max(0.0, (now - heartbeat).total_seconds()) for heartbeat in heartbeats
            )

        return QueueStatusSnapshot(
            redis_connected=True,
            queue_depth=self.get_queue_depth(),
            active_job_count=self.get_active_job_count(),
            failed_job_count=self.get_failed_job_count(),
            worker_count=len(workers),
            worker_heartbeat_age_seconds=worker_heartbeat_age_seconds,
            average_wait_time_seconds=average_wait_time_seconds,
            estimated_wait_time_seconds=estimated_wait_time_seconds,
        )

    def check_backpressure(self, estimated_wait_seconds: float) -> None:
        queue_depth = self.get_queue_depth()
        if queue_depth >= self.settings.llm_max_queue_size:
            raise QueueSaturatedError(
                retry_after_seconds=int(max(1, estimated_wait_seconds))
            )
        if estimated_wait_seconds > self.settings.llm_queue_wait_timeout_seconds:
            raise QueueSaturatedError(
                message=(
                    "The language model queue is too busy to accept this request right now."
                ),
                retry_after_seconds=int(max(1, estimated_wait_seconds)),
            )
