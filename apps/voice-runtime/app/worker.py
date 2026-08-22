"""The entrypoint: join a room, hold the conversation, report what happened.

One job = one phone call. `apps/api` dispatches this worker into a room just
before the SIP participant is created, so by the time the contact says "hello"
the agent is already there.

Everything this worker knows about the call arrives as job metadata - the
rendered goal, which providers to run on, and the identifiers the completion
callback needs. It reads no database and holds no organisation's credentials of
its own.

Kept deliberately thin. The three pieces with real logic - choosing plugins
(`pipeline.py`), gathering fields (`collection.py`), and delivering the result
(`reporter.py`) - are separate and tested on their own.

What remains is the LiveKit lifecycle. `wait_for_call_end()` is written against
a duck-typed context rather than `JobContext` precisely so it *can* be tested
without a live room: it is the one piece of ordering that decides whether a call
is held or dropped, and the first version of this file got it wrong in a way
only a live call would have shown.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.collection import Collector, fields_from_metadata, recover_missing
from app.config import config
from app.pipeline import PLUGIN_MODULES, AgentSpec, build_pipeline
from app.reporter import ReportFailed, report_completion

log = logging.getLogger("voice-runtime.worker")

# A conversation that produced no turns at all did not happen, whatever the
# carrier reported - reporting COMPLETED for it would show an operator a call
# that connected and said nothing.
_ANSWERED = "COMPLETED"
_NO_ANSWER = "NO_ANSWER"
_FAILED = "FAILED"

# The agent's own instructions already say how to open; this only tells it that
# now is the moment. Spelling the greeting out here would override whatever the
# agent's prompt asked for.
_OPENING = "The contact has just answered. Open the call as your instructions describe."


#: Voice activity detection, needed by every STT pipeline regardless of vendor -
#: without it nothing knows when the contact stopped talking, so the agent never
#: takes a turn. Not in `PLUGIN_MODULES` because no provider selects it.
_VAD_MODULE = "silero"

#: How often a live call is checked for the agent having asked to hang up.
#: Short enough that ending a call feels immediate, long enough that a
#: half-hour call is not thousands of wakeups.
_HANGUP_POLL_SECONDS = 1.0


def register_plugins() -> list[str]:
    """Import every vendor plugin this deployment has, on the main thread.

    `livekit-agents` raises "Plugins must be registered on the main thread" if a
    plugin is first imported anywhere else, and it runs each job in a worker
    thread. So importing lazily inside a factory - which is where the plugin
    choice actually lives - kills the job at launch with `DuplexClosed`, before
    the contact hears a thing. That is what the first live call did.

    Doing it here keeps the property the lazy import was for: a deployment
    installs only the vendors its organisations use, and anything absent is
    skipped rather than being a startup error.
    """
    registered: list[str] = []
    for module in sorted({*PLUGIN_MODULES, _VAD_MODULE}):
        try:
            importlib.import_module(f"livekit.plugins.{module}")
        except ImportError:
            continue
        registered.append(module)
    return registered


def prewarm(proc: Any) -> None:
    """Load the voice-activity model once per worker process, not per call.

    Silero is a few megabytes of ONNX. Loading it inside `run_call` would add
    that to the moment the contact says hello, which is the one moment in a call
    that cannot afford it. The module itself is already imported by
    `register_plugins()` - this only builds the model.
    """
    from livekit.plugins import silero

    proc.userdata["vad"] = silero.VAD.load()


def _vad(ctx: Any) -> Any:
    """The prewarmed model, or one loaded now if this worker skipped prewarm."""
    cached = getattr(getattr(ctx, "proc", None), "userdata", {}) or {}
    if cached.get("vad") is not None:
        return cached["vad"]

    from livekit.plugins import silero

    log.warning("voice activity model was not prewarmed - loading it mid-call")
    return silero.VAD.load()


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
    metadata: dict[str, Any],
    *,
    transcript: str,
    duration_seconds: int,
    error: str | None = None,
    collected: dict[str, Any] | None = None,
    provider_call_id: str | None = None,
) -> dict[str, Any]:
    """The body `/internal/v1/runs/{run_id}/complete` expects.

    `contact_name`/`phone_masked` are echoed straight back from metadata
    because the API keys the outcome row on them - inventing either here would
    create a second row rather than resolving the in-flight one.

    `collected` is the organisation's own business fields and goes in its own
    key, never into `extracted`: the API reads triage's inputs out of
    `extracted`, so a field an organisation happened to call `do_not_call`
    would otherwise decide the disposition. `extracted` stays empty until
    something actually infers those signals from the conversation - sending
    nothing keeps triage falling through to the status buckets rather than
    acting on invented values.
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
        "extracted": {},
        "collected": collected or {},
        "provider_call_id": provider_call_id,
    }


