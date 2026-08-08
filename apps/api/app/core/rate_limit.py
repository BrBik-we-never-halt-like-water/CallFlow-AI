"""Per-organisation rate limiting.

Two limits, both fail closed:
  * per-window - stops one organisation's burst of runs from draining the
                 engine balance or dialling a number too fast
  * per-day    - a daily ceiling on real calls, per organisation

Both buckets are keyed by organisation, not by IP: this used to be IP-keyed with
one process-global daily bucket, from when the product was an unauthenticated
public demo. Once every caller is a signed-in member of a real organisation,
keying by IP is both wrong (an office NAT puts unrelated visitors in the same
bucket) and unsafe (two unrelated paying organisations on the same deployment
would drain, and rate-limit, each other's shared budget). `key` is the
organisation id today; nothing here assumes it's an IP.

The owner bypasses both by sending an owner key, so testing is unrestricted.
Limits default to the deployment's env-var config but accept an organisation's
own override (`org_safety_settings`), resolved once per run by the caller.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from app.core.config import config


@dataclass(frozen=True)
class LimitVerdict:
    allowed: bool
    reason: str = ""
    retry_after_seconds: int = 0


class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windowed: dict[str, deque[float]] = defaultdict(deque)
        self._daily: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, bucket: deque[float], window: float, now: float) -> None:
        while bucket and now - bucket[0] > window:
            bucket.popleft()

    def check(
        self,
        key: str,
        *,
        calls: int,
        is_owner: bool = False,
        rate_limit_calls: int | None = None,
        rate_limit_window_seconds: int | None = None,
        daily_call_budget: int | None = None,
    ) -> LimitVerdict:
        """Check whether `calls` live calls may be placed for this key.

        Overrides default to the deployment's env-var config when omitted; the
        caller passes an organisation's own (`org_safety_settings`).
        """
        if is_owner:
            return LimitVerdict(True)

        window_calls = rate_limit_calls if rate_limit_calls is not None else config.rate_limit_calls
        window_seconds = float(
            rate_limit_window_seconds
            if rate_limit_window_seconds is not None
            else config.rate_limit_window_seconds
        )
        budget = daily_call_budget if daily_call_budget is not None else config.daily_call_budget

        now = time.monotonic()

        with self._lock:
            windowed_bucket = self._windowed[key]
            daily_bucket = self._daily[key]
            self._prune(windowed_bucket, window_seconds, now)
            self._prune(daily_bucket, 86_400.0, now)

            if len(daily_bucket) + calls > budget:
                return LimitVerdict(
                    False,
                    f"This organisation's daily budget of {budget} calls is used up. "
                    "It resumes tomorrow, or raise it in Settings → Safety.",
                )

            if len(windowed_bucket) + calls > window_calls:
                oldest = windowed_bucket[0] if windowed_bucket else now
                retry = max(1, int(window_seconds - (now - oldest)))
                mins = max(1, retry // 60)
                return LimitVerdict(
                    False,
                    f"Call limit reached ({window_calls} per "
                    f"{int(window_seconds // 60)} minutes). Try again in about {mins} minute"
                    f"{'s' if mins != 1 else ''}.",
                    retry,
                )

            # Reserve the slots now so concurrent requests cannot both pass.
            for _ in range(calls):
                windowed_bucket.append(now)
                daily_bucket.append(now)

            return LimitVerdict(True)

    def release(self, key: str, calls: int) -> None:
        """Give back reserved slots when a run fails before dialing."""
        with self._lock:
            windowed_bucket = self._windowed.get(key)
            daily_bucket = self._daily.get(key)
            for _ in range(calls):
                if windowed_bucket:
                    windowed_bucket.pop()
                if daily_bucket:
                    daily_bucket.pop()

    def snapshot(
        self,
        key: str,
        *,
        rate_limit_calls: int | None = None,
        rate_limit_window_seconds: int | None = None,
        daily_call_budget: int | None = None,
    ) -> dict[str, int]:
        now = time.monotonic()
        with self._lock:
            daily_bucket = self._daily[key]
            self._prune(daily_bucket, 86_400.0, now)
            return {
                "used_today": len(daily_bucket),
                "daily_budget": (
                    daily_call_budget if daily_call_budget is not None else config.daily_call_budget
                ),
                "per_window": (
                    rate_limit_calls if rate_limit_calls is not None else config.rate_limit_calls
                ),
                "window_minutes": int(
                    (
                        rate_limit_window_seconds
                        if rate_limit_window_seconds is not None
                        else config.rate_limit_window_seconds
                    )
                    // 60
                ),
            }


limiter = RateLimiter()
