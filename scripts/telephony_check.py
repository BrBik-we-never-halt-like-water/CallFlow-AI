#!/usr/bin/env python
"""Manual verification for the telephony path, against real vendor accounts.

`RUNBOOK_HET_PART_1.md` §10 accepts manual verification for Phase A1's "a real
`CreateSIPParticipant` call placed against a test Twilio number". This is that
verification, written down so it is repeatable rather than a sequence of pasted
snippets nobody can re-run.

Every carrier adapter in this repo was written from published API docs and has
never touched a live account. This script is what closes that gap, one stage at
a time, and each stage is independently useful:

    snapshot   read the number's current Twilio config          (read-only)
    connect    provision it: LiveKit trunks + Twilio trunk      (DESTRUCTIVE)
    call       place a call, with or without the voice agent    (rings a phone)
    teardown   delete what `connect` created at both vendors    (DESTRUCTIVE)

**`snapshot` first, always.** Attaching a number to a SIP trunk repoints its
inbound routing: calls *to* it stop reaching whatever was handling them before.
`snapshot` writes the previous configuration to a JSON file so it can be put
back by hand, and `connect` refuses to run until that file exists.

Nothing here is imported by the application. It reads the same adapters the
product does, so a bug it finds is a real bug and not a difference between this
script and the real path.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env")

from app.core.config import config
from app.domain.entities import Campaign, Contact
from app.domain.goal_rendering import render_goal
from app.domain.result_schemas import build_result_schema
from app.integrations.livekit.client import LiveKitGateway, SipTransport
from app.integrations.telephony import CarrierError, sip_uri
from app.integrations.telephony.twilio import TwilioCarrier
from app.services.campaign_runner import CampaignRunner
from app.services.number_provisioning import _sip_auth

STATE_DIR = REPO_ROOT / ".telephony-check"
SNAPSHOT = STATE_DIR / "twilio-snapshot.json"
CREATED = STATE_DIR / "created.json"

LABEL = "callflow-test"


# --- the test campaign --------------------------------------------------------
# Deliberately defined here rather than added to `domain/campaigns.py`: a built-in
# campaign shows up in every organisation's list, and this is a test fixture, not
# a product decision. Promote it later if it earns its place.

DUBAI_TRIP_PLANNER = Campaign(
    id="dubai-trip-planner",
    name="Dubai trip planner",
    goal_template=(
        "You are a friendly travel consultant from CallFlow calling {name} about "
        "planning a trip to Dubai.\n\n"
        "Open by greeting them by name, say you are calling about their Dubai trip "
        "enquiry, and check this is a good time to talk. If it is not, apologise, "
        "ask when to call back, and end politely.\n\n"
        "You need exactly three things, and nothing else:\n"
        "  1. How many people are travelling\n"
        "  2. Roughly what their budget is for the trip\n"
        "  3. How many days they plan to stay\n\n"
        "Ask them conversationally, one at a time, and acknowledge each answer "
        "before moving to the next. Do not interrogate them and do not ask for "
        "anything beyond those three. If they volunteer more, listen politely but "
        "do not chase it.\n\n"
        "Once you have all three, read them back briefly to confirm you heard "
        "correctly, thank them by name, tell them a consultant will follow up with "
        "Dubai options, and end the call.\n\n"
        "If they sound annoyed or say it is a bad time, do not push. Apologise "
        "once, offer to have a colleague call them, and close warmly.\n\n"
        "Do not promise a price, a WhatsApp message, an email, or a specific "
        "callback time - none of that is yours to commit to. Keep the whole call "
        "under three minutes."
    ),
    outcome_fields={
        "party_size": "number of people travelling",
        "budget": "stated budget for the trip, with currency if given",
        "duration_days": "number of days they plan to stay",
    },
    region="AE",
    language="en-IN",
    escalate_on_negative=True,
)

DUBAI_SCHEMA = build_result_schema(
    {
        "party_size": {"type": "integer", "description": "How many people are travelling."},
        "budget": {"type": "string", "description": "Their stated budget, verbatim."},
        "duration_days": {"type": "integer", "description": "How many days they will stay."},
    },
    ["party_size", "budget", "duration_days"],
)


# --- helpers ------------------------------------------------------------------


def _say(*parts: object) -> None:
    print(*parts, flush=True)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _save(path: Path, data: dict[str, Any]) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _twilio(args: argparse.Namespace) -> TwilioCarrier:
    if not (args.account_sid and args.auth_token):
        raise SystemExit(
            "Twilio credentials are required. Pass --account-sid and --auth-token, "
            "or set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in the environment."
        )
    return TwilioCarrier(account_sid=args.account_sid, auth_token=args.auth_token)


async def _twilio_get(carrier: TwilioCarrier, url: str) -> dict[str, Any]:
    """A raw read against Twilio, for the parts the adapter has no method for.

    The adapter deliberately only knows how to *configure* a number - reading one
    back is this script's concern, not the product's.
    """
    assert carrier._client is not None
    response = await carrier._client.get(url, auth=carrier._auth)
    if response.status_code >= 300:
        raise CarrierError("Twilio", "read the number", f"HTTP {response.status_code}.")
    return response.json()


# --- snapshot -----------------------------------------------------------------


async def cmd_snapshot(args: argparse.Namespace) -> int:
    """Read-only. Records what this number is configured for right now."""
    async with _twilio(args) as carrier:
        listing = await _twilio_get(
            carrier,
            f"https://api.twilio.com/2010-04-01/Accounts/{args.account_sid}"
            f"/IncomingPhoneNumbers.json?PhoneNumber={args.number}",
        )
        numbers = listing.get("incoming_phone_numbers") or []
        if not numbers:
            _say(f"{args.number} is not on this Twilio account.")
            return 1
        number = numbers[0]

        _say(f"  number        {number.get('phone_number')}")
        _say(f"  sid           {number.get('sid')}")
        _say(f"  friendly name {number.get('friendly_name')}")
        _say(f"  voice url     {number.get('voice_url') or '(none)'}")
        _say(f"  voice app sid {number.get('voice_application_sid') or '(none)'}")
        _say(f"  trunk sid     {number.get('trunk_sid') or '(none)'}")
        _say(f"  sms url       {number.get('sms_url') or '(none)'}")

        if number.get("trunk_sid"):
            _say("")
            _say("  !! This number is already attached to a SIP trunk. Connecting it")
            _say("    to CallFlow will move it to a different one.")
        elif number.get("voice_url") or number.get("voice_application_sid"):
            _say("")
            _say("  !! This number currently routes inbound voice somewhere. Attaching")
            _say("    it to a CallFlow trunk replaces that routing.")

        _save(SNAPSHOT, number)
        _say("")
        _say(f"Saved to {SNAPSHOT.relative_to(REPO_ROOT)} - keep it to restore this later.")
    return 0


# --- connect ------------------------------------------------------------------


async def cmd_connect(args: argparse.Namespace) -> int:
    """Provision the number end to end. Creates real objects at both vendors."""
    snapshot = _load(SNAPSHOT)
    if not snapshot:
        _say("Run `snapshot` first - it records what this number is configured for")
        _say("now, which is the only way back if connecting it breaks something.")
        return 1
    if not args.yes:
        _say("This creates a new Twilio SIP trunk and new LiveKit trunks.")
        if args.attach_number:
            _say("--attach-number will ALSO repoint the number's inbound routing away")
            _say("from whatever handles it today. Everything else is additive.")
        else:
            _say("The number keeps its current inbound routing (outbound only).")
        _say("Re-run with --yes to proceed.")
        return 1

    number_sid = snapshot.get("sid")
    if not number_sid:
        _say("The snapshot has no number SID - re-run `snapshot`.")
        return 1

    # The product's own derivation, called directly. An earlier version of this
    # script derived its own lookalike credentials, which meant the first live
    # run tested the script's hex string rather than `_sip_auth`'s - and both
    # happened to be wrong in the same way, so the bug still surfaced. Calling
    # the real function is the only way a pass here means the product passes.
    username, password = _sip_auth(f"telephony-check:{number_sid}")

    created = _load(CREATED)

    if args.attach_number:
        _say("1/4  Twilio: trunk, origination URI, outbound credentials, attach number")
        _say("     this MOVES the number inbound routing away from whatever has it now")
    else:
        _say("1/4  Twilio: trunk, origination URI, outbound credentials (outbound only)")
        _say("     the number keeps its current inbound routing - nothing existing changes")
    async with _twilio(args) as carrier:
        trunk = await carrier.configure_number(
            number_ref=number_sid,
            livekit_sip_host=config.livekit_sip_host,
            label=LABEL,
            auth_username=username,
            auth_password=password,
            attach_number=args.attach_number,
        )
    _say(f"     trunk {trunk.trunk_id} · termination {trunk.termination_domain}")
    created["twilio_trunk_sid"] = trunk.trunk_id
    created["termination_domain"] = trunk.termination_domain
    created.update(trunk.details)
    _save(CREATED, created)

    async with LiveKitGateway(agent_name="") as gateway:
        _say("2/4  LiveKit: inbound trunk")
        inbound = await gateway.create_inbound_trunk(
            name=f"CallFlow {LABEL} inbound",
            numbers=[args.number],
            allowed_addresses=TwilioCarrier.allowed_addresses(),
        )
        created["livekit_inbound_trunk_id"] = inbound
        _save(CREATED, created)
        _say(f"     {inbound}")

        _say("3/4  LiveKit: dispatch rule")
        rule = await gateway.create_dispatch_rule(
            name=f"CallFlow {LABEL}",
            room_prefix=f"call-{LABEL}",
            trunk_ids=[inbound],
        )
        created["livekit_dispatch_rule_id"] = rule
        _save(CREATED, created)
        _say(f"     {rule}")

        _say("4/4  LiveKit: outbound trunk")
        outbound = await gateway.create_outbound_trunk(
            name=f"CallFlow {LABEL} outbound",
            address=trunk.termination_domain or "",
            numbers=[args.number],
            auth_username=username,
            auth_password=password,
            transport=TwilioCarrier.outbound_transport or SipTransport.AUTO,
        )
        created["livekit_outbound_trunk_id"] = outbound
        _save(CREATED, created)
        _say(f"     {outbound}")

    _say("")
    _say(f"Connected. Origination URI Twilio was given: {sip_uri(config.livekit_sip_host)}")
    _say(f"Outbound trunk to dial with:                {outbound}")
    _say(f"State written to {CREATED.relative_to(REPO_ROOT)}")
    return 0


# --- call ---------------------------------------------------------------------


async def cmd_call(args: argparse.Namespace) -> int:
    """Place one real call.

    Without `--agent` this dispatches no worker: it proves the trunk carries
    audio and nothing else, which is the cheapest useful proof and needs no
    speech or model credentials. The callee hears silence and should hang up.
    """
    created = _load(CREATED)
    trunk_id = args.trunk_id or created.get("livekit_outbound_trunk_id")
    if not trunk_id:
        _say("No outbound trunk. Run `connect` first, or pass --trunk-id.")
        return 1

    contact = Contact(name=args.name, phone=args.to, language=args.language)

    if not args.agent:
        _say(f"Placing a bare verification call to {args.to} (no agent, expect silence)")
        async with LiveKitGateway(agent_name="") as gateway:
            info = await gateway.start_call(
                trunk_id=trunk_id,
                phone=args.to,
                room_name=f"verify-{uuid.uuid4().hex[:8]}",
                participant_identity="verify",
                max_call_duration_seconds=60,
            )
        _say(f"Answered. sip_call_id={info['sip_call_id']} room={info['room_name']}")
        return 0

    voice_agent = {
        "stt_provider": args.stt,
        "tts_provider": args.tts,
        "llm_provider": args.llm,
        "llm_model": args.model,
        "voice_id": args.voice,
        "stt_api_key": args.stt_key,
        "tts_api_key": args.tts_key,
        "llm_api_key": args.llm_key,
    }
    missing = [k for k in ("stt_api_key", "tts_api_key", "llm_api_key") if not voice_agent[k]]
    if missing:
        _say(f"Missing credentials for: {', '.join(missing)}.")
        _say("Pass --stt-key/--tts-key/--llm-key (one vendor may cover two of them).")
        return 1

    _say(f"Placing a Dubai trip planner call to {args.to}")
    _say(f"  stt={args.stt}  tts={args.tts}  llm={args.llm} ({args.model})")
    _say("")
    _say("  The voice-runtime worker must already be running, or the callee hears")
    _say("  silence. See this file's header for the command.")
    _say("")

    # The worker refuses a job with no run id, and rightly so - it would have
    # nowhere to report the transcript. Without --run-id this is a throwaway one,
    # so the call happens and the completion callback 404s; pass a real run's id
    # to close the loop against the database.
    run_id = args.run_id or f"chk{uuid.uuid4().hex[:9]}"
    _say(f"  run_id={run_id}" + ("" if args.run_id else "  (throwaway - completion will 404)"))

    runner = CampaignRunner(
        result_schema=DUBAI_SCHEMA,
        trunk_id=trunk_id,
        voice_agent=voice_agent,
        run_id=run_id,
        allowlist=frozenset({args.to}),
        max_calls_per_run=1,
    )
    outcome = await runner.run_one(DUBAI_TRIP_PLANNER, contact)

    _say(f"status       {outcome.status}")
    _say(f"disposition  {outcome.disposition.value}")
    _say(f"reason       {outcome.disposition_reason}")
    if outcome.error:
        _say(f"error        {outcome.error}")
    if outcome.status == "IN_PROGRESS":
        _say("")
        _say("Answered, and the conversation is happening now. The worker reports the")
        _say("transcript to /internal/v1/runs/{run_id}/complete when the call ends -")
        _say("which needs a real run row, so with --run-id unset expect a 404 there")
        _say("and read the transcript from the worker's own log instead.")
    return 0


async def cmd_goal(args: argparse.Namespace) -> int:
    """Print the rendered goal without calling anyone. Read it before dialling."""
    _say(render_goal(DUBAI_TRIP_PLANNER, Contact(name=args.name, phone="+15555550100")))
    return 0


# --- teardown -----------------------------------------------------------------


async def cmd_teardown(args: argparse.Namespace) -> int:
    """Delete what `connect` made. Twilio's own number routing is NOT restored -
    that is a manual step from the snapshot, deliberately, because guessing at
    someone else's previous configuration is worse than telling them to look."""
    created = _load(CREATED)
    if not created:
        _say("Nothing recorded as created.")
        return 0
    if not args.yes:
        _say("Would delete:")
        for key, value in created.items():
            _say(f"  {key}: {value}")
        _say("Re-run with --yes to actually delete them.")
        return 1

    async with LiveKitGateway(agent_name="") as gateway:
        client = gateway._open_client
        for key, delete in (
            ("livekit_dispatch_rule_id", client.sip.delete_sip_dispatch_rule),
            ("livekit_inbound_trunk_id", client.sip.delete_sip_trunk),
            ("livekit_outbound_trunk_id", client.sip.delete_sip_trunk),
        ):
            value = created.get(key)
            if not value:
                continue
            try:
                await delete(value)
                _say(f"deleted {key} {value}")
            except Exception as exc:  # noqa: BLE001 - best effort cleanup
                _say(f"could not delete {key} {value}: {type(exc).__name__}")

    snapshot = _load(SNAPSHOT)
    _say("")
    _say("Twilio: the trunk and the number's attachment are NOT undone here.")
    _say(f"Restore it in the console from {SNAPSHOT.relative_to(REPO_ROOT)}:")
    _say(f"  voice url     {snapshot.get('voice_url') or '(none)'}")
    _say(f"  voice app sid {snapshot.get('voice_application_sid') or '(none)'}")
    _say(f"  trunk sid     {snapshot.get('trunk_sid') or '(none)'}")
    return 0


