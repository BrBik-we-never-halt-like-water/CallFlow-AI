"""The entrypoint: join a room, hold the conversation, report what happened.

One job = one phone call. `apps/api` dispatches this worker into a room just
before the SIP participant is created, so by the time the contact says "hello"
the agent is already there.

Everything this worker knows about the call arrives as job metadata - the
rendered goal, which providers to run on, and the identifiers the completion
callback needs. It reads no database and holds no organisation's credentials of
its own.

Kept deliberately thin. The two pieces with real logic - choosing plugins
(`pipeline.py`) and delivering the result (`reporter.py`) - are separate and
tested on their own; what remains here is the LiveKit lifecycle, which cannot
be tested without a live room and so should contain as little as possible.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import config
from app.pipeline import AgentSpec, build_pipeline
from app.reporter import ReportFailed, report_completion

log = logging.getLogger("voice-runtime.worker")

# A conversation that produced no turns at all did not happen, whatever the
# carrier reported - reporting COMPLETED for it would show an operator a call
# that connected and said nothing.
_ANSWERED = "COMPLETED"
_NO_ANSWER = "NO_ANSWER"
_FAILED = "FAILED"


def parse_job_metadata(raw: str | None) -> dict[str, Any]:
    """Job metadata, or an empty mapping if it is missing or malformed.

    Never raises: a worker that dies on bad metadata leaves a live call with
    nobody on the line. The caller checks what it needs and refuses the job
    with a reason instead.
    """
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        log.error("job metadata is not valid JSON - refusing the job")
        return {}
    return parsed if isinstance(parsed, dict) else {}


def transcript_from_history(history: Any) -> str:
    """Flatten a session's chat history into the stored transcript.

    Plain "Role: text" lines rather than JSON: this is read by a person in the
    dashboard, and every consumer downstream already treats it as prose.
    """
    lines: list[str] = []
    for item in getattr(history, "items", None) or []:
        role = str(getattr(item, "role", "") or "")
        if role not in {"user", "assistant"}:
            continue
        content = getattr(item, "text_content", None) or ""
        if not content:
            continue
        speaker = "Contact" if role == "user" else "Agent"
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


def completion_payload(
    metadata: dict[str, Any], *, transcript: str, duration_seconds: int, error: str | None = None
) -> dict[str, Any]:
    """The body `/internal/v1/runs/{run_id}/complete` expects.

    `contact_name`/`phone_masked` are echoed straight back from metadata
    because the API keys the outcome row on them - inventing either here would
    create a second row rather than resolving the in-flight one.
    """
    if error is not None:
        status = _FAILED
    elif transcript:
        status = _ANSWERED
    else:
        status = _NO_ANSWER

    return {
        "contact_name": metadata.get("contact_name", ""),
        "phone_masked": metadata.get("phone_masked", ""),
        "status": status,
        "transcript": transcript or None,
        "duration_seconds": duration_seconds,
        "error": error,
        # Structured extraction against the campaign's own result_schema is
        # Part 2's (RUNBOOK_ARBAAZ_PART_2.md P2-T2). Sending an empty object
        # rather than a guess keeps triage honest: it falls through to the
        # status-based buckets instead of acting on invented fields.
        "extracted": {},
    }


async def run_call(ctx: Any) -> None:
    """One call, start to finish.

    Structured so the completion report happens in `finally`: a crash mid-call
    still tells the operator what was said up to that point, rather than
    leaving the row in flight forever.
    """
    from livekit.agents import Agent, AgentSession  # imported late: heavy, and unused in tests

    metadata = parse_job_metadata(getattr(ctx.job, "metadata", None))
    run_id = metadata.get("run_id")
    if not run_id:
        log.error("job has no run_id - nothing could be reported, refusing the call")
        return

    goal = metadata.get("goal") or "Have a brief, polite conversation and end the call."
    spec = AgentSpec.from_metadata(metadata)

    transcript = ""
    error: str | None = None
    started = ctx.job.id if hasattr(ctx.job, "id") else ""
    log.info("starting call for run %s (job %s)", run_id, started)

    session: Any = None
    try:
        pipeline = build_pipeline(spec)
        session = AgentSession(stt=pipeline.stt, tts=pipeline.tts, llm=pipeline.llm)
        await session.start(agent=Agent(instructions=goal), room=ctx.room)
        await ctx.connect()
        await session.aclose()
    except Exception as exc:
        # The reason is logged in full but only the exception *type* is
        # reported: a vendor message can carry an API key or the dialled
        # number, and this string reaches a user-facing field.
        log.exception("call for run %s failed", run_id)
        error = type(exc).__name__
    finally:
        if session is not None:
            transcript = transcript_from_history(getattr(session, "history", None))

        payload = completion_payload(
            metadata,
            transcript=transcript,
            duration_seconds=0,
            error=error,
        )
        try:
            await report_completion(str(run_id), payload)
        except ReportFailed:
            # Nothing left to escalate to from here. Logged loudly so the row
            # stuck in flight can be traced back to this call.
            log.exception("run %s: the call happened but its result was not recorded", run_id)


def main() -> None:
    """Start the worker, or refuse to start and say exactly what is missing.

    The configuration check runs *before* importing `livekit.agents`, on
    purpose: an operator who has not set up their `.env` should be told which
    variables to set, not handed a ModuleNotFoundError for a package that is
    beside the point.
    """
    missing = config.missing()
    if missing:
        raise SystemExit(
            "The voice runtime is not configured. Set: "
            + ", ".join(missing)
            + " (see .env.example)."
        )

    from livekit.agents import WorkerOptions, cli

    cli.run_app(WorkerOptions(entrypoint_fnc=run_call, agent_name=config.agent_name))


if __name__ == "__main__":
    main()
