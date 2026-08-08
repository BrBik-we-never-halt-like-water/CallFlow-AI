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


def _origins(name: str) -> list[str]:
    """Parse CORS origins, tolerating Render's bare-hostname form.

    `fromService … property: host` yields "callflow-web.onrender.com" with no
    scheme, but CORS matching is exact   a missing scheme silently blocks every
    request. Add https:// when absent and strip any trailing slash.
    """
    out: list[str] = []
    for raw in _list(name):
        value = raw if raw.startswith(("http://", "https://")) else f"https://{raw}"
        out.append(value.rstrip("/"))
    return out


@dataclass(frozen=True)
class Config:
    api_key: str = field(default_factory=lambda: os.getenv("CALLE_API_KEY", ""))
    default_region: str = field(default_factory=lambda: os.getenv("CALLE_DEFAULT_REGION", "IN"))
    default_language: str = field(default_factory=lambda: os.getenv("CALLE_DEFAULT_LANGUAGE", "en"))

    # Dry run is the default everywhere. Dialing is opt-in, never incidental.
    dry_run: bool = field(default_factory=lambda: _bool("CALLFLOW_DRY_RUN", True))
    max_calls_per_run: int = field(default_factory=lambda: _int("CALLFLOW_MAX_CALLS_PER_RUN", 3))
    allowlist: list[str] = field(default_factory=lambda: _list("CALLFLOW_ALLOWLIST"))

    # Extra browser origins allowed to call this API (deployed frontends).
    cors_origins: list[str] = field(default_factory=lambda: _origins("CALLFLOW_CORS_ORIGINS"))

    # --- public demo limits -------------------------------------------------
    # The hosted dashboard lets visitors call their own number. These caps stop
    # one visitor draining the owner's credits or dialing strangers repeatedly.
    rate_limit_calls: int = field(default_factory=lambda: _int("CALLFLOW_RATE_LIMIT_CALLS", 5))
    rate_limit_window_seconds: int = field(
        default_factory=lambda: _int("CALLFLOW_RATE_LIMIT_WINDOW", 3600)
    )
    daily_call_budget: int = field(default_factory=lambda: _int("CALLFLOW_DAILY_BUDGET", 20))

    # Shared secret that lifts the limits, so the owner can test freely.
    owner_key: str = field(default_factory=lambda: os.getenv("CALLFLOW_OWNER_KEY", ""))

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
            "No Voice API key is set. Copy .env.example to .env and set "
            "CALLE_API_KEY before placing live calls."
        )
    return config.api_key
