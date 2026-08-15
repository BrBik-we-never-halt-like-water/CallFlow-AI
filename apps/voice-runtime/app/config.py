"""Runtime configuration for the voice worker.

Same shape as `apps/api/app/core/config.py` deliberately - a frozen dataclass
read once at import, `os.getenv` with defaults - because this repo already has
that convention and a second process is not a reason to invent a second one.

This worker holds no organisation's credentials of its own. LiveKit connects it
to rooms; every STT/TTS/LLM key arrives per job, resolved by `apps/api` from
that org's `provider_credentials`. The only secrets here are CallFlow's own.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Resolved from this file, not the working directory: pm2 starts this from an
# absolute path and pytest from the package root, and a CWD-relative lookup
# silently finds nothing in at least one of them.
_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, ""))
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    # Must match `LIVEKIT_AGENT_NAME` on the API side, or dispatches name a
    # worker that never answers and callers hear silence.
    agent_name: str = field(
        default_factory=lambda: os.getenv("LIVEKIT_AGENT_NAME", "callflow-voice")
    )

    livekit_url: str = field(default_factory=lambda: os.getenv("LIVEKIT_URL", "").rstrip("/"))
    livekit_api_key: str = field(default_factory=lambda: os.getenv("LIVEKIT_API_KEY", ""))
    livekit_api_secret: str = field(default_factory=lambda: os.getenv("LIVEKIT_API_SECRET", ""))

    # Where a finished call is reported. Both halves are required to report at
    # all - see `reporter.py`, which refuses to start a call it could never
    # report the result of rather than discovering that once the call is over.
    api_base_url: str = field(
        default_factory=lambda: os.getenv("CALLFLOW_PUBLIC_API_URL", "").rstrip("/")
    )
    internal_api_secret: str = field(
        default_factory=lambda: os.getenv("CALLFLOW_INTERNAL_API_SECRET", "")
    )

    # A call that outlives this is abandoned. The carrier enforces its own
    # ceiling too (`max_call_duration` on the SIP participant); this is the
    # worker's own backstop for a conversation that connects but never ends.
    max_call_seconds: int = field(default_factory=lambda: _int("CALLFLOW_MAX_CALL_SECONDS", 900))

    # How long to keep retrying the completion callback. A transcript that
    # cannot be delivered is a call the operator never sees the result of, so
    # this is deliberately generous.
    report_retry_seconds: int = field(
        default_factory=lambda: _int("CALLFLOW_REPORT_RETRY_SECONDS", 120)
    )

    def missing(self) -> list[str]:
        """Which required settings are unset, for a startup check that names
        all of them at once rather than failing on whichever is read first."""
        required = {
            "LIVEKIT_URL": self.livekit_url,
            "LIVEKIT_API_KEY": self.livekit_api_key,
            "LIVEKIT_API_SECRET": self.livekit_api_secret,
            "CALLFLOW_PUBLIC_API_URL": self.api_base_url,
            "CALLFLOW_INTERNAL_API_SECRET": self.internal_api_secret,
        }
        return sorted(name for name, value in required.items() if not value)


config = Config()
