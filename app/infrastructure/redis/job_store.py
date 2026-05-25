from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from app.core.config import AppSettings
from app.domain.jobs import LLMCallJob
from app.infrastructure.redis.connection import (
    close_async_redis_connection,
    get_async_redis_connection,
    get_redis_connection,
)
from app.ports.job_store import JobStore
from app.ports.queue_client import QueueClient

QUEUE_METRICS_KEY = "llm:queue:metrics"


class RedisJobStore(JobStore):
    def __init__(
        self,
        settings: AppSettings,
        queue_client: QueueClient,
        connection: Redis | None = None,
        async_connection_factory: callable | None = None,
    ) -> None:
        self.settings = settings
        self.queue_client = queue_client
        self.connection = connection or get_redis_connection(settings.redis_url)
        self.async_connection_factory = async_connection_factory or (
            lambda: get_async_redis_connection(settings.redis_url)
        )

    def get_stream_channel(self, job_id: str) -> str:
        return f"{self.settings.llm_stream_channel_prefix}:{job_id}"

    def _compute_elapsed_seconds(self, llm_call: LLMCallJob) -> float | None:
        start_time = llm_call.started_at or llm_call.created_at
        if start_time is None:
            return None
        end_time = llm_call.completed_at or datetime.now(UTC)
        return max(0.0, (end_time - start_time).total_seconds())

    def serialize_llm_call(self, llm_call: LLMCallJob) -> dict[str, Any]:
        llm_call.elapsed_seconds = self._compute_elapsed_seconds(llm_call)
        return llm_call.model_dump(mode="json")

    def save_job_payload(self, job: Any, llm_call: LLMCallJob) -> None:
        job.meta["llm_call"] = self.serialize_llm_call(llm_call)
        job.save_meta()

    def record_wait_time(self, wait_seconds: float) -> None:
        self.connection.hincrbyfloat(
            QUEUE_METRICS_KEY, "total_wait_seconds", wait_seconds
        )
        self.connection.hincrby(QUEUE_METRICS_KEY, "started_jobs", 1)

    def record_completion_metrics(self, llm_call: LLMCallJob) -> None:
        if llm_call.started_at is not None and llm_call.completed_at is not None:
            generation_seconds = max(
                0.0,
                (llm_call.completed_at - llm_call.started_at).total_seconds(),
            )
            self.connection.hincrbyfloat(
                QUEUE_METRICS_KEY,
                "total_generation_seconds",
                generation_seconds,
            )
        self.connection.hincrby(QUEUE_METRICS_KEY, "completed_jobs", 1)

    def read_average_wait_time_seconds(self) -> float | None:
        metrics = self.connection.hgetall(QUEUE_METRICS_KEY)
        started_jobs_raw = metrics.get(b"started_jobs") or metrics.get("started_jobs")
        total_wait_raw = metrics.get(b"total_wait_seconds") or metrics.get(
            "total_wait_seconds"
        )
        if not started_jobs_raw or not total_wait_raw:
            return None
        started_jobs = int(
            started_jobs_raw.decode()
            if isinstance(started_jobs_raw, bytes)
            else started_jobs_raw
        )
        if started_jobs <= 0:
            return None
        total_wait = float(
            total_wait_raw.decode()
            if isinstance(total_wait_raw, bytes)
            else total_wait_raw
        )
        return total_wait / started_jobs

    def read_average_generation_time_seconds(self) -> float | None:
        metrics = self.connection.hgetall(QUEUE_METRICS_KEY)
        completed_jobs_raw = metrics.get(b"completed_jobs") or metrics.get(
            "completed_jobs"
        )
        total_generation_raw = metrics.get(b"total_generation_seconds") or metrics.get(
            "total_generation_seconds"
        )
        if not completed_jobs_raw or not total_generation_raw:
            return None
        completed_jobs = int(
            completed_jobs_raw.decode()
            if isinstance(completed_jobs_raw, bytes)
            else completed_jobs_raw
        )
        if completed_jobs <= 0:
            return None
        total_generation = float(
            total_generation_raw.decode()
            if isinstance(total_generation_raw, bytes)
            else total_generation_raw
        )
        return total_generation / completed_jobs

    def append_stream_event(self, job_id: str, payload: dict[str, Any]) -> str:
        stream_name = self.get_stream_channel(job_id)
        event_id = self.connection.xadd(stream_name, {"event": json.dumps(payload)})
        self.connection.expire(stream_name, self.settings.llm_result_ttl_seconds)
        if isinstance(event_id, bytes):
            return event_id.decode()
        return str(event_id)

    def get_job_result(self, job_id: str) -> LLMCallJob:
        job = self.queue_client.get_job(job_id)
        payload = getattr(job, "result", None) or job.meta.get("llm_call")
        if payload is None:
            raise RuntimeError(f"LLM job '{job_id}' has no result payload.")
        llm_call = LLMCallJob.model_validate(payload)
        if llm_call.stream_channel is None:
            llm_call.stream_channel = self.get_stream_channel(job_id)
        if llm_call.status == "queued":
            llm_call.queue_position = self.queue_client.get_job_position(job_id)
        llm_call.elapsed_seconds = self._compute_elapsed_seconds(llm_call)
        return llm_call

    def is_cancel_requested(self, job_id: str) -> bool:
        return bool(self.get_job_result(job_id).cancel_requested)

    async def stream_llm_events(
        self,
        job_id: str,
        timeout_seconds: int,
    ) -> AsyncIterator[dict[str, Any]]:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        last_id = "0-0"
        redis_connection: AsyncRedis = self.async_connection_factory()
        try:
            while True:
                stream_name = self.get_stream_channel(job_id)
                records = await redis_connection.xread(
                    {stream_name: last_id},
                    count=20,
                    block=1000,
                )
                events: list[dict[str, Any]] = []
                for _stream_name, stream_records in records:
                    for event_id, data in stream_records:
                        raw_event = (
                            data.get(b"event")
                            if b"event" in data
                            else data.get("event")
                        )
                        if isinstance(raw_event, bytes):
                            raw_event = raw_event.decode()
                        event = json.loads(raw_event)
                        event["_stream_id"] = (
                            event_id.decode()
                            if isinstance(event_id, bytes)
                            else str(event_id)
                        )
                        events.append(event)

                if not events:
                    if asyncio.get_running_loop().time() >= deadline:
                        raise TimeoutError(
                            f"Timed out waiting for LLM stream '{job_id}'."
                        )
                    continue

                deadline = asyncio.get_running_loop().time() + timeout_seconds
                for event in events:
                    last_id = event.pop("_stream_id")
                    yield event
                    if event.get("done") is True or event.get("status") in {
                        "completed",
                        "failed",
                        "cancelled",
                    }:
                        return
        finally:
            await close_async_redis_connection(redis_connection)
