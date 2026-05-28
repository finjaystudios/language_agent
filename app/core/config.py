import os
from dataclasses import dataclass


def parse_bool(value: str, *, default: bool) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def parse_csv_env(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class AppSettings:
    auth_enabled: bool
    fastapi_api_key: str | None
    chainlit_auth_secret: str | None
    cors_allowed_origins: list[str]
    database_url: str
    database_pool_size: int
    database_echo: bool
    password_hash_scheme: str
    redis_url: str
    llm_backend: str
    llm_queue_name: str
    llm_queue_timeout_seconds: int
    llm_queue_wait_timeout_seconds: int
    llm_generation_timeout_seconds: int
    llm_result_ttl_seconds: int
    llm_max_queue_size: int
    llm_worker_concurrency: int
    llm_job_max_retries: int
    llm_stream_channel_prefix: str
    llm_status_poll_interval_seconds: float
    llm_stream_timeout_seconds: int
    llama_server_url: str
    llama_server_api_key: str
    llama_server_timeout_seconds: int
    llama_server_stream_timeout_seconds: int
    llama_server_model_name: str
    llama_server_health_path: str
    model_profiles_path: str

    @classmethod
    def from_env(cls) -> "AppSettings":
        queue_timeout = int(os.getenv("LLM_QUEUE_TIMEOUT_SECONDS", "180"))
        return cls(
            auth_enabled=parse_bool(os.getenv("AUTH_ENABLED", "true"), default=True),
            fastapi_api_key=os.getenv("FASTAPI_API_KEY"),
            chainlit_auth_secret=os.getenv("CHAINLIT_AUTH_SECRET"),
            cors_allowed_origins=parse_csv_env(os.getenv("CORS_ALLOWED_ORIGINS", "")),
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg://language_agent:change-me@127.0.0.1:5432/language_agent",
            ),
            database_pool_size=int(os.getenv("DATABASE_POOL_SIZE", "5")),
            database_echo=parse_bool(
                os.getenv("DATABASE_ECHO", "false"), default=False
            ),
            password_hash_scheme=os.getenv("PASSWORD_HASH_SCHEME", "argon2id"),
            redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
            llm_backend=os.getenv("LLM_BACKEND", "llama_server"),
            llm_queue_name=os.getenv("LLM_QUEUE_NAME", "llm"),
            llm_queue_timeout_seconds=queue_timeout,
            llm_queue_wait_timeout_seconds=int(
                os.getenv("LLM_QUEUE_WAIT_TIMEOUT_SECONDS", "300")
            ),
            llm_generation_timeout_seconds=int(
                os.getenv("LLM_GENERATION_TIMEOUT_SECONDS", str(queue_timeout))
            ),
            llm_result_ttl_seconds=int(os.getenv("LLM_RESULT_TTL_SECONDS", "300")),
            llm_max_queue_size=int(os.getenv("LLM_MAX_QUEUE_SIZE", "100")),
            llm_worker_concurrency=int(os.getenv("LLM_WORKER_CONCURRENCY", "1")),
            llm_job_max_retries=int(os.getenv("LLM_JOB_MAX_RETRIES", "2")),
            llm_stream_channel_prefix=os.getenv(
                "LLM_STREAM_CHANNEL_PREFIX", "llm-stream"
            ),
            llm_status_poll_interval_seconds=float(
                os.getenv(
                    "LLM_STATUS_POLL_INTERVAL_SECONDS",
                    os.getenv("LLM_QUEUE_POLL_INTERVAL_SECONDS", "0.05"),
                )
            ),
            llm_stream_timeout_seconds=int(
                os.getenv("LLM_STREAM_TIMEOUT_SECONDS", str(queue_timeout))
            ),
            llama_server_url=os.getenv("LLAMA_SERVER_URL", "http://localhost:8080"),
            llama_server_api_key=os.getenv("LLAMA_SERVER_API_KEY", ""),
            llama_server_timeout_seconds=int(
                os.getenv("LLAMA_SERVER_TIMEOUT_SECONDS", str(queue_timeout))
            ),
            llama_server_stream_timeout_seconds=int(
                os.getenv("LLAMA_SERVER_STREAM_TIMEOUT_SECONDS", str(queue_timeout))
            ),
            llama_server_model_name=os.getenv("LLAMA_SERVER_MODEL_NAME", ""),
            llama_server_health_path=os.getenv("LLAMA_SERVER_HEALTH_PATH", "/health"),
            model_profiles_path=os.getenv(
                "MODEL_PROFILES_PATH", "config/model_profiles.yml"
            ),
        )