async def wait_for_call_end(
    ctx: Any,
    *,
    answer_timeout: float,
    max_seconds: float,
    on_answered: Callable[[], Awaitable[None]] | None = None,
    should_end: Callable[[], bool] | None = None,
) -> bool:
    """Block while the contact is on the line. Returns whether anyone joined.

    This is the whole reason a job outlives its own setup. Returning as soon as
    the session starts would close the room while the phone was still ringing,
    and every call would report an empty transcript.

    Two waits, not one, because they mean different things: nobody arriving is
    an unanswered call, while somebody arriving and then leaving is a finished
    one. `max_seconds` is the backstop for the third case - a room that never
    reports either.

    `on_answered` fires between them, once the contact is actually in the room.
    That is where the agent's opening line belongs: speaking any earlier plays
    it into an empty room, and the person who then says "hello?" is answered by
    silence.

    `should_end` is polled while the call is up, and returning True closes it
    from this side. That is how "please stop calling me" hangs up on the spot:
    the tool sets a flag and this returns, rather than the agent waiting for the
    contact to disconnect a call they already asked to end.
    """
    try:
        await asyncio.wait_for(ctx.wait_for_participant(), timeout=answer_timeout)
    except TimeoutError:
        log.info("nobody joined within %ss - the call went unanswered", answer_timeout)
        return False

    ended = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _on_left(*_args: Any) -> None:
        # `Event.set` is not thread-safe and LiveKit's room events cross a
        # thread boundary from the Rust bridge.
        loop.call_soon_threadsafe(ended.set)

    room = ctx.room
    room.on("participant_disconnected", _on_left)
    room.on("disconnected", _on_left)

    if on_answered is not None:
        await on_answered()

    # Checked *after* the handlers are armed: a very short call can end between
    # the join above and this line, and a handler registered afterwards would
    # never fire, leaving the worker waiting out the full ceiling.
    if not getattr(room, "remote_participants", None):
        return True

    if should_end is None:
        try:
            await asyncio.wait_for(ended.wait(), timeout=max_seconds)
        except TimeoutError:
            log.warning("call ran past the %ss ceiling - closing it from this side", max_seconds)
        return True

    # Polled rather than awaited on an event, because the flag is set from
    # inside a tool call on the session's own task - handing that task an
    # asyncio primitive to signal is more machinery than a one-second check.
    deadline = max_seconds
    while deadline > 0:
        if should_end():
            log.info("the agent asked to end the call - closing it from this side")
            return True
        try:
            await asyncio.wait_for(ended.wait(), timeout=min(_HANGUP_POLL_SECONDS, deadline))
            return True
        except TimeoutError:
            deadline -= _HANGUP_POLL_SECONDS

    log.warning("call ran past the %ss ceiling - closing it from this side", max_seconds)
    return True


