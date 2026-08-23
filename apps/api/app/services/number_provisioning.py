"""Connecting an organisation's own number to a voice agent.

Four things have to line up before a call can be placed, across two vendors:

    1. a LiveKit inbound trunk        (so calls *to* the number reach LiveKit)
    2. a LiveKit dispatch rule        (so each caller gets their own room)
    3. the carrier's own config       (origination URI + outbound credentials)
    4. a LiveKit outbound trunk       (so CallFlow can dial *out* through it)

That order is a dependency chain, not a preference: step 4 needs the address
the carrier hands back in step 3, and step 3 needs LiveKit's SIP host, which is
a property of the project rather than of any trunk.

**Nothing here is transactional.** LiveKit and the carrier are separate systems
with no shared commit, so a failure at step 3 leaves steps 1 and 2 really
created. The row is the ledger: each step records what it made the moment it
makes it, and a retry of the *same* attempt reads those ids back and skips
whatever is already done. Re-running step 1 blindly would leave an orphaned
LiveKit trunk that nobody ever cleans up - which is the specific failure ADR-4
called out and the reason `telephony_provisioning` exists at all.

Retrying the *same* attempt resumes. "Try again" in the UI is a **new** attempt
with a new key, which starts from scratch and leaves the failed row's
`last_error` intact as the record of what went wrong.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

import asyncpg

from app.core.config import config
from app.database.repositories import telephony_numbers as numbers_repo
from app.database.repositories import telephony_provisioning as provisioning_repo
from app.domain.numbers import InvalidTransition, NumberStatus
from app.domain.provisioning import ProvisioningStatus
from app.integrations.livekit.client import (
    LiveKitGateway,
    SipTransport,
    explain_error,
)
from app.integrations.telephony import CarrierError, CarrierTrunk
from app.integrations.telephony.plivo import PlivoCarrier
from app.integrations.telephony.telnyx import TelnyxCarrier
from app.integrations.telephony.twilio import TwilioCarrier
from app.integrations.telephony.vonage import VonageCarrier

log = logging.getLogger("app.services.number_provisioning")

GatewayFactory = Callable[[], LiveKitGateway]
CarrierFactory = Callable[..., Any]

CARRIERS: dict[str, CarrierFactory] = {
    "twilio": TwilioCarrier,
    "plivo": PlivoCarrier,
    "telnyx": TelnyxCarrier,
    "vonage": VonageCarrier,
}


class ProvisioningRefused(Exception):
    """The attempt cannot proceed, for a reason retrying will not change."""


def _sip_auth(idempotency_key: str) -> tuple[str, str]:
    """The username and password LiveKit and the carrier must both agree on.

    Derived from the attempt's own key rather than randomly generated, so a
    resumed attempt produces the *same* credentials without needing a column to
    remember them - regenerating would leave LiveKit dialling with a password
    the carrier no longer expects, and the failure would show up only as
    silently rejected outbound calls.

    Keyed on `provider_credentials_key`, the server-held secret whose entire
    job is protecting provider credentials, so the derived password is not
    guessable from the attempt id alone.

    Refuses rather than falling back to a constant when that key is unset. A
    fallback would make every deployment that forgot to set it derive the same
    password from the same attempt id - which is a guessable SIP credential on
    a trunk that can place real calls, and it would work, so nothing would ever
    reveal the problem (CLAUDE.md non-negotiable #2: fail closed).

    **The `Cf1` prefix is not decoration.** Twilio rejects a SIP credential
    password that is not at least 12 characters with an uppercase letter, a
    lowercase letter and a digit (error 21240). A hex digest is `[0-9a-f]` and
    so has no uppercase character at all, which failed *every* Twilio
    provisioning attempt at the store-credentials step - found the first time
    this ran against a real account, because a stub has no password policy to
    violate. The prefix guarantees one of each class by construction rather
    than hoping the digest happens to contain them, and the whole password
    stays alphanumeric so no carrier has to escape it.

    The username dropped its hyphen in the same change. That one is
    precautionary rather than observed - Twilio documents SIP credential
    usernames as alphanumeric, and finding out the hard way costs another
    half-provisioned trunk on someone's real account.
    """
    if not config.provider_credentials_key:
        raise ProvisioningRefused(
            "PROVIDER_CREDENTIALS_KEY is not set, and it is what makes this trunk's SIP "
            "password unguessable. Generate one before connecting a number."
        )
    digest = hmac.new(
        config.provider_credentials_key.encode(),
        idempotency_key.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"cf{digest[:14]}", f"Cf1{digest[16:44]}"


async def _mirror_to_number(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    provider: str,
    phone_e164: str,
    target: NumberStatus,
    attempt: asyncpg.Record | None = None,
    error: str | None = None,
    clear_error: bool = False,
) -> None:
    """Carry an attempt's outcome onto the number row the dial gate reads.

    Two tables record this workflow and they answer different questions.
    `telephony_provisioning` is the ledger of one attempt - what it created, in
    what order, and what went wrong - and it is keyed by voice agent, so a
    number connected to two agents has two rows. `telephony_numbers` is the
    number itself, and `is_diallable(status) and livekit_outbound_trunk_id` on
    *that* row is what `GET /telephony/numbers` reports and what a run dials
    from. Without this step the ledger says verified while the number stays
    `discovered` with no trunk, so every number the product provisions remains
    undiallable and the run composer keeps telling people to connect a carrier
    they already connected.

    Never raises. Provisioning has really configured LiveKit and the carrier by
    the time this runs; a number row that cannot be found or moved is worth a
    log line, not an exception that would roll back the ledger of what exists.
    """
    number = await numbers_repo.by_e164(
        conn, org_id=org_id, provider=provider, phone_e164=phone_e164
    )
    if number is None:
        # Provisioning accepts any E.164 the caller names, so a number that was
        # never discovered by a sync has no row to mirror onto.
        log.info("no %s number row for the provisioned line; nothing to mirror", provider)
        return

    if attempt is not None:
        await numbers_repo.record_livekit_ids(
            conn,
            org_id=org_id,
            number_id=number["id"],
            inbound_trunk_id=attempt["livekit_inbound_trunk_id"],
            outbound_trunk_id=attempt["livekit_outbound_trunk_id"],
            dispatch_rule_id=attempt["livekit_dispatch_rule_id"],
            carrier_termination_domain=attempt["carrier_termination_domain"],
        )

    # Before the short-circuit below on purpose: a part-way failure leaves the
    # number on `provisioning`, which is where it already was, so anything after
    # that early return would never run for the very case that needs it.
    if error is not None or clear_error:
        await numbers_repo.record_error(
            conn, org_id=org_id, number_id=number["id"], message=error
        )

    current = NumberStatus(number["status"])
    if current is target:
        return
    if current is NumberStatus.DISABLED:
        # `disabled` is an operator's deliberate act, and `disabled -> verified`
        # is a legal move - it is how re-enabling works - so the transition
        # table will not stop this. Provisioning must not take that decision on
        # someone's behalf: the trunk ids above are recorded, and re-enabling
        # stays a human action.
        log.info("number is disabled; recorded its trunks but left it out of service")
        return
    try:
        await numbers_repo.set_status(
            conn, org_id=org_id, number_id=number["id"], target=target
        )
    except InvalidTransition:
        # A number reached this state by another route - already disabled, or
        # already verified through a different agent's attempt. The trunk ids
        # above are still written, and forcing the status would be the one way
        # to make a deliberate `disabled` dial again.
        log.info(
            "left number status at %s; %s is not a legal move from there",
            current.value,
            target.value,
        )


async def connect_number(
    conn: asyncpg.Connection,
    *,
    voice_agent_id: UUID,
    org_id: UUID,
    idempotency_key: str,
    provider: str,
    credentials: dict[str, str],
    phone_number: str,
    number_ref: str | None = None,
    label: str,
    livekit_sip_host: str | None = None,
    gateway_factory: GatewayFactory | None = None,
    carrier_factory: CarrierFactory | None = None,
    attach_number: bool = False,
) -> asyncpg.Record:
    """Run the workflow, resuming whatever this attempt already finished.

    Returns the attempt row, **whether or not it worked**. `status` and
    `last_error` on that row are the result: `verified` means done, anything
    else with a `last_error` means a step failed and a retry with this same key
    will resume from there. Failure is reported rather than raised so the
    ledger of what was really created survives the caller's transaction - see
    the error handler below.

    Raises only for a refusal that happens *before* any attempt row exists, and
    so has nothing to record.

    **`attach_number` defaults to False, and that is deliberate.** Placing calls
    needs only the outbound half; claiming a number's inbound routing redirects
    whatever already answers it - an IVR, a support line, a person - and is not
    something to do as a side effect of "make this diallable". Everything the
    default creates is new, so a number keeps answering where it always did and
    can still be dialled out from. An organisation that wants CallFlow to answer
    the number too asks for it explicitly.
    """
    carrier_cls = carrier_factory or CARRIERS.get(provider)
    if carrier_cls is None:
        raise ProvisioningRefused(
            f"'{provider}' is not a carrier CallFlow can configure. "
            f"Supported: {', '.join(sorted(CARRIERS))}."
        )

    sip_host = livekit_sip_host or config.livekit_sip_host
    if not sip_host:
        raise ProvisioningRefused(
            "LIVEKIT_SIP_HOST is not set, so the carrier cannot be told where to "
            "send calls. Copy it from the LiveKit project's SIP settings."
        )

    row, created = await provisioning_repo.start_attempt(
        conn,
        voice_agent_id=voice_agent_id,
        org_id=org_id,
        idempotency_key=idempotency_key,
    )
    status = ProvisioningStatus(row["status"])

    if status is ProvisioningStatus.VERIFIED:
        # Already done. Returning the row rather than raising means a
        # double-submitted request is a no-op, not an error the UI has to
        # explain away.
        return row
    if status is ProvisioningStatus.FAILED:
        # Terminal: this attempt was superseded by a later one, so resuming it
        # would configure against objects a newer attempt has moved past.
        raise ProvisioningRefused(
            "This attempt was superseded and cannot be resumed. "
            "Start a new one - the old attempt is kept as the record of what went wrong."
        )

    if created:
        # A fresh attempt supersedes whatever came before it, so an agent does
        # not accumulate rows that look live forever. Their `last_error` is
        # left alone - it is the record of what actually went wrong.
        superseded = await provisioning_repo.supersede_unfinished(
            conn, voice_agent_id, except_id=row["id"]
        )
        if superseded:
            log.info("superseded %d unfinished attempt(s) for agent %s", superseded, voice_agent_id)
    else:
        log.info("resuming provisioning attempt %s", row["id"])

    if status is ProvisioningStatus.PENDING:
        row = _require(
            await provisioning_repo.set_status(conn, row["id"], ProvisioningStatus.PROVISIONING),
            row["id"],
        )
        await _mirror_to_number(
            conn,
            org_id=org_id,
            provider=provider,
            phone_e164=phone_number,
            target=NumberStatus.PROVISIONING,
        )

    username, password = _sip_auth(idempotency_key)

    try:
        row = await _run_steps(
            conn,
            row=row,
            carrier_cls=carrier_cls,
            credentials=credentials,
            phone_number=phone_number,
            number_ref=number_ref or phone_number,
            label=label,
            sip_host=sip_host,
            username=username,
            password=password,
            gateway_factory=gateway_factory or LiveKitGateway,
            attach_number=attach_number,
        )
    except Exception as exc:
        # Recorded, but the attempt stays `provisioning` rather than becoming
        # terminal. A step that failed part-way has left real LiveKit objects
        # behind, and the only safe way forward is to resume this attempt and
        # skip them - marking it failed here would make that illegal and the
        # next attempt would orphan them (ADR-4).
        #
        # A carrier's own wording is kept because it is the only part that says
        # why; anything else is reported by type, since a raw exception string
        # can carry a credential or a hostname.
        # Three tiers, because "what do I do about this" differs for each.
        #
        # A carrier's or a refusal's own wording is already operator-facing. A
        # media-server error is not - but it carries a transport code that says
        # exactly which of authentication, permission, SIP-not-enabled or a bad
        # argument went wrong, and `explain_error` turns that into the sentence.
        # Only a genuinely unknown exception falls back to its type name.
        #
        # This tier used to be missing, and the cost was concrete: LiveKit's
        # `ServerError` *is* `TwirpError` (the SDK renamed the class and kept the
        # old name as an alias), so every media-server rejection landed in the
        # last branch and reported "(ServerError)" - a string that names the
        # vendor's class and tells an operator nothing. Three provisioning
        # attempts failed on dev with no trunk ids recorded at all, meaning the
        # very first call was refused, and the recorded error could not say why.
        if isinstance(exc, CarrierError | ProvisioningRefused):
            detail = str(exc)
        else:
            detail = explain_error(exc) or (
                f"An unexpected error stopped provisioning ({type(exc).__name__}). "
                "The steps already completed are recorded and a retry will resume from there."
            )
        log.exception("provisioning attempt %s stopped", row["id"])
        # The number keeps `provisioning`, matching the attempt: a part-way
        # failure is resumable, and the ids the successful steps recorded are
        # mirrored so a resume does not rebuild what already exists.
        await _mirror_to_number(
            conn,
            org_id=org_id,
            provider=provider,
            phone_e164=phone_number,
            target=NumberStatus.PROVISIONING,
            attempt=row,
            # The same reason the attempt records. Without this the number row
            # kept whatever it collected first and the real failure lived only on
            # the attempt, which nothing in the interface reads.
            error=detail,
        )
        # Returned, not re-raised, and that is the whole point. `as_user()`
        # wraps a request in a single transaction, so propagating from here
        # would roll back this note *and* every trunk id the steps that did
        # succeed recorded - leaving a row claiming nothing exists while real
        # LiveKit trunks do, so the retry orphans a second pair. The row is the
        # ledger, and `last_error` beside a non-verified status is how the
        # caller learns this failed.
        return _require(await provisioning_repo.record_error(conn, row["id"], detail), row["id"])

    verified = _require(
        await provisioning_repo.set_status(conn, row["id"], ProvisioningStatus.VERIFIED),
        row["id"],
    )
    await _mirror_to_number(
        conn,
        org_id=org_id,
        provider=provider,
        phone_e164=phone_number,
        target=NumberStatus.VERIFIED,
        attempt=verified,
        # The number is diallable, so whatever used to be wrong with it is not
        # wrong any more. Leaving the last reason behind would put a red line
        # beside a working number.
        clear_error=True,
    )
    return verified


async def _run_steps(
    conn: asyncpg.Connection,
    *,
    row: asyncpg.Record,
    carrier_cls: CarrierFactory,
    credentials: dict[str, str],
    phone_number: str,
    number_ref: str,
    label: str,
    sip_host: str,
    username: str,
    password: str,
    gateway_factory: GatewayFactory,
    # Outbound-only unless a caller asks otherwise, matching
    # `connect_number`'s own default - claiming a number's inbound routing
    # redirects whatever already answers it.
    attach_number: bool = False,
) -> asyncpg.Record:
    """Each step is skipped when the row already records its result."""
    attempt_id = row["id"]

    async with gateway_factory() as gateway:
        if not row["livekit_inbound_trunk_id"]:
            trunk_id = await gateway.create_inbound_trunk(
                name=f"CallFlow {label} inbound",
                numbers=[phone_number],
                # Twilio cannot authenticate inbound at all, so its adapter
                # supplies signalling ranges to restrict the trunk to. Plivo's
                # is deliberately empty - it authenticates instead.
                allowed_addresses=carrier_cls.allowed_addresses(),
            )
            row = _require(
                await provisioning_repo.record_livekit_ids(
                    conn, attempt_id, inbound_trunk_id=trunk_id
                ),
                attempt_id,
            )

        if not row["livekit_dispatch_rule_id"]:
            rule_id = await gateway.create_dispatch_rule(
                name=f"CallFlow {label}",
                room_prefix=f"call-{label}",
                trunk_ids=[row["livekit_inbound_trunk_id"]],
            )
            row = _require(
                await provisioning_repo.record_livekit_ids(
                    conn, attempt_id, dispatch_rule_id=rule_id
                ),
                attempt_id,
            )

        # The carrier comes before the outbound trunk because it is what hands
        # back the address that trunk dials.
        if not row["carrier_termination_domain"]:
            configured = await _configure_carrier(
                carrier_cls,
                credentials=credentials,
                number_ref=number_ref,
                label=label,
                sip_host=sip_host,
                username=username,
                password=password,
                attach_number=attach_number,
            )
            row = _require(
                await provisioning_repo.record_livekit_ids(
                    conn, attempt_id, carrier_termination_domain=configured.termination_domain
                ),
                attempt_id,
            )

        if not row["livekit_outbound_trunk_id"]:
            outbound_id = await gateway.create_outbound_trunk(
                name=f"CallFlow {label} outbound",
                address=row["carrier_termination_domain"],
                numbers=[phone_number],
                auth_username=username,
                auth_password=password,
                # Read off the carrier, not the row: a resumed attempt reaches
                # here with `configured` long out of scope, and defaulting to
                # `auto` is exactly what Plivo rejects.
                transport=carrier_cls.outbound_transport or SipTransport.AUTO,
            )
            row = _require(
                await provisioning_repo.record_livekit_ids(
                    conn, attempt_id, outbound_trunk_id=outbound_id
                ),
                attempt_id,
            )

    return row


async def _configure_carrier(
    carrier_cls: CarrierFactory,
    *,
    credentials: dict[str, str],
    number_ref: str,
    label: str,
    sip_host: str,
    username: str,
    password: str,
    attach_number: bool,
) -> CarrierTrunk:
    """One call, whichever carrier this is.

    Twilio addresses a number by SID and Plivo by the number itself - a real
    difference in their APIs, which the adapters absorb behind `number_ref`
    rather than making every caller branch on the provider.
    """
    async with carrier_cls(**credentials) as carrier:
        return await carrier.configure_number(
            number_ref=number_ref,
            livekit_sip_host=sip_host,
            label=label,
            auth_username=username,
            auth_password=password,
            attach_number=attach_number,
        )


def _require(row: asyncpg.Record | None, attempt_id: Any) -> asyncpg.Record:
    """A step recorded its result against a row that is no longer visible.

    Under RLS that means the attempt is not this caller's, which is a bug
    rather than a condition to recover from - and continuing would dial using
    another organisation's trunk.
    """
    if row is None:
        raise ProvisioningRefused(
            f"Provisioning attempt {attempt_id} is no longer readable - it may belong "
            "to another organisation. Nothing further was created."
        )
    return row


__all__ = ["CARRIERS", "ProvisioningRefused", "connect_number"]
