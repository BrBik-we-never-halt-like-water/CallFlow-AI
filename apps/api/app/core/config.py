"""Runtime configuration. Safety defaults are deliberately conservative."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Resolved from this file rather than the working directory. The API is started
# from apps/api by pm2, from the repo root by some tooling, and from apps/api by
# pytest - a CWD-relative lookup silently finds nothing in at least one of those.
_REPO_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(_REPO_ROOT / ".env")


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
    scheme, but CORS matching is exact - a missing scheme silently blocks every
    request. Add https:// when absent and strip any trailing slash.
    """
    out: list[str] = []
    for raw in _list(name):
        value = raw if raw.startswith(("http://", "https://")) else f"https://{raw}"
        out.append(value.rstrip("/"))
    return out


@dataclass(frozen=True)
class Config:
    max_calls_per_run: int = field(default_factory=lambda: _int("CALLFLOW_MAX_CALLS_PER_RUN", 3))
    allowlist: list[str] = field(default_factory=lambda: _list("CALLFLOW_ALLOWLIST"))

    # Extra browser origins allowed to call this API (deployed frontends).
    cors_origins: list[str] = field(default_factory=lambda: _origins("CALLFLOW_CORS_ORIGINS"))

    # "text" for a human tailing stdout (the default - matches every deployment
    # today); "json" for a deployment shipping to a log aggregator that wants
    # one parseable object per line instead.
    log_format: str = field(default_factory=lambda: os.getenv("CALLFLOW_LOG_FORMAT", "text"))

    # This API's own publicly-reachable base URL (e.g. https://api.example.com,
    # no trailing slash). Kept through the CALL-E removal because the voice
    # runtime needs a callback base to POST a finished call's transcript back to
    # (RUNBOOK_HET_PART_1.md P1-T4); nothing reads it until that lands.
    public_api_url: str = field(
        default_factory=lambda: os.getenv("CALLFLOW_PUBLIC_API_URL", "").rstrip("/")
    )

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

    # How many contacts in one run may be dialling at once. Starts conservative
    # rather than guessing a number a carrier might reject under load.
    max_concurrent_calls: int = field(
        default_factory=lambda: _int("CALLFLOW_MAX_CONCURRENT_CALLS", 5)
    )

    # --- Supabase: identity and persistence ---------------------------------
    supabase_url: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", "").rstrip("/"))
    supabase_project_ref: str = field(
        default_factory=lambda: os.getenv("SUPABASE_PROJECT_REF", "")
    )
    supabase_publishable_key: str = field(
        default_factory=lambda: os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    )
    # Bypasses RLS. Reachable only through app/database/privileged.py.
    supabase_secret_key: str = field(default_factory=lambda: os.getenv("SUPABASE_SECRET_KEY", ""))

    # Asymmetric signing keys mean tokens verify against the public JWKS, so the
    # API holds no shared secret. SUPABASE_JWT_SECRET is the legacy HS256 fallback.
    supabase_jwks_url: str = field(default_factory=lambda: os.getenv("SUPABASE_JWKS_URL", ""))
    supabase_jwt_secret: str = field(default_factory=lambda: os.getenv("SUPABASE_JWT_SECRET", ""))

    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    db_pool_min: int = field(default_factory=lambda: _int("DB_POOL_MIN", 2))
    db_pool_max: int = field(default_factory=lambda: _int("DB_POOL_MAX", 10))
    db_command_timeout: float = 30.0

    # Pepper for the suppression phone_hash. Changing it orphans every existing
    # suppression row, so it is effectively permanent once live data exists.
    phone_hash_pepper: str = field(default_factory=lambda: os.getenv("PHONE_HASH_PEPPER", ""))

    whatsapp_token: str = field(default_factory=lambda: os.getenv("WHATSAPP_TOKEN", ""))
    whatsapp_phone_number_id: str = field(
        default_factory=lambda: os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    )

    # Transactional email (invitations). Empty key ⇒ EmailGateway refuses to send
    # rather than silently dropping the message.
    resend_api_key: str = field(default_factory=lambda: os.getenv("RESEND_API_KEY", ""))
    resend_from_email: str = field(
        default_factory=lambda: os.getenv(
            "RESEND_FROM_EMAIL", "CallFlow AI <noreply@callflow-ai.brbik.com>"
        )
    )

    # Where the web app is served, for building links that go out in email.
    site_url: str = field(
        default_factory=lambda: os.getenv("SITE_URL", "http://localhost:3000").rstrip("/")
    )

    # --- LiveKit: the media/SIP substrate ------------------------------------
    # CallFlow's own LiveKit Cloud project, not an org's credential: every
    # organisation's calls run through it, on their own carrier trunks. Empty
    # key/secret ⇒ `LiveKitGateway` refuses to construct rather than failing at
    # the first API call, same spirit as the old `require_api_key()`.
    livekit_url: str = field(default_factory=lambda: os.getenv("LIVEKIT_URL", "").rstrip("/"))
    livekit_api_key: str = field(default_factory=lambda: os.getenv("LIVEKIT_API_KEY", ""))
    livekit_api_secret: str = field(default_factory=lambda: os.getenv("LIVEKIT_API_SECRET", ""))

    # Symmetric key for org-owned third-party provider credentials (Twilio/Plivo
    # auth tokens). Same sensitivity class as SUPABASE_SECRET_KEY - never enters
    # the database, only this process's environment. A Fernet key: 32 url-safe
    # base64-encoded bytes, e.g. `Fernet.generate_key()`.
    provider_credentials_key: str = field(
        default_factory=lambda: os.getenv("PROVIDER_CREDENTIALS_KEY", "")
    )


config = Config()