def build_tools(collector: Collector) -> list[Any]:
    """The two things an agent can *do* during a call, as LLM tools.

    Built per call rather than declared at module scope because both close over
    this call's `Collector`. `record_field` is described in terms of the actual
    field names so the model does not have to infer the vocabulary from the
    prompt, and `end_call` exists because "please stop calling me" has to end
    the call on the spot rather than after the agent finishes its sentence -
    that is the difference between a system that respects a refusal and one that
    talks over it.
    """
    from livekit.agents import function_tool

    keys = collector.keys

    @function_tool
    async def record_field(key: str, value: str) -> str:
        """Record one answer the contact has given.

        Args:
            key: Which field this answers. One of: {keys}.
            value: What the contact said, in their own terms.
        """
        return collector.record(key, value)

    # The docstring is the tool schema the model sees, so the real field names
    # have to be substituted in rather than left as a placeholder.
    record_field.__doc__ = (record_field.__doc__ or "").format(
        keys=", ".join(keys) or "none - do not call this tool"
    )

    @function_tool
    async def end_call(reason: str) -> str:
        """End the call now. Use this the moment the contact asks you to stop,
        asks not to be called again, or says goodbye.

        Args:
            reason: Why the call is ending, in one short phrase.
        """
        collector.request_hangup(reason)
        return "Ending the call now."

    tools: list[Any] = [end_call]
    if keys:
        # An agent with no fields gets no recording tool at all, rather than one
        # it can only ever misuse.
        tools.insert(0, record_field)
    return tools


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

    # `prompt` is what the dialer sends (ADR-8); `goal` is what campaigns sent
    # and is still read so a job dispatched by an older API build is held rather
    # than answered with the fallback line.
    prompt = (
        metadata.get("prompt")
        or metadata.get("goal")
        or "Have a brief, polite conversation and end the call."
    )
    spec = AgentSpec.from_metadata(metadata)
    collector = Collector(fields=fields_from_metadata(metadata))

    transcript = ""
    error: str | None = None
    duration_seconds = 0
    started = ctx.job.id if hasattr(ctx.job, "id") else ""
    log.info("starting call for run %s (job %s)", run_id, started)

    session: Any = None
    try:
        pipeline = build_pipeline(spec)
        # Connect before the session starts: `session.start()` publishes the
        # agent's own track into the room, which needs the connection to exist.
        await ctx.connect()
        session = AgentSession(
            stt=pipeline.stt,
            tts=pipeline.tts,
            llm=pipeline.llm,
            # Without voice activity detection an STT pipeline has no way to
            # know when the contact stopped talking, so it never takes a turn.
            vad=_vad(ctx),
        )
        await session.start(
            agent=Agent(instructions=prompt, tools=build_tools(collector)),
            room=ctx.room,
        )

        began_at = time.monotonic()

        async def greet() -> None:
            # CallFlow only ever dials out, and the person who picks up an
            # outbound call waits to be spoken to. An agent that waits back
            # leaves both sides listening to each other in silence until one
            # hangs up - which is exactly what the first live call did.
            await session.generate_reply(instructions=_OPENING)

        answered = await wait_for_call_end(
            ctx,
            answer_timeout=config.answer_timeout_seconds,
            max_seconds=float(metadata.get("max_call_duration_seconds") or config.max_call_seconds),
            on_answered=greet,
            should_end=lambda: collector.hangup_reason is not None,
        )
        if answered:
            duration_seconds = int(time.monotonic() - began_at)
        if collector.hangup_reason:
            log.info("run %s: agent ended the call - %s", run_id, collector.hangup_reason)
    except Exception as exc:
        # The reason is logged in full but only the exception *type* is
        # reported: a vendor message can carry an API key or the dialled
        # number, and this string reaches a user-facing field.
        log.exception("call for run %s failed", run_id)
        error = type(exc).__name__
    finally:
        if session is not None:
            # Read before closing - `aclose()` is free to drop the history.
            transcript = transcript_from_history(getattr(session, "history", None))
            try:
                await session.aclose()
            except Exception:
                log.exception("run %s: closing the session failed", run_id)

        # Recorded values win over recovered ones: the first is what the agent
        # heard, the second is `collection.py`'s reading of the transcript.
        collected = {**recover_missing(collector.fields, collector.values, transcript),
                     **collector.values}

        payload = completion_payload(
            metadata,
            transcript=transcript,
            duration_seconds=duration_seconds,
            error=error,
            collected=collected,
            provider_call_id=str(getattr(ctx.job, "id", "") or "") or None,
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

    # Before any job exists, and before `cli.run_app` hands control to the
    # worker's own threads.
    registered = register_plugins()
    log.info("registered %d vendor plugin(s): %s", len(registered), ", ".join(registered))

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=run_call,
            prewarm_fnc=prewarm,
            agent_name=config.agent_name,
        )
    )


if __name__ == "__main__":
    main()
