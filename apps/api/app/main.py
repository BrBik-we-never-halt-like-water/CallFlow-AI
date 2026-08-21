"""FastAPI surface consumed by the Next.js dashboard."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routes.ai_providers import router as ai_providers_router
from app.api.v1.routes.api_keys import router as api_keys_router
from app.api.v1.routes.escalations import router as escalations_router
from app.api.v1.routes.integrations import router as integrations_router
from app.api.v1.routes.internal import router as internal_router
from app.api.v1.routes.invitations import router as invitations_router
from app.api.v1.routes.messages import router as messages_router
from app.api.v1.routes.organisations import router as organisations_router
from app.api.v1.routes.profile import router as profile_router
from app.api.v1.routes.runs import router as runs_router
from app.api.v1.routes.sharing import router as sharing_router
from app.api.v1.routes.suppressions import router as suppressions_router
from app.api.v1.routes.telephony import router as telephony_router
from app.api.v1.routes.telephony_numbers import router as telephony_numbers_router
from app.api.v1.routes.voice_agents import router as voice_agents_router
from app.core.config import config
from app.core.logging import configure_logging
from app.database import database
from app.database.session import DatabasePoolBusy

configure_logging(json_format=config.log_format == "json")
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
app.include_router(escalations_router)
app.include_router(runs_router)
app.include_router(sharing_router)
app.include_router(suppressions_router)
app.include_router(api_keys_router)
app.include_router(integrations_router)
app.include_router(ai_providers_router)
app.include_router(voice_agents_router)
app.include_router(messages_router)
app.include_router(telephony_router)
app.include_router(telephony_numbers_router)
# Not a public API - the voice runtime's callback, guarded by a shared secret.
app.include_router(internal_router)


@app.exception_handler(DatabasePoolBusy)
async def _pool_busy(_: Request, exc: DatabasePoolBusy) -> JSONResponse:
    """Answer saturation, rather than leaving the caller holding an open socket.

    503 with `Retry-After`, because the condition is transient and the client's
    correct move is to try again - not to treat this as a bad request. The
    alternative is what this replaces: no response at all, which every caller
    experiences as a permanent loading state.
    """
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": f"{exc} Try again in a moment."},
        headers={"Retry-After": "5"},
    )


@app.get("/")
def root() -> dict[str, str]:
    """Cheapest possible liveness probe.

    Render's health check and any keep-alive pinger hit this. It touches no
    locks and no config so it can never be the slow thing.
    """
    return {"service": "callflow-api", "status": "ok"}


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Unauthenticated, so it reports only the deployment's own readiness -
    never any one organisation's data."""
    # Was hard-coded false while origination did not exist. It does now
    # (`services/run_dispatch.py` -> `RunDialer` -> `CreateSIPParticipant`), so
    # this reports whether *this deployment* can actually dial: without a
    # LiveKit key, secret and SIP host, `LiveKitGateway` refuses to construct
    # and no run can place a call whatever else is configured.
    #
    # It deliberately does not check whether any organisation has connected a
    # carrier or a verified number - that is per-org, and the run composer
    # already refuses with a specific reason naming the thing to go and fix.
    calling_available = bool(
        config.livekit_api_key and config.livekit_api_secret and config.livekit_sip_host
    )
    return {
        "ok": True,
        "calling_available": calling_available,
        # Occupancy, not credentials: how many pooled connections exist and how
        # many are free right now. `pool_free: 0` under load is the signature of
        # the stall this endpoint exists to make diagnosable without SSH.
        "database": database.stats(),
    }


