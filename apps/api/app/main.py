"""FastAPI surface consumed by the Next.js dashboard."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes.api_keys import router as api_keys_router
from app.api.v1.routes.campaigns import router as campaigns_router
from app.api.v1.routes.integrations import router as integrations_router
from app.api.v1.routes.invitations import router as invitations_router
from app.api.v1.routes.organisations import router as organisations_router
from app.api.v1.routes.profile import router as profile_router
from app.api.v1.routes.runs import router as runs_router
from app.api.v1.routes.safety import router as safety_router
from app.api.v1.routes.suppressions import router as suppressions_router
from app.core.config import config
from app.database import database

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app.main")

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Open the connection pool on startup, drain it on shutdown.

    A missing DATABASE_URL is not fatal here: the calling endpoints predate the
    database and still work without it, so the API starts and the auth endpoints
    report the problem rather than the whole service refusing to boot.
    """
    try:
        await database.connect()
    except Exception:
        log.exception("database unavailable at startup - auth endpoints will fail")

    yield

    await database.disconnect()


app = FastAPI(title="CallFlow AI API", version="0.1.0", lifespan=lifespan)

# Local dev origins always work; deployed frontends are added via
# CALLFLOW_CORS_ORIGINS (comma-separated) so the API isn't open to the world.
_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    *config.cors_origins,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # Render and Vercel preview deployments get a fresh subdomain per push.
    allow_origin_regex=r"https://[a-z0-9-]+\.(onrender\.com|vercel\.app)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile_router)
app.include_router(organisations_router)
app.include_router(invitations_router)
app.include_router(campaigns_router)
app.include_router(runs_router)
app.include_router(safety_router)
app.include_router(suppressions_router)
app.include_router(api_keys_router)
app.include_router(integrations_router)


@app.get("/")
def root() -> dict[str, str]:
    """Cheapest possible liveness probe.

    Render's health check and any keep-alive pinger hit this. It touches no
    locks and no config so it can never be the slow thing.
    """
    return {"service": "callflow-api", "status": "ok"}


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Unauthenticated, so this can only report the deployment's own defaults -
    not any organisation's live usage or override. `GET /api/v1/safety` (signed
    in) is where a real `used_today` lives now that the limiter is org-scoped."""
    return {
        "ok": True,
        "api_key_configured": bool(config.api_key),
        "max_calls_per_run": config.max_calls_per_run,
        "allowlist_active": bool(config.allowlist),
        "limits": {
            "daily_budget": config.daily_call_budget,
            "per_window": config.rate_limit_calls,
            "window_minutes": config.rate_limit_window_seconds // 60,
        },
    }


