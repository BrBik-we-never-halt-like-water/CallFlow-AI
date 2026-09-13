#!/usr/bin/env python3
"""H1 — prove a carrier number can ring an Indian mobile.

This is not the product path. The product dials through LiveKit
(`CreateSIPParticipant`, H6) once a trunk exists. This script talks to Twilio
or Plivo directly, from a laptop, so KYC / billing / the number itself can be
proven on day one without LiveKit, a VM, or the API running.

    python scripts/probe-dial.py --to +919876543210

Reads, in order: flags, then the environment. Never prints the callee in full
after the request is built — only a masked form — so a log of this script is
safe to paste.

Twilio (preferred for this probe): inline TwiML, no public URL required.

    TWILIO_ACCOUNT_SID  TWILIO_AUTH_TOKEN  TWILIO_NUMBER

Plivo: their Call API needs an answer URL that returns Speak XML. Host the
file in this repo (`scripts/probe-dial-answer.xml`) on any HTTPS origin and
pass it as --answer-url, or set PLIVO_ANSWER_URL.

    PLIVO_AUTH_ID  PLIVO_AUTH_TOKEN  PLIVO_NUMBER  PLIVO_ANSWER_URL
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from typing import Mapping


def _mask(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit() or c == "+")
    if len(digits) < 6:
        return "***"
    return f"{digits[:4]}…{digits[-2:]}"


def _basic(user: str, password: str) -> str:
    token = b64encode(f"{user}:{password}".encode("ascii")).decode("ascii")
    return f"Basic {token}"


def _post(
    url: str,
    *,
    auth: str,
    fields: Mapping[str, str] | None = None,
    json_body: Mapping[str, str] | None = None,
) -> tuple[int, dict[str, object]]:
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        content_type = "application/json"
    else:
        data = urllib.parse.urlencode(fields or {}).encode("utf-8")
        content_type = "application/x-www-form-urlencoded"
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": auth,
            "Content-Type": content_type,
        },
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, context=context, timeout=30) as response:
            body = response.read().decode("utf-8")
            parsed: dict[str, object] = json.loads(body) if body else {}
            return response.status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw[:500]}
        return exc.code, parsed


def twilio_call(*, sid: str, token: str, from_number: str, to: str) -> int:
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json"
    twiml = (
        "<Response><Say voice='Polly.Aditi' language='en-IN'>"
        "This is a CallFlow probe. You can hang up."
        "</Say><Pause length='2'/><Hangup/></Response>"
    )
    status, body = _post(
        url,
        auth=_basic(sid, token),
        fields={"To": to, "From": from_number, "Twiml": twiml},
    )
    call_sid = body.get("sid") or body.get("code") or "(none)"
    if status >= 300:
        message = body.get("message") or body
        print(f"Twilio refused the call ({status}): {message}", file=sys.stderr)
        return 1
    print(f"Twilio accepted. Call SID {call_sid}. Rang {_mask(to)} from {_mask(from_number)}.")
    print("The handset should ring within a few seconds. Hang up when it does — that is the proof.")
    return 0


def plivo_call(
    *,
    auth_id: str,
    token: str,
    from_number: str,
    to: str,
    answer_url: str,
) -> int:
    url = f"https://api.plivo.com/v1/Account/{auth_id}/Call/"
    status, body = _post(
        url,
        auth=_basic(auth_id, token),
        json_body={
            "from": from_number,
            "to": to,
            "answer_url": answer_url,
            "answer_method": "GET",
        },
    )
    request_uuid = body.get("request_uuid") or body.get("error") or "(none)"
    if status >= 300:
        print(f"Plivo refused the call ({status}): {body}", file=sys.stderr)
        return 1
    print(f"Plivo accepted. request_uuid {request_uuid}. Rang {_mask(to)} from {_mask(from_number)}.")
    print("The handset should ring within a few seconds. Hang up when it does — that is the proof.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--to", required=True, help="Teammate's Indian mobile, E.164 (+91…)")
    parser.add_argument("--provider", choices=("twilio", "plivo", "auto"), default="auto")
    parser.add_argument("--from", dest="from_number", default="", help="Override the env number")
    parser.add_argument("--answer-url", default="", help="Plivo only: HTTPS URL that returns Speak XML")
    args = parser.parse_args()

    to = args.to.strip()
    if not to.startswith("+91") or len("".join(c for c in to if c.isdigit())) < 12:
        print("Pass an Indian E.164 number: --to +91XXXXXXXXXX", file=sys.stderr)
        return 1

    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_number = args.from_number or os.getenv("TWILIO_NUMBER", "")
    plivo_id = os.getenv("PLIVO_AUTH_ID", "")
    plivo_token = os.getenv("PLIVO_AUTH_TOKEN", "")
    plivo_number = args.from_number or os.getenv("PLIVO_NUMBER", "")
    answer_url = args.answer_url or os.getenv("PLIVO_ANSWER_URL", "")

    provider = args.provider
    if provider == "auto":
        if twilio_sid and twilio_token and twilio_number:
            provider = "twilio"
        elif plivo_id and plivo_token and plivo_number:
            provider = "plivo"
        else:
            print(
                "No carrier credentials in the environment. Set Twilio "
                "(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_NUMBER) or Plivo "
                "(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN, PLIVO_NUMBER) and retry.",
                file=sys.stderr,
            )
            return 1

    if provider == "twilio":
        missing = [
            name
            for name, value in (
                ("TWILIO_ACCOUNT_SID", twilio_sid),
                ("TWILIO_AUTH_TOKEN", twilio_token),
                ("TWILIO_NUMBER", twilio_number),
            )
            if not value
        ]
        if missing:
            print(f"Twilio probe is missing {', '.join(missing)}.", file=sys.stderr)
            return 1
        return twilio_call(sid=twilio_sid, token=twilio_token, from_number=twilio_number, to=to)

    missing = [
        name
        for name, value in (
            ("PLIVO_AUTH_ID", plivo_id),
            ("PLIVO_AUTH_TOKEN", plivo_token),
            ("PLIVO_NUMBER", plivo_number),
            ("PLIVO_ANSWER_URL / --answer-url", answer_url),
        )
        if not value
    ]
    if missing:
        print(f"Plivo probe is missing {', '.join(missing)}.", file=sys.stderr)
        print("Host scripts/probe-dial-answer.xml on HTTPS and pass that URL.", file=sys.stderr)
        return 1
    return plivo_call(
        auth_id=plivo_id,
        token=plivo_token,
        from_number=plivo_number,
        to=to,
        answer_url=answer_url,
    )


if __name__ == "__main__":
    raise SystemExit(main())
