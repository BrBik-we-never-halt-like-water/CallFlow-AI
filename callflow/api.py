"""FastAPI surface consumed by the Next.js dashboard."""

from __future__ import annotations

import logging
import secrets
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .campaigns import (
    BUILT_IN_IDS,
    FIELD_TYPES,
    REGISTRY,
    SCHEMAS,
    delete_campaign,
    get_campaign,
    register_campaign,
)
from .config import config
from .models import Contact
from .orchestrator import CampaignRunner, render_goal
from .ratelimit import limiter
from .store import store

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("callflow.api")

app = FastAPI(title="CallFlow AI API", version="0.1.0")

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


class ContactIn(BaseModel):
    name: str
    phone: str
    region: str | None = None
    language: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class RunRequest(BaseModel):
    campaign_id: str
    contacts: list[ContactIn]
    # Defaults to the server's safety setting; must be explicitly set false to dial.
    dry_run: bool | None = None


@app.get("/")
def root() -> dict[str, str]:
    """Cheapest possible liveness probe.

    Render's health check and any keep-alive pinger hit this. It touches no
    locks and no config so it can never be the slow thing.
    """
    return {"service": "callflow-api", "status": "ok"}


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "dry_run_default": config.dry_run,
        "api_key_configured": bool(config.api_key),
        "max_calls_per_run": config.max_calls_per_run,
        "allowlist_active": bool(config.allowlist),
        "limits": limiter.snapshot(),
    }


class FieldIn(BaseModel):
    key: str = Field(min_length=1, max_length=40)
    type: str = "string"
    description: str = ""


class CampaignIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    goal_template: str = Field(min_length=40)
    extra_fields: list[FieldIn] = Field(default_factory=list)
    region: str | None = None
    language: str | None = None
    escalate_on_negative: bool = True


def _campaign_json(c: Any) -> dict[str, Any]:
    return {
        "id": c.id,
        "name": c.name,
        "region": c.region,
        "language": c.language,
        "outcome_fields": c.outcome_fields,
        "goal_template": c.goal_template,
        "goal_preview": c.goal_template[:280],
        "built_in": c.id in BUILT_IN_IDS,
    }


@app.get("/api/campaigns")
def list_campaigns() -> list[dict[str, Any]]:
    return [_campaign_json(c) for c in REGISTRY.values()]


@app.post("/api/campaigns", status_code=201)
def create_campaign(body: CampaignIn) -> dict[str, Any]:
    bad = [f.type for f in body.extra_fields if f.type not in FIELD_TYPES]
    if bad:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported field type(s): {', '.join(bad)}. Use: {', '.join(sorted(FIELD_TYPES))}",
        )

    # The engine rejects thin task text with call_not_ready, so catch it here where
    # we can give a useful message instead of failing mid-run.
    if len(body.goal_template.strip()) < 40:
        raise HTTPException(
            status_code=400,
            detail="The goal is too short. Describe what the agent should say, ask, and do.",
        )

    campaign = register_campaign(
        name=body.name,
        goal_template=body.goal_template,
        extra_fields=[f.model_dump() for f in body.extra_fields],
        region=body.region,
        language=body.language,
        escalate_on_negative=body.escalate_on_negative,
    )
    return _campaign_json(campaign)


@app.delete("/api/campaigns/{campaign_id}", status_code=204)
def remove_campaign(campaign_id: str) -> None:
    try:
        delete_campaign(campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/preview")
def preview(req: RunRequest) -> dict[str, Any]:
    """Render goals without touching the voice engine. Free, instant, no credits."""
    try:
        campaign = get_campaign(req.campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    previews = []
    for c in req.contacts:
        try:
            contact = Contact(**c.model_dump())
        except ValueError as exc:
            previews.append({"name": c.name, "error": str(exc)})
            continue
        previews.append({"name": contact.name, "goal": render_goal(campaign, contact)})
    return {"campaign_id": campaign.id, "previews": previews}


def _execute(run_id: str, campaign_id: str, contacts: list[Contact], dry_run: bool) -> None:
    campaign = get_campaign(campaign_id)
    runner = CampaignRunner(dry_run=dry_run, result_schema=SCHEMAS.get(campaign_id))
    try:
        runner.run(
            campaign,
            contacts,
            on_progress=lambda outcome: store.append_outcome(run_id, outcome),
        )
        store.finish(run_id)
    except Exception as exc:
        log.exception("run %s failed", run_id)
        store.finish(run_id, error=f"{type(exc).__name__}: {exc}")


def _client_ip(request: Request) -> str:
    """Real client IP behind Render's proxy."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_owner(request: Request) -> bool:
    """True when the caller presents the owner key, lifting all rate limits."""
    if not config.owner_key:
        return False
    presented = request.headers.get("x-callflow-owner-key", "")
    # Constant-time compare so the key can't be guessed by timing.
    return secrets.compare_digest(presented, config.owner_key)


@app.post("/api/runs")
def start_run(
    req: RunRequest, background: BackgroundTasks, request: Request
) -> dict[str, Any]:
    try:
        get_campaign(req.campaign_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not req.contacts:
        raise HTTPException(status_code=400, detail="At least one contact is required.")

    try:
        contacts = [Contact(**c.model_dump()) for c in req.contacts]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    dry_run = config.dry_run if req.dry_run is None else req.dry_run
    if not dry_run and not config.api_key:
        raise HTTPException(
            status_code=400,
            detail="No Voice API key is configured   cannot place live calls.",
        )

    # Live calls spend the owner's credits and ring real people, so the public
    # demo is rate limited. Dry run stays unlimited.
    if not dry_run:
        verdict = limiter.check(
            _client_ip(request), calls=len(contacts), is_owner=_is_owner(request)
        )
        if not verdict.allowed:
            raise HTTPException(
                status_code=429,
                detail=verdict.reason,
                headers=(
                    {"Retry-After": str(verdict.retry_after_seconds)}
                    if verdict.retry_after_seconds
                    else None
                ),
            )

    run_id = store.create_run(req.campaign_id, len(contacts), dry_run)
    background.add_task(_execute, run_id, req.campaign_id, contacts, dry_run)
    return {"run_id": run_id, "dry_run": dry_run, "total": len(contacts)}


@app.get("/api/runs")
def list_runs() -> list[dict[str, Any]]:
    return store.list_runs()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    run = store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    outcomes = run["outcomes"]
    # A row exists as soon as a call is placed, so count only calls that have
    # actually resolved   an in-flight one is not progress yet.
    resolved = [o for o in outcomes if o["disposition"] != "in_flight"]
    escalated = sum(1 for o in resolved if o["disposition"] == "escalated")
    return run | {
        "stats": {
            "completed": len(resolved),
            "total": run["total"],
            "escalated": escalated,
            "auto_closed": sum(1 for o in outcomes if o["disposition"] == "auto_closed"),
            "needs_human_pct": round(100 * escalated / len(outcomes)) if outcomes else 0,
        }
    }
