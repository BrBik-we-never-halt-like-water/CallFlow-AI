"""Campaigns: the two built-in templates (global, code-defined) plus whatever
an organisation has created for itself (real rows, org-scoped)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser, RequirePermission, current_user
from app.auth.permissions import Permission
from app.database import database
from app.database.repositories import campaigns as campaigns_repo
from app.domain.campaigns import BUILT_IN_IDS, FIELD_TYPES, REGISTRY, SCHEMAS, slugify
from app.domain.entities import Campaign as CampaignEntity
from app.domain.entities import Contact
from app.domain.result_schemas import build_result_schema
from app.services.campaign_runner import render_goal

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])


class FieldIn(BaseModel):
    key: str = Field(min_length=1, max_length=40)
    type: str = "string"
    description: str = ""
    required: bool = False


class CampaignIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    goal_template: str = Field(min_length=40)
    extra_fields: list[FieldIn] = Field(default_factory=list)
    region: str | None = None
    language: str | None = None
    escalate_on_negative: bool = True


class CampaignOut(BaseModel):
    id: str
    name: str
    region: str | None
    language: str | None
    outcome_fields: dict[str, str]
    goal_template: str
    goal_preview: str
    built_in: bool


class PreviewIn(BaseModel):
    campaign_id: str
    contacts: list[dict[str, Any]]


async def resolve_campaign(
    conn: Any, org_id: Any, campaign_id: str
) -> tuple[CampaignEntity, dict[str, Any]] | None:
    """A campaign is either a built-in constant or a row this org owns."""
    if campaign_id in REGISTRY:
        return REGISTRY[campaign_id], SCHEMAS.get(campaign_id, {})

    row = await campaigns_repo.get_org_campaign(conn, org_id, campaign_id)
    if row is None:
        return None

    campaign = CampaignEntity(
        id=row["id"],
        name=row["name"],
        goal_template=row["goal_template"],
        outcome_fields=row["outcome_fields"],
        region=row["region"],
        language=row["language"],
        escalate_on_negative=row["escalate_on_negative"],
    )
    return campaign, row["result_schema"]


def _built_in_json(c: CampaignEntity) -> CampaignOut:
    return CampaignOut(
        id=c.id,
        name=c.name,
        region=c.region,
        language=c.language,
        outcome_fields=c.outcome_fields,
        goal_template=c.goal_template,
        goal_preview=c.goal_template[:280],
        built_in=True,
    )


def _row_json(row: Any) -> CampaignOut:
    return CampaignOut(
        id=row["id"],
        name=row["name"],
        region=row["region"],
        language=row["language"],
        outcome_fields=row["outcome_fields"],
        goal_template=row["goal_template"],
        goal_preview=row["goal_template"][:280],
        built_in=False,
    )


@router.get("", response_model=list[CampaignOut])
async def list_campaigns(
    user: Annotated[CurrentUser, Depends(current_user)],
) -> list[CampaignOut]:
    async with database.as_user(user.auth_user_id) as conn:
        rows = await campaigns_repo.list_org_campaigns(conn, user.org_id)
    return [_built_in_json(c) for c in REGISTRY.values()] + [_row_json(r) for r in rows]


def _validate_and_build_fields(
    body: CampaignIn,
) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    bad = [f.type for f in body.extra_fields if f.type not in FIELD_TYPES]
    if bad:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported field type(s): {', '.join(bad)}. Use: {', '.join(sorted(FIELD_TYPES))}",
        )

    # The engine rejects thin task text with call_not_ready, so catch it here where
    # we can give a useful message instead of failing mid-run.
    if len(body.goal_template.strip()) < 40:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The goal is too short. Describe what the agent should say, ask, and do.",
        )

    properties: dict[str, Any] = {}
    outcome_fields: dict[str, str] = {}
    required: list[str] = []
    for field in body.extra_fields:
        key = slugify(field.key).replace("-", "_")
        if not key:
            continue
        ftype = field.type if field.type in FIELD_TYPES else "string"
        description = field.description.strip() or f"The contact's {key.replace('_', ' ')}."
        properties[key] = {"type": ftype, "description": description}
        outcome_fields[key] = description
        if field.required:
            required.append(key)
    return properties, outcome_fields, required


@router.post("", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    body: CampaignIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.CAMPAIGNS_WRITE))],
) -> CampaignOut:
    properties, outcome_fields, required = _validate_and_build_fields(body)

    async with database.as_user(user.auth_user_id) as conn:
        existing = await campaigns_repo.list_org_campaigns(conn, user.org_id)
        taken = {r["id"] for r in existing} | BUILT_IN_IDS
        base = slugify(body.name)
        candidate = base
        suffix = 2
        while candidate in taken:
            candidate = f"{base}-{suffix}"
            suffix += 1

        row = await campaigns_repo.create_campaign(
            conn,
            org_id=user.org_id,
            created_by=user.id,
            campaign_id=candidate,
            name=body.name.strip(),
            goal_template=body.goal_template.strip(),
            outcome_fields=outcome_fields,
            result_schema=build_result_schema(properties, required),
            region=body.region,
            language=body.language,
            escalate_on_negative=body.escalate_on_negative,
        )
    return _row_json(row)


@router.patch("/{campaign_id}", response_model=CampaignOut)
async def update_campaign(
    campaign_id: str,
    body: CampaignIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.CAMPAIGNS_WRITE))],
) -> CampaignOut:
    if campaign_id in BUILT_IN_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Built-in campaigns cannot be edited. Duplicate it to make changes.",
        )

    properties, outcome_fields, required = _validate_and_build_fields(body)

    async with database.as_user(user.auth_user_id) as conn:
        row = await campaigns_repo.update_campaign(
            conn,
            org_id=user.org_id,
            campaign_id=campaign_id,
            name=body.name.strip(),
            goal_template=body.goal_template.strip(),
            outcome_fields=outcome_fields,
            result_schema=build_result_schema(properties, required),
            region=body.region,
            language=body.language,
            escalate_on_negative=body.escalate_on_negative,
        )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown campaign: {campaign_id}"
        )
    return _row_json(row)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_campaign(
    campaign_id: str,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.CAMPAIGNS_DELETE))],
) -> None:
    if campaign_id in BUILT_IN_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Built-in campaigns cannot be deleted.",
        )
    async with database.as_user(user.auth_user_id) as conn:
        deleted = await campaigns_repo.delete_campaign(conn, user.org_id, campaign_id)
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown campaign: {campaign_id}"
        )


@router.post("/preview")
async def preview(
    req: PreviewIn, user: Annotated[CurrentUser, Depends(current_user)]
) -> dict[str, Any]:
    """Render goals without touching the voice engine. Free, instant, no credits."""
    async with database.as_user(user.auth_user_id) as conn:
        resolved = await resolve_campaign(conn, user.org_id, req.campaign_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"Unknown campaign: {req.campaign_id}")
    campaign, _ = resolved

    previews = []
    for c in req.contacts:
        try:
            contact = Contact(**c)
        except ValueError as exc:
            previews.append({"name": c.get("name"), "error": str(exc)})
            continue
        previews.append({"name": contact.name, "goal": render_goal(campaign, contact)})
    return {"campaign_id": campaign.id, "previews": previews}
