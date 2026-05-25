from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    environment: str = "development"
    web_concurrency: int = 1
    generated_apps_dir: Path = Path("generated/apps")

    @classmethod
    def from_env(cls) -> "Settings":
        generated_dir = Path(os.getenv("GENERATED_APPS_DIR", "generated/apps"))
        settings = cls(
            host=os.getenv("HOST", "0.0.0.0"),
            port=_env_int("PORT", 8000),
            log_level=os.getenv("LOG_LEVEL", "info"),
            environment=os.getenv("APP_ENV", "development"),
            web_concurrency=max(1, _env_int("WEB_CONCURRENCY", 1)),
            generated_apps_dir=generated_dir,
        )
        settings.ensure_directories()
        return settings

    def ensure_directories(self) -> None:
        self.generated_apps_dir.mkdir(parents=True, exist_ok=True)
