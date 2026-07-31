"""Runtime configuration. Safety defaults are deliberately conservative."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"true", "1", "yes"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, ""))
    except ValueError:
        return default


def _list(name: str) -> list[str]:
    return [p.strip() for p in os.getenv(name, "").split(",") if p.strip()]


@dataclass(frozen=True)
class Config:
    api_key: str = field(default_factory=lambda: os.getenv("CALLE_API_KEY", ""))
    default_region: str = field(default_factory=lambda: os.getenv("CALLE_DEFAULT_REGION", "IN"))
    default_language: str = field(default_factory=lambda: os.getenv("CALLE_DEFAULT_LANGUAGE", "en"))

    # Dry run is the default everywhere. Dialing is opt-in, never incidental.
    dry_run: bool = field(default_factory=lambda: _bool("CALLFLOW_DRY_RUN", True))
    max_calls_per_run: int = field(default_factory=lambda: _int("CALLFLOW_MAX_CALLS_PER_RUN", 3))
    allowlist: list[str] = field(default_factory=lambda: _list("CALLFLOW_ALLOWLIST"))

    poll_interval_seconds: float = 10.0
    poll_timeout_seconds: float = 900.0

    whatsapp_token: str = field(default_factory=lambda: os.getenv("WHATSAPP_TOKEN", ""))
    whatsapp_phone_number_id: str = field(
        default_factory=lambda: os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    )


config = Config()


def require_api_key() -> str:
    if not config.api_key:
        raise RuntimeError(
            "CALLE_API_KEY is not set. Copy .env.example to .env and add your key "
            "from https://dashboard.heycall-e.com"
        )
    return config.api_key
