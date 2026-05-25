import os
from dataclasses import dataclass

from app.core.config import parse_csv_env


@dataclass(frozen=True)
class CORSConfig:
    allowed_origins: list[str]

    @classmethod
    def from_env(cls) -> "CORSConfig":
        return cls(allowed_origins=parse_csv_env(os.getenv("CORS_ALLOWED_ORIGINS", "")))
