"""The third-party accounts an organisation connects, and their credentials.

Every provider a `voice_agent` can name lives here - carriers, speech vendors,
and the LLM marketplace - not just the two carriers this started as. The list
itself is `app/domain/providers.py`; this module is the HTTP surface over it.

Two ways in, because vendors differ and pretending otherwise would be a lie:

- **API key.** Most vendors issue one and offer nothing else. The operator
  pastes it and it is encrypted at rest.
- **OAuth.** OpenRouter hosts a login and hands back a key the organisation
  owns. `POST /providers/openrouter/oauth/exchange` completes that flow.

A provider that has no login flow never renders one - see `ConnectMethod` in
`domain/providers.py` for why that matters.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser, RequirePermission
from app.auth.permissions import Permission
from app.core.crypto import CredentialsNotConfigured, pack_fields, unpack_fields
from app.database import database
from app.database.repositories import provider_credentials as credentials_repo
from app.domain.providers import PROVIDERS, ConnectMethod, ProviderSpec, spec
from app.services.credential_check import CheckResult, check_credentials

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])

# OpenRouter's documented PKCE exchange. The only outbound call this module
# makes - everything else is storage.
_OPENROUTER_KEY_EXCHANGE = "https://openrouter.ai/api/v1/auth/keys"


def _require_known(provider: str) -> None:
    """404 for a provider CallFlow does not support.

    A plain `Literal` would give a 422 that names every valid value, which is
    fine but says nothing about *why* one is missing. This says it.
    """
    if spec(provider) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"'{provider}' is not a provider CallFlow can connect.",
        )


class CredentialFieldOut(BaseModel):
    """One input on the connect form, described by the server.

    The frontend renders whatever arrives here and knows nothing about any
    particular vendor - which is what lets a provider be added in
    `domain/providers.py` alone.
    """

    key: str
    label: str
    secret: bool
    required: bool
    placeholder: str
    help: str | None
    multiline: bool


class ProviderSpecOut(BaseModel):
    """What the settings page needs to render a provider it has never seen.

    Sent from the server rather than duplicated in the frontend: the two lists
    drifting is how a provider becomes selectable in the interface and
    unstorable by the API.

    `wired` is the honest field. False means CallFlow will encrypt and store the
    credential and nothing in a call will read it - there is no recording,
    tool-calling or tracing behind those vendors yet. The interface says exactly
    that rather than showing them as connected (CLAUDE.md non-negotiable #9).
    """

    id: str
    name: str
    roles: list[str]
    connect: str
    summary: str
    fields: list[CredentialFieldOut]
    docs_url: str
    wired: bool
    #: Whether CallFlow can prove a credential for this vendor is real - i.e.
    #: whether a probe is declared. `is_verifiable` existed on the spec already
    #: but was never sent, which left the interface with only `wired` to reason
    #: from: "a call reads this vendor", which is not "this key works". It is
    #: what decides whether Re-check is offered, and it is why a vendor with no
    #: probe says "Can't be confirmed" rather than pretending a retry would help.
    verifiable: bool
    needs_model: bool
    note: str | None


class ProviderCredentialOut(BaseModel):
    provider: str
    label: str | None
    phone_number: str | None
    created_at: datetime
    updated_at: datetime
    #: Whether the vendor confirmed these credentials work. `None` means the
    #: check could not be completed - no probe is declared for this provider,
    #: the vendor was unreachable, or the key authenticated but was scoped too
    #: narrowly to verify. Reported rather than dropped: the credential is
    #: stored either way, and telling someone it is "Connected" when nothing
    #: confirmed it is a success state for something that did not happen
    #: (CLAUDE.md non-negotiable #9, `ISSUES.md` #169).
    verified: bool | None = None
    #: Why, when `verified` is None and there is something to say.
    verification_note: str | None = None
    #: When the vendor last confirmed *these* credentials - the durable half of
    #: the same answer.
    #:
    #: `verified` above is per-request: it describes the check this call just
    #: ran, and is null on every read. That is enough for the toast at connect
    #: time and nothing else, so a card rendered after a reload had only
    #: `wired` left to go on - "does a call read this vendor", not "does this
    #: key work" - and said **Connected** for a credential stored while the
    #: vendor was unreachable, for any of the 27 vendors with no probe, and for
    #: a key revoked at the vendor's end months ago. A rejected credential was
    #: never the problem; `connect_provider` already refuses to store one.
    #:
    #: Null is the absence of a claim, not a failure, and the interface must not
    #: render it as one.
    verified_at: datetime | None = None


class ProviderCredentialIn(BaseModel):
    """Whatever fields this provider declares, by their own names.

    A free-form mapping rather than a model per vendor: there are 57 of them and
    the set is data, not code. `connect_provider` validates it against the
    provider's own `fields` - an unknown key is rejected rather than stored, so a
    typo cannot quietly persist a credential no adapter will ever look for.

    The value ceiling is generous because a Google service-account JSON is a
    field here.
    """

    fields: dict[str, str] = Field(default_factory=dict)
    phone_number: str | None = Field(default=None, max_length=20)
    label: str | None = Field(default=None, max_length=120)


class OAuthExchangeIn(BaseModel):
    """The authorization code OpenRouter redirected back with."""

    code: str = Field(min_length=1, max_length=500)
    code_verifier: str | None = Field(default=None, max_length=200)


def _row_to_out(row: asyncpg.Record) -> ProviderCredentialOut:
    return ProviderCredentialOut(
        provider=row["provider"],
        label=row["label"],
        phone_number=row["phone_number"],
        verified_at=row["verified_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("/catalogue", response_model=list[ProviderSpecOut])
async def list_catalogue(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_READ))],
) -> list[ProviderSpecOut]:
    """Every provider CallFlow supports, and how each one connects."""
    return [_spec_to_out(p) for p in PROVIDERS]


def _spec_to_out(p: ProviderSpec) -> ProviderSpecOut:
    return ProviderSpecOut(
        id=p.id,
        name=p.name,
        # Sorted so the interface's grouping is stable between requests - a set
        # iterates in whatever order it likes, and a card jumping between
        # sections on refresh reads as a bug.
        roles=sorted(r.value for r in p.roles),
        connect=p.connect.value,
        summary=p.summary,
        fields=[
            CredentialFieldOut(
                key=f.key,
                label=f.label,
                secret=f.secret,
                required=f.required,
                placeholder=f.placeholder,
                help=f.help,
                multiline=f.multiline,
            )
            for f in p.fields
        ],
        docs_url=p.docs_url,
        wired=p.is_wired,
        verifiable=p.is_verifiable,
        needs_model=p.needs_model,
        note=p.note,
    )


@router.get("/providers", response_model=list[ProviderCredentialOut])
async def list_providers(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_READ))],
) -> list[ProviderCredentialOut]:
    async with database.as_user(user.auth_user_id) as conn:
        rows = await credentials_repo.list_for_org(conn, user.org_id)
    return [_row_to_out(r) for r in rows]


@router.post("/providers/{provider}/oauth/exchange", response_model=ProviderCredentialOut)
async def exchange_oauth_code(
    provider: str,
    body: OAuthExchangeIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_WRITE))],
) -> ProviderCredentialOut:
    """Trade an authorization code for a key, and store it.

    The exchange happens server-side even though the flow starts in the
    browser: the key that comes back is a long-lived credential, and handing it
    to the frontend first would put it in a place this product otherwise takes
    care to keep it out of.
    """
    _require_known(provider)
    provider_spec = spec(provider)
    assert provider_spec is not None  # guarded above
    if provider_spec.connect is not ConnectMethod.OAUTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider_spec.name} does not offer a login flow - add an API key instead.",
        )

    payload: dict[str, str] = {"code": body.code}
    if body.code_verifier:
        payload["code_verifier"] = body.code_verifier
        payload["code_challenge_method"] = "S256"

    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            response = await http.post(_OPENROUTER_KEY_EXCHANGE, json=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not reach {provider_spec.name} to finish connecting.",
        ) from exc

    if response.status_code >= 300:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{provider_spec.name} rejected the authorization code. "
                "It may have already been used - start the connection again."
            ),
        )

    key = str(response.json().get("key") or "")
    if not key:
        # The code is single-use, so there is nothing to retry with. Saying so
        # beats storing an empty credential that fails at call time instead.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{provider_spec.name} returned no key. The authorization code is "
                "single-use, so start the connection again."
            ),
        )

    # Checked like any other credential. A key handed over by the vendor's own
    # login is very likely good, and "very likely" is not something this
    # endpoint is allowed to record as confirmed.
    fields = {provider_spec.fields[0].key: key}
    return await _store(
        user=user,
        provider=provider,
        fields=fields,
        phone_number=None,
        label="Connected with OpenRouter",
        verified_at=_verified_now(await check_credentials(provider_spec, fields)),
    )


async def _store(
    *,
    user: CurrentUser,
    provider: str,
    fields: dict[str, str],
    phone_number: str | None,
    label: str | None,
    verified_at: datetime | None,
) -> ProviderCredentialOut:
    """Encrypt the whole field set as one blob and upsert it."""
    try:
        packed = pack_fields(fields)
    except CredentialsNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    async with database.as_user(user.auth_user_id) as conn:
        row = await credentials_repo.upsert(
            conn,
            org_id=user.org_id,
            created_by=user.id,
            provider=provider,
            label=label,
            fields_encrypted=packed,
            phone_number=phone_number,
            verified_at=verified_at,
        )
    return _row_to_out(row)


def _verified_now(checked: CheckResult) -> datetime | None:
    """A check result as a timestamp to store.

    Only `ok is True` earns one. `ok is None` - no probe, unreachable vendor, a
    key too narrowly scoped to confirm - stores nothing, which is what keeps the
    column an assertion rather than a guess.
    """
    return datetime.now(UTC) if checked.ok is True else None


def _validated_fields(provider_spec: ProviderSpec, submitted: dict[str, str]) -> dict[str, str]:
    """Exactly the fields this provider declares, trimmed, none missing.

    Unknown keys are rejected rather than dropped. Silently discarding one would
    let a caller believe they had configured something they had not - and the
    only sign would be an authentication failure on a live call, long after the
    form said it saved.
    """
    declared = {f.key: f for f in provider_spec.fields}
    unknown = sorted(set(submitted) - set(declared))
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{provider_spec.name} has no field called '{unknown[0]}'. "
                f"It takes: {', '.join(f.label for f in provider_spec.fields)}."
            ),
        )

    cleaned: dict[str, str] = {}
    for key, spec_field in declared.items():
        value = (submitted.get(key) or "").strip()
        if not value:
            if spec_field.required:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{provider_spec.name} needs a {spec_field.label}.",
                )
            continue
        cleaned[key] = value
    return cleaned


@router.put("/providers/{provider}", response_model=ProviderCredentialOut)
async def connect_provider(
    provider: str,
    body: ProviderCredentialIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_WRITE))],
) -> ProviderCredentialOut:
    """Verify one provider's credentials against the vendor, then store them.

    For a carrier or a speech or model vendor, storing is enough to make the
    credential usable on a call; for storage, automation and observability
    vendors nothing reads it yet, and the catalogue's `wired` flag is what the
    interface uses to say so.

    **A credential the vendor rejects is not stored.** It used to be: whatever
    was typed was saved and the card read "Connected", so a mistyped key
    surfaced later as a sync that found nothing or a call that reached silence,
    a long way from the form that caused it. A vendor that cannot be *reached*
    is a different case and does not block the save - an outage at the vendor
    must not stop someone configuring a working account.
    """
    _require_known(provider)
    provider_spec = spec(provider)
    assert provider_spec is not None  # guarded above

    fields = _validated_fields(provider_spec, body.fields)
    checked = await check_credentials(provider_spec, fields)
    if checked.ok is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=checked.detail or f"{provider_spec.name} rejected these credentials.",
        )

    stored = await _store(
        user=user,
        provider=provider,
        fields=fields,
        phone_number=body.phone_number,
        label=body.label,
        verified_at=_verified_now(checked),
    )
    return stored.model_copy(
        update={"verified": checked.ok, "verification_note": checked.detail}
    )


@router.post("/providers/{provider}/verify", response_model=ProviderCredentialOut)
async def verify_provider(
    provider: str,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_WRITE))],
) -> ProviderCredentialOut:
    """Ask the vendor again about a credential that is already stored.

    The one thing checking-on-connect cannot do. A key revoked, rotated, or
    expired at the vendor's end leaves a row that was honestly verified months
    ago and is dead now, and nothing in CallFlow would notice until a call
    failed. It is also the way out of an `ok=None`: a credential saved while the
    vendor was unreachable stays unconfirmed until something asks again.

    A refusal clears `verified_at` rather than deleting the row - the operator
    asked a question, not for their configuration to be thrown away, and a
    credential they can see and update beats one that silently vanished.

    Requires INTEGRATIONS_WRITE despite reading nothing: it spends a request
    against the organisation's own vendor account, and it changes what the
    interface will claim.
    """
    _require_known(provider)
    provider_spec = spec(provider)
    assert provider_spec is not None  # guarded above

    async with database.as_user(user.auth_user_id) as conn:
        row = await credentials_repo.get_for_provider(conn, user.org_id, provider)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not connected.")

    try:
        fields = unpack_fields(row)
    except CredentialsNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    checked = await check_credentials(provider_spec, fields)
    async with database.as_user(user.auth_user_id) as conn:
        updated = await credentials_repo.mark_verified(
            conn, user.org_id, provider, at=_verified_now(checked)
        )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not connected.")

    if checked.ok is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                checked.detail
                or f"{provider_spec.name} no longer accepts the stored credentials."
            ),
        )
    return _row_to_out(updated).model_copy(
        update={"verified": checked.ok, "verification_note": checked.detail}
    )


@router.delete("/providers/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_provider(
    provider: str,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_WRITE))],
) -> None:
    """Forget one provider's credentials entirely.

    A delete, not a soft flag: the row exists to hold a secret, so leaving it
    behind marked inactive would keep a live vendor credential in the database
    that nothing in the product can see or rotate.
    """
    async with database.as_user(user.auth_user_id) as conn:
        deleted = await credentials_repo.remove(conn, user.org_id, provider)
    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not connected.")
