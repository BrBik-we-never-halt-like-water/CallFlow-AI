"""In-memory run store.

Deliberately simple: the hackathon demo needs judges to see live state, not a
production database. Swap for Postgres by reimplementing this interface.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from .models import CallOutcome


class RunStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, dict[str, Any]] = {}

    def create_run(self, campaign_id: str, total: int, dry_run: bool) -> str:
        run_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._runs[run_id] = {
                "id": run_id,
                "campaign_id": campaign_id,
                "total": total,
                "dry_run": dry_run,
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": None,
                "outcomes": [],
                "error": None,
            }
        return run_id

    def append_outcome(self, run_id: str, outcome: CallOutcome) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is not None:
                run["outcomes"].append(outcome.model_dump(mode="json"))

    def finish(self, run_id: str, error: str | None = None) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is not None:
                run["status"] = "failed" if error else "completed"
                run["finished_at"] = datetime.now(timezone.utc).isoformat()
                run["error"] = error

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            run = self._runs.get(run_id)
            return dict(run) if run else None

    def list_runs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {k: v for k, v in run.items() if k != "outcomes"}
                | {"completed": len(run["outcomes"])}
                for run in sorted(
                    self._runs.values(), key=lambda r: r["started_at"], reverse=True
                )
            ]


store = RunStore()