# --- cli ----------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--account-sid", default=None)
    parser.add_argument("--auth-token", default=None)
    parser.add_argument("--number", default=None, help="The Twilio number, E.164")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("snapshot", help="read the number's current Twilio config")

    connect = sub.add_parser("connect", help="provision the number (DESTRUCTIVE)")
    connect.add_argument("--yes", action="store_true")
    # Default OFF: attaching the number is the one step that changes behaviour
    # somebody else may be relying on. Opt in to it, never default into it.
    connect.add_argument(
        "--attach-number",
        action="store_true",
        help="also route inbound to LiveKit (destructive - replaces existing routing)",
    )

    call = sub.add_parser("call", help="place a real call")
    call.add_argument("--to", required=True, help="Who to ring, E.164")
    call.add_argument("--name", default="there", help="What the agent calls them")
    call.add_argument("--agent", action="store_true", help="Run the Dubai planner")
    call.add_argument("--trunk-id", default=None)
    call.add_argument("--run-id", default=None)
    call.add_argument("--stt", default="sarvam")
    call.add_argument("--tts", default="sarvam")
    call.add_argument("--llm", default="openrouter")
    call.add_argument("--model", default="openai/gpt-4o-mini")
    # Left unset so Sarvam picks a speaker its current model supports.
    call.add_argument("--voice", default=None, help="Vendor voice id, if you want a specific one")
    call.add_argument("--language", default="en-IN", help="Locale code the vendors expect")
    call.add_argument("--stt-key", default=None)
    call.add_argument("--tts-key", default=None)
    call.add_argument("--llm-key", default=None)

    goal = sub.add_parser("goal", help="print the rendered goal, call nobody")
    goal.add_argument("--name", default="there")

    teardown = sub.add_parser("teardown", help="delete what connect made (DESTRUCTIVE)")
    teardown.add_argument("--yes", action="store_true")

    args = parser.parse_args()

    import os

    args.account_sid = args.account_sid or os.getenv("TWILIO_ACCOUNT_SID", "")
    args.auth_token = args.auth_token or os.getenv("TWILIO_AUTH_TOKEN", "")
    args.number = args.number or os.getenv("TWILIO_NUMBER", "")

    handlers = {
        "snapshot": cmd_snapshot,
        "connect": cmd_connect,
        "call": cmd_call,
        "goal": cmd_goal,
        "teardown": cmd_teardown,
    }
    return asyncio.run(handlers[args.command](args))


if __name__ == "__main__":
    raise SystemExit(main())
