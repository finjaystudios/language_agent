import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CORSConfig:
    allowed_origins: list[str]

    @classmethod
    def from_env(cls) -> "CORSConfig":
        return cls(
            allowed_origins=parse_csv_env(os.getenv("CORS_ALLOWED_ORIGINS", "")),
        )


def parse_csv_env(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
