from app.core.errors import APIError


class QueueSaturatedError(APIError):
    status_code = 429
    error = "queue_saturated"
    message = "The language model queue is full. Please try again shortly."

    def __init__(self, message: str | None = None, retry_after_seconds: int = 5):
        headers = {"Retry-After": str(max(1, retry_after_seconds))}
        super().__init__(message=message or self.message, headers=headers)


class QueueWaitTimeoutError(APIError):
    status_code = 504
    error = "queue_wait_timeout"
    message = "The request waited too long in the language model queue."


class GenerationTimeoutError(APIError):
    status_code = 504
    error = "generation_timeout"
    message = "The language model took too long to generate a response."


class StreamingTimeoutError(APIError):
    status_code = 504
    error = "stream_timeout"
    message = "The language model stream timed out before completion."
