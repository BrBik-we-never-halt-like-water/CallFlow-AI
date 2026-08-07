"""Per-visitor rate limiting for the public deployment.

The hosted dashboard lets anyone enter their own number and receive a real
call. That is the point of the demo — but it runs on the owner's engine
credits, so an unlimited public endpoint would be trivially drainable and
could be pointed at strangers.

Two limits, both fail closed:
  * per-IP    — stops one visitor burning the balance or harassing a number
  * per-day   — a global floor so the demo still works late in the judging day

The owner bypasses both by sending an owner key, so testing is unrestricted.
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
        self._per_ip: dict[str, deque[float]] = defaultdict(deque)
        self._today: deque[float] = deque()

    def _prune(self, bucket: deque[float], window: float, now: float) -> None:
        while bucket and now - bucket[0] > window:
            bucket.popleft()

    def check(self, ip: str, *, calls: int, is_owner: bool = False) -> LimitVerdict:
        """Check whether `calls` live calls may be placed from this IP."""
        if is_owner:
            return LimitVerdict(True)

        now = time.monotonic()
        window = float(config.rate_limit_window_seconds)

        with self._lock:
            ip_bucket = self._per_ip[ip]
            self._prune(ip_bucket, window, now)
            self._prune(self._today, 86_400.0, now)

            if len(self._today) + calls > config.daily_call_budget:
                return LimitVerdict(
                    False,
                    f"The shared daily demo budget of {config.daily_call_budget} calls is used up. "
                    "It resumes tomorrow.",
                )

            if len(ip_bucket) + calls > config.rate_limit_calls:
                oldest = ip_bucket[0] if ip_bucket else now
                retry = max(1, int(window - (now - oldest)))
                mins = max(1, retry // 60)
                return LimitVerdict(
                    False,
                    f"Call limit reached ({config.rate_limit_calls} per "
                    f"{int(window // 60)} minutes). Try again in about {mins} minute"
                    f"{'s' if mins != 1 else ''}.",
                    retry,
                )

            # Reserve the slots now so concurrent requests cannot both pass.
            for _ in range(calls):
                ip_bucket.append(now)
                self._today.append(now)

            return LimitVerdict(True)

    def release(self, ip: str, calls: int) -> None:
        """Give back reserved slots when a run fails before dialing."""
        with self._lock:
            bucket = self._per_ip.get(ip)
            for _ in range(calls):
                if bucket:
                    bucket.pop()
                if self._today:
                    self._today.pop()

    def snapshot(self) -> dict[str, int]:
        now = time.monotonic()
        with self._lock:
            self._prune(self._today, 86_400.0, now)
            return {
                "used_today": len(self._today),
                "daily_budget": config.daily_call_budget,
                "per_window": config.rate_limit_calls,
                "window_minutes": int(config.rate_limit_window_seconds // 60),
            }


limiter = RateLimiter()
