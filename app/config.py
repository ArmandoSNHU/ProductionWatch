"""Runtime settings, read once from environment variables."""
import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./data/productionwatch.db"
    demo_mode: bool = False
    demo_token: str = ""
    demo_latency_seconds: float = 1.5
    log_level: str = "INFO"
    seed_on_startup: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.getenv("DATABASE_URL", cls.database_url),
            demo_mode=_env_bool("DEMO_MODE", False),
            demo_token=os.getenv("DEMO_TOKEN", ""),
            demo_latency_seconds=float(os.getenv("DEMO_LATENCY_SECONDS", cls.demo_latency_seconds)),
            log_level=os.getenv("LOG_LEVEL", cls.log_level),
            seed_on_startup=_env_bool("SEED_ON_STARTUP", True),
        )
