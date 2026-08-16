"""Connecting an organisation's own number to one of its voice agents.

Two endpoints over `services/number_provisioning.py`: one starts an attempt, one
reports on it. They are separate because the workflow crosses two vendors and
can take tens of seconds - long enough that holding an HTTP request open for it
would time out somewhere between the browser and here.

**Permission is `integrations:write`, not an agent-specific one.** What this
endpoint actually does is reconfigure the organisation's own Twilio or Plivo
account using the credentials stored on the Integrations page - it is that
page's action, reached from an agent. Voice-agent CRUD and any permission it
needs are Part 2's (`RUNBOOK_ARBAAZ_PART_2.md`); borrowing an enum member that
does not exist yet would block this endpoint on someone else's branch for no
gain, and inventing a second name for it would leave two to reconcile later.

Failure is reported in the attempt row, not as a 500. The workflow deliberately
returns its ledger row whichever way it goes, because a part-way failure has
created real objects at the vendors and the record of them has to survive.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser, RequirePermission
from app.auth.permissions import Permission
from app.core.crypto import CredentialsNotConfigured, decrypt
from app.database import database
from app.database.repositories import provider_credentials as credentials_repo
from app.database.repositories import telephony_provisioning as provisioning_repo
from app.domain.provisioning import ProvisioningStatus
from app.services.number_provisioning import (
    CARRIERS,
    ProvisioningRefused,
    connect_number,
)

log = logging.getLogger("app.api.v1.telephony")

router = APIRouter(prefix="/api/v1/voice-agents", tags=["telephony"])


class ConnectNumberIn(BaseModel):
    provider: str = Field(description="twilio or plivo - whichever the org has connected")
    phone_number: str = Field(min_length=4, max_length=20)
    # Twilio addresses a number by SID (`PN…`), Plivo by the number itself. The
    # adapters absorb that difference behind `number_ref`; the caller sends
    # whichever its carrier uses, and defaults to the number when omitted.
    number_ref: str | None = Field(default=None, max_length=64)
    label: str = Field(min_length=1, max_length=60)
    # The client's own retry token. Reusing it *resumes* the attempt rather than
    # starting a second one, which is what keeps a double-click from creating a
    # second LiveKit trunk pair nobody will ever clean up.
    idempotency_key: str = Field(min_length=8, max_length=120)


class ProvisioningOut(BaseModel):
    """The attempt, as the connect-a-number screen polls it.

    No trunk ids: they are LiveKit's internal handles, and an operator can do
    nothing with them. `status` plus `last_error` is the whole of what the
    screen needs to say.
    """

    id: str
    voice_agent_id: str
    status: str
    last_error: str | None
    created_at: datetime
    updated_at: datetime


def _row_to_out(row: asyncpg.Record) -> ProvisioningOut:
    return ProvisioningOut(
        id=str(row["id"]),
        voice_agent_id=str(row["voice_agent_id"]),
        status=row["status"],
        last_error=row["last_error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def _carrier_credentials(
    conn: asyncpg.Connection, org_id: UUID, provider: str
) -> dict[str, str]:
    """The stored keys for this carrier, decrypted, in its adapter's own shape.

    Both adapters take exactly two secrets under different names, so the
    mapping is here rather than in either of them - an adapter that knew about
    `provider_credentials` would be reaching back across the boundary it exists
    to hold.
    """
    row = await credentials_repo.get_for_provider(conn, org_id, provider)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"No {provider} account is connected. Add its credentials on "
                "Settings → Integrations, then connect a number."
            ),
        )
    try:
        identifier = decrypt(row["identifier_encrypted"])
        secret = decrypt(row["secret_encrypted"])
    except CredentialsNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    if provider == "twilio":
        return {"account_sid": identifier, "auth_token": secret}
    return {"auth_id": identifier, "auth_token": secret}


@router.post(
    "/{voice_agent_id}/connect-number",
    response_model=ProvisioningOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_connect_number(
    voice_agent_id: UUID,
    body: ConnectNumberIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_WRITE))],
) -> ProvisioningOut:
    """Begin connecting a number, or resume the attempt this key already began.

    202 rather than 201 because the work is not finished when this returns:
    poll the companion GET. A `verified` status here just means the whole chain
    happened to complete within the request.
    """
    if body.provider not in CARRIERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"'{body.provider}' is not a carrier CallFlow can configure. "
                f"Supported: {', '.join(sorted(CARRIERS))}."
            ),
        )

    async with database.as_user(user.auth_user_id) as conn:
        if not await provisioning_repo.agent_is_visible(conn, voice_agent_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unknown voice agent"
            )
        credentials = await _carrier_credentials(conn, user.org_id, body.provider)

        try:
            row = await connect_number(
                conn,
                voice_agent_id=voice_agent_id,
                org_id=user.org_id,
                idempotency_key=body.idempotency_key,
                provider=body.provider,
                credentials=credentials,
                phone_number=body.phone_number,
                number_ref=body.number_ref,
                label=body.label,
            )
        except ProvisioningRefused as exc:
            # Raised only before an attempt row exists, so there is nothing
            # recorded to hand back and nothing a retry would resume.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unknown voice agent"
            ) from exc

    if row["status"] != ProvisioningStatus.VERIFIED.value:
        log.info("connect-number for agent %s did not complete in one pass", voice_agent_id)
    return _row_to_out(row)


@router.get("/{voice_agent_id}/connect-number", response_model=ProvisioningOut)
async def connect_number_status(
    voice_agent_id: UUID,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_READ))],
) -> ProvisioningOut:
    """The newest attempt for this agent, which is what the screen reports on."""
    async with database.as_user(user.auth_user_id) as conn:
        row = await provisioning_repo.latest_for_agent(conn, voice_agent_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No number has been connected to this agent yet.",
        )
    return _row_to_out(row)
