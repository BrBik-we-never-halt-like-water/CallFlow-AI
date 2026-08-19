"""The numbers an organisation owns, and connecting them to LiveKit.

Its own module and its own prefix rather than living under `/voice-agents`,
because a number is no longer a property of an agent (ADR-8): it belongs to the
organisation, and a run picks which of them to dial from.

Numbers are masked in every response. The full number is a separate,
permissioned, audit-logged reveal (CLAUDE.md non-negotiable #4) - a picker only
needs enough digits to tell two lines apart.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.auth.dependencies import CurrentUser, RequirePermission
from app.auth.permissions import Permission
from app.core.crypto import CredentialsNotConfigured, unpack_fields
from app.database import database
from app.database.repositories import provider_credentials as credentials_repo
from app.database.repositories import telephony_numbers as numbers_repo
from app.database.repositories import voice_agents as voice_agents_repo
from app.domain.numbers import InvalidTransition, NumberStatus, is_diallable
from app.domain.safety import mask
from app.integrations.telephony import CarrierError
from app.services.number_directory import UnsupportedCarrier, sync_numbers
from app.services.number_provisioning import ProvisioningRefused, connect_number

log = logging.getLogger("app.api.v1.telephony_numbers")

router = APIRouter(prefix="/api/v1/telephony", tags=["telephony"])


class NumberOut(BaseModel):
    """One number, as a picker needs it."""

    id: str
    provider: str
    #: Masked. Enough to tell two lines apart, not enough to dial.
    phone_masked: str
    label: str | None
    status: str
    #: Whether a run may dial from it - the domain's rule, not a status string
    #: comparison the frontend would have to keep in step.
    diallable: bool
    last_error: str | None
    last_synced_at: datetime | None


def _out(row: asyncpg.Record) -> NumberOut:
    status_value = NumberStatus(row["status"])
    return NumberOut(
        id=str(row["id"]),
        provider=row["provider"],
        phone_masked=mask(row["phone_e164"]),
        label=row["label"],
        status=status_value.value,
        # A verified row with no trunk would be a provisioning bug; reporting it
        # as diallable would offer a run a line that fails at LiveKit with the
        # phone already ringing.
        diallable=is_diallable(status_value) and bool(row["livekit_outbound_trunk_id"]),
        last_error=row["last_error"],
        last_synced_at=row["last_synced_at"],
    )


@router.get("/numbers", response_model=list[NumberOut])
async def list_numbers(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_READ))],
    provider: Annotated[str | None, Query()] = None,
) -> list[NumberOut]:
    """What this organisation holds, from CallFlow's own records.

    Does not call the carrier: a picker must not depend on a vendor being
    reachable. `POST /numbers/sync` is what refreshes from the account.
    """
    async with database.as_user(user.auth_user_id) as conn:
        rows = await numbers_repo.list_for_org(conn, user.org_id, provider=provider)
    return [_out(row) for row in rows]


@router.post("/numbers/sync", response_model=list[NumberOut])
async def sync_provider_numbers(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_WRITE))],
    provider: Annotated[str, Query()],
) -> list[NumberOut]:
    """Ask the carrier what this account actually holds, and record it.

    Idempotent by the upsert, so pressing it twice is a no-op rather than a
    second set of rows. A number that has since disappeared from the carrier is
    marked `disabled`, never deleted - it may have placed real calls.
    """
    async with database.as_user(user.auth_user_id) as conn:
        row = await credentials_repo.get_for_provider(conn, user.org_id, provider)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No {provider} credentials are stored for this organisation. "
                    "Add them in Integrations first."
                ),
            )
        try:
            credentials = unpack_fields(row)
        except CredentialsNotConfigured as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"The stored {provider} credentials could not be read. "
                    "Re-enter them in Integrations."
                ),
            ) from exc

        try:
            rows = await sync_numbers(
                conn,
                org_id=user.org_id,
                created_by=user.id,
                provider=provider,
                credentials=credentials,
            )
        except UnsupportedCarrier as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        except CarrierError as exc:
            # The vendor's own message: it is the only part that says why, and it
            # is already written as something an operator can act on.
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            ) from exc

        rows = await _make_diallable(
            conn,
            org_id=user.org_id,
            auth_user_id=user.auth_user_id,
            provider=provider,
            credentials=credentials,
            rows=rows,
        )

    return [_out(row) for row in rows]


async def _make_diallable(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    auth_user_id: str,
    provider: str,
    credentials: dict[str, str],
    rows: list[asyncpg.Record],
) -> list[asyncpg.Record]:
    """Point every freshly-discovered number at LiveKit, so a sync leaves them
    ready to dial from.

    Discovery on its own produces a `discovered` row with no trunk, which
    `is_diallable` refuses - so before this ran, connecting a carrier and
    syncing it left the run composer still reporting no line to dial from, and
    the missing step was invisible from the product.

    **Outbound only.** `connect_number` defaults `attach_number=False`: it
    builds everything needed to dial *out* and does not touch what answers the
    number, because a sync is not consent to redirect a line that may already
    be a support queue.

    Failures are per number and never raise. The carrier and LiveKit are two
    separate systems and either can refuse one number for a reason that says
    nothing about the next; a sync that 502s because the third number is
    mis-configured would hide the two that worked. Each failure is left on its
    own row's `last_error`, which is what the Integrations list already shows.
    """
    pending = [r for r in rows if NumberStatus(r["status"]) is NumberStatus.DISCOVERED]
    if not pending:
        return rows

    agents = await voice_agents_repo.list_org_agents(conn, org_id)
    if not agents:
        # The dispatch rule routes inbound calls to an agent, so there has to be
        # one to name. Left `discovered` with a reason rather than failing the
        # sync: the numbers are real and the agent is one screen away.
        log.info("no voice agent yet; %d number(s) left undiallable", len(pending))
        for row in pending:
            await numbers_repo.record_error(
                conn,
                org_id=org_id,
                number_id=row["id"],
                message=(
                    "Build an agent first - a number is routed to one, so there "
                    "has to be an agent to point it at."
                ),
            )
        return await numbers_repo.list_for_org(conn, org_id, provider=provider)

    agent_id = agents[0]["id"]
    for row in pending:
        try:
            await connect_number(
                conn,
                voice_agent_id=agent_id,
                org_id=org_id,
                idempotency_key=f"sync-{row['id']}",
                provider=provider,
                credentials=credentials,
                phone_number=row["phone_e164"],
                number_ref=row["provider_number_ref"],
                label=row["label"] or row["phone_e164"],
            )
        except (ProvisioningRefused, CarrierError) as exc:
            log.info("could not make a %s number diallable: %s", provider, exc)
            await numbers_repo.record_error(
                conn, org_id=org_id, number_id=row["id"], message=str(exc)
            )
        except Exception:
            log.exception("unexpected error making a %s number diallable", provider)
            await numbers_repo.record_error(
                conn,
                org_id=org_id,
                number_id=row["id"],
                message="Something went wrong pointing this number at LiveKit. Try again.",
            )

    return await numbers_repo.list_for_org(conn, org_id, provider=provider)


class NumberStatusIn(BaseModel):
    status: str


@router.patch("/numbers/{number_id}", response_model=NumberOut)
async def update_number_status(
    number_id: UUID,
    body: NumberStatusIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_WRITE))],
) -> NumberOut:
    """Retire a number, or bring a retired one back.

    The only status change an operator makes by hand. Everything else is
    provisioning's own business, and the domain's transition check refuses a move
    that is not declared rather than persisting it.
    """
    try:
        target = NumberStatus(body.status)
    except ValueError as exc:
        allowed = ", ".join(sorted(s.value for s in NumberStatus))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{body.status}' is not a number status. Use one of: {allowed}.",
        ) from exc

    async with database.as_user(user.auth_user_id) as conn:
        try:
            row = await numbers_repo.set_status(
                conn, org_id=user.org_id, number_id=number_id, target=target
            )
        except InvalidTransition as exc:
            # The machine's own message names both ends and what was possible.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That number no longer exists."
        )
    return _out(row)
