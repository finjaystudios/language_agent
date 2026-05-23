class APIError(Exception):
    status_code = 500
    error = "internal_error"
    message = "An internal service error occurred."
    headers: dict[str, str] | None = None

    def __init__(
        self,
        message: str | None = None,
        details: dict | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.message = message or self.message
        self.details = details
        self.headers = headers
        super().__init__(self.message)
