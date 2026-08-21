"""Starting and reading runs - org-scoped, persisted.

Every run dials for real. There is no dry-run mode (CLAUDE.md, ADR-3).

**The only guard between "started a run" and "rang a real phone" is the
suppression list.** The per-run ceiling, the allowlist, per-organisation rate
limiting, the daily budget and per-teammate credits were all removed at the
product owner's direction while a replacement security layer is designed - see
`domain/safety.py`'s module docstring. Nothing here throttles, caps, or bills a
run: a request that resolves an agent and a verified number dials every contact
in the list.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser, RequirePermission, current_user
from app.auth.permissions import Permission
from app.core.config import config
from app.core.logging import CallContext
from app.database import database
from app.database.repositories import escalations as escalations_repo
from app.database.repositories import run_numbers as run_numbers_repo
from app.database.repositories import runs as runs_repo
from app.database.repositories import suppressions as suppressions_repo
from app.domain.entities import NEEDS_A_PERSON_DISPOSITIONS, CallOutcome, Contact
from app.domain.safety import mask, phone_hash
from app.domain.spreadsheet import (
    MAX_ROWS,
    SheetTooLarge,
    parse_rows,
    to_contact_payload,
)
from app.services.run_dialer import RunDialer
from app.services.run_dispatch import RunNotDispatchable, RunPlan, resolve_run_plan

log = logging.getLogger("app.api.v1.runs")

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


class ContactIn(BaseModel):
    name: str
    phone: str
    region: str | None = None
    language: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class RunRequest(BaseModel):
    """What starting a run needs.

    The number lives here rather than on the agent (ADR-8), which is what lets
    one agent dial through any carrier the organisation has connected.
    """

    voice_agent_id: UUID
    #: One, several, or every verified number. A run with none is refused.
    number_ids: list[UUID] = Field(default_factory=list)
    contacts: list[ContactIn]
    #: A human label for the run list. Optional - runs are also identifiable by
    #: their agent and start time.
    name: str | None = Field(default=None, max_length=120)
    #: Appended to every prompt in this run, so a one-off instruction does not
    #: mean editing an agent the whole organisation shares.
    run_instruction: str | None = Field(default=None, max_length=2000)
    allocation_strategy: str = "round_robin"


def _deduplicate(contacts: Iterable[Contact]) -> list[Contact]:
    """Collapse contacts that would share one `call_outcomes` row.

    That table is keyed on (run_id, contact_name, phone_masked), so a CSV
    listing the same person twice produces one row however many times it is
    dialled - while `runs.total` counted both. The settled count could then
    never reach the total and the run stayed "running" forever.

    Deduplicating beats loosening the key: a run should not dial the same
    person twice anyway, and the row that would have been overwritten was a
    real call whose transcript was being discarded.
    """
    seen: set[tuple[str, str]] = set()
    unique: list[Contact] = []
    for contact in contacts:
        key = (contact.name, contact.phone)
        if key in seen:
            log.info("skipping a repeated contact in this run's list")
            continue
        seen.add(key)
        unique.append(contact)
    return unique


async def _run_and_persist(
    *,
    run_id: str,
    org_id: UUID,
    auth_user_id: str,
    plan: RunPlan,
    contacts: list[Contact],
    suppressed_hashes: frozenset[str],
) -> None:
    dialer = RunDialer(
        suppressed_hashes=suppressed_hashes,
        run_id=run_id,
        # The two things nothing ever passed before, which is why every dial was
        # refused before the phone rang.
        lines=plan.lines,
        voice_agent=plan.voice_agent,
        allocation_strategy=plan.allocation_strategy,
        run_instruction=plan.run_instruction,
    )

    async def on_progress(outcome: CallOutcome) -> None:
        record = outcome.model_dump(mode="json")
        record["provider_call_id"] = record.pop("run_id", None)
        async with database.as_user(auth_user_id) as conn:
            call_outcome_id = await runs_repo.append_outcome(
                conn, run_id=run_id, org_id=org_id, outcome=record
            )
            if outcome.disposition in NEEDS_A_PERSON_DISPOSITIONS:
                await escalations_repo.create_for_outcome(
                    conn, org_id=org_id, run_id=run_id, call_outcome_id=call_outcome_id
                )

    # Every log line this run produces - in this module and `RunDialer` -
    # carries `run_id`/`org_id` for the run's whole lifetime, so one run's
    # lines can be grepped together regardless of which contact or module
    # emitted them.
    with CallContext(run_id=run_id, org_id=str(org_id)):
        try:
            await dialer.run(plan.agent, contacts, on_progress=on_progress)
            # Deliberately not `finish_run()`. Origination returns when a call
            # is answered, not when it ends, so at this point conversations are
            # still running - closing the run here would show it completed
            # while its own rows still read "In conversation…". Whichever
            # worker callback settles the last contact closes it instead
            # (`finish_if_all_settled`). This still handles the case where every
            # contact was blocked or failed to dial: those settle immediately,
            # so the check below closes the run right away.
            async with database.as_user(auth_user_id) as conn:
                await runs_repo.finish_if_all_settled(
                    conn, run_id, stale_after_seconds=int(config.poll_timeout_seconds) * 2
                )
        except Exception as exc:
            log.exception("run %s failed", run_id)
            async with database.as_user(auth_user_id) as conn:
                await runs_repo.finish_run(conn, run_id, error=f"{type(exc).__name__}: {exc}")


@router.post("", status_code=status.HTTP_200_OK)
async def start_run(
    req: RunRequest,
    request: Request,
    background: BackgroundTasks,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.RUNS_START))],
) -> dict[str, Any]:
    # Resolved before anything is written: a run that cannot dial must not
    # exist as a row that never starts, and every refusal here names the thing to
    # go and fix.
    async with database.as_user(user.auth_user_id) as conn:
        try:
            plan = await resolve_run_plan(
                conn,
                org_id=user.org_id,
                voice_agent_id=req.voice_agent_id,
                number_ids=req.number_ids,
                allocation_strategy=req.allocation_strategy,
                run_instruction=req.run_instruction,
            )
        except RunNotDispatchable as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not req.contacts:
        raise HTTPException(status_code=400, detail="At least one contact is required.")

    try:
        contacts = _deduplicate(Contact(**c.model_dump()) for c in req.contacts)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    run_id = uuid.uuid4().hex[:12]
    async with database.as_user(user.auth_user_id) as conn:
        # Resolved once here, not once per contact - the one guard that still
        # stands before a dial.
        suppressed: set[str] = set()
        for contact in contacts:
            digest = phone_hash(contact.phone)
            if await suppressions_repo.is_suppressed(conn, user.org_id, digest):
                suppressed.add(digest)

        await runs_repo.create_run(
            conn,
            run_id=run_id,
            org_id=user.org_id,
            voice_agent_id=req.voice_agent_id,
            total=len(contacts),
            started_by=user.id,
            name=req.name,
            run_instruction=req.run_instruction,
            allocation_strategy=req.allocation_strategy,
        )
        # Which lines this run may dial from, recorded before it starts: the run
        # is the permanent record of where its calls came from, and resolving
        # that later from a number that has since been retired would lose it.
        await run_numbers_repo.attach(
            conn,
            run_id=run_id,
            org_id=user.org_id,
            number_ids=[line.number_id for line in plan.lines],
        )

    background.add_task(
        _run_and_persist,
        run_id=run_id,
        org_id=user.org_id,
        auth_user_id=user.auth_user_id,
        plan=plan,
        contacts=contacts,
        suppressed_hashes=frozenset(suppressed),
    )
    return {"run_id": run_id, "total": len(contacts)}


@router.get("")
async def list_runs(user: Annotated[CurrentUser, Depends(current_user)]) -> list[dict[str, Any]]:
    async with database.as_user(user.auth_user_id) as conn:
        rows = await runs_repo.list_runs(conn, user.org_id)
    return [
        {
            "id": r["id"],
            "voice_agent_id": str(r["voice_agent_id"]) if r["voice_agent_id"] else None,
            "agent_name": r["agent_name"],
            "name": r["name"],
            "total": r["total"],
            "status": r["status"],
            "started_at": r["started_at"].isoformat(),
            "finished_at": r["finished_at"].isoformat() if r["finished_at"] else None,
            "error": r["error"],
            "completed": r["completed"],
            "started_by": str(r["started_by"]) if r["started_by"] else None,
            "started_by_name": r["started_by_name"],
            "started_by_avatar_url": r["started_by_avatar_url"],
        }
        for r in rows
    ]


class TeamMemberSummary(BaseModel):
    user_id: str | None
    name: str | None
    avatar_url: str | None
    total_runs: int
    total_calls: int


@router.get(
    "/team-summary",
    response_model=list[TeamMemberSummary],
    dependencies=[Depends(RequirePermission(Permission.RUNS_READ_TEAM))],
)
async def team_summary(user: Annotated[CurrentUser, Depends(current_user)]) -> list[TeamMemberSummary]:
    """Call volume per teammate, for the admin/owner/viewer dashboard chart."""
    async with database.as_user(user.auth_user_id) as conn:
        rows = await runs_repo.summarize_by_member(conn, user.org_id)
    return [
        TeamMemberSummary(
            user_id=str(r["started_by"]) if r["started_by"] else None,
            name=r["started_by_name"],
            avatar_url=r["started_by_avatar_url"],
            total_runs=r["total_runs"],
            total_calls=r["total_calls"],
        )
        for r in rows
    ]


@router.get("/{run_id}")
async def get_run(
    run_id: str, user: Annotated[CurrentUser, Depends(current_user)]
) -> dict[str, Any]:
    async with database.as_user(user.auth_user_id) as conn:
        run = await runs_repo.get_run(conn, user.org_id, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        outcome_rows = await runs_repo.list_outcomes(conn, run_id)

    outcomes = [
        {
            "contact_name": o["contact_name"],
            "phone_masked": o["phone_masked"],
            "voice_agent_id": str(run["voice_agent_id"]) if run["voice_agent_id"] else None,
            "agent_name": run["agent_name"],
            "status": o["status"],
            "run_id": run_id,
            "provider_call_id": o["provider_call_id"],
            "transcript": o["transcript"],
            "summary": o["summary"],
            "sentiment": o["sentiment"],
            "sentiment_reason": o["sentiment_reason"],
            "extracted": o["extracted"],
            "disposition": o["disposition"],
            "disposition_reason": o["disposition_reason"],
            "error": o["error"],
            "duration_seconds": o["duration_seconds"],
            "created_at": o["created_at"].isoformat(),
            "task_completed": o["task_completed"],
            "completion_confidence_score": o["completion_confidence_score"],
            "completion_confidence_label": o["completion_confidence_label"],
            "evidence": o["evidence"],
            "attempts": o["attempts"],
            # The fields the agent was actually sent to collect. Persisted
            # since `ISSUES.md` #155 - the column, the domain model, the API
            # type and `TranscriptView` all existed, and only the write and
            # this serialisation were missing, so every run showed an empty
            # "What we asked for".
            "collected": o["collected"],
            "missing_required_fields": o["missing_required_fields"],
            "handoff_questions": o["handoff_questions"],
            "from_number_masked": o["from_number_masked"],
        }
        for o in outcome_rows
    ]
    resolved = [o for o in outcomes if o["disposition"] != "in_flight"]
    escalated = sum(1 for o in resolved if o["disposition"] == "escalated")

    started_by = run["started_by"]
    return {
        "id": run["id"],
        "voice_agent_id": str(run["voice_agent_id"]) if run["voice_agent_id"] else None,
        "agent_name": run["agent_name"],
        "total": run["total"],
        "status": run["status"],
        "started_at": run["started_at"].isoformat(),
        "finished_at": run["finished_at"].isoformat() if run["finished_at"] else None,
        "error": run["error"],
        "started_by": str(started_by) if started_by else None,
        "started_by_name": run["started_by_name"],
        "started_by_avatar_url": run["started_by_avatar_url"],
        "outcomes": outcomes,
        "stats": {
            "completed": len(resolved),
            "total": run["total"],
            "escalated": escalated,
            "auto_closed": sum(1 for o in outcomes if o["disposition"] == "auto_closed"),
            "needs_human_pct": round(100 * escalated / len(outcomes)) if outcomes else 0,
        },
    }


#: Refused before a byte is parsed. A workbook this large is either not a
#: contact list or is one that belongs in several uploads - and `openpyxl`
#: materialises far more than the file size in memory.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

_XLSX_TYPES = frozenset(
    {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/octet-stream",
    }
)


class SheetRowOut(BaseModel):
    """One parsed row - valid, or carrying the reason it is not."""

    row: int
    name: str
    #: Masked. The composer shows enough to recognise a row; the full number
    #: travels only in the `contact` payload the browser posts straight back.
    phone_masked: str
    note: str
    context: dict[str, str]
    valid: bool
    error: str | None
    #: The body `POST /api/v1/runs` accepts for this row, or null when the row
    #: cannot be dialled. Built here so the browser is not re-deriving the
    #: context rules a second time and drifting from them.
    contact: dict[str, Any] | None


class SheetOut(BaseModel):
    rows: list[SheetRowOut]
    #: Context columns found across the sheet, so the composer can say what each
    #: contact brings into its own conversation.
    context_columns: list[str]


@router.post("/parse-sheet", response_model=SheetOut)
async def parse_sheet(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.RUNS_START))],
    file: Annotated[UploadFile, File()],
) -> SheetOut:
    """Read an uploaded `.xlsx` into contact rows. Nothing is dialled or stored.

    Parsing happens here rather than in the browser because a workbook is a zip
    of XML with shared strings, styles and typed cells - a phone number typed as
    digits arrives as a float, and getting that wrong turns a valid number into
    `9.19876543210e+11`. CSV is still parsed in the browser, where it is a
    string split and the whole round trip is unnecessary.

    The response is reviewed in the composer before a run is started, exactly as
    a pasted CSV is: an upload is never a dial.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="That file is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"That file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)}MB. "
                "Split it into smaller uploads."
            ),
        )

    filename = (file.filename or "").lower()
    if not filename.endswith((".xlsx", ".xlsm")) and file.content_type not in _XLSX_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Upload an .xlsx file, or paste the rows in as CSV.",
        )

    try:
        rows = _read_workbook(raw)
    except SheetTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        parsed = parse_rows(rows)
    except SheetTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    columns = sorted({key for row in parsed for key in row.context})
    # Row count and column names only - never a cell value, which is a
    # customer's own data (CLAUDE.md non-negotiable #5).
    log.info(
        "org %s parsed a sheet: %d rows, %d valid, context columns: %s",
        user.org_id,
        len(parsed),
        sum(1 for r in parsed if r.valid),
        ", ".join(columns) or "none",
    )

    return SheetOut(
        rows=[
            SheetRowOut(
                row=row.row,
                name=row.name,
                phone_masked=mask(row.phone) if row.phone else "",
                note=row.note,
                context=row.context,
                valid=row.valid,
                error=row.error,
                contact=to_contact_payload(row) if row.valid else None,
            )
            for row in parsed
        ],
        context_columns=columns,
    )


def _read_workbook(raw: bytes) -> list[list[Any]]:
    """The first worksheet as rows of cell values.

    `read_only` streams rather than building the whole object graph, and
    `data_only` takes a formula cell's cached result - a sheet where the phone
    column is `=CONCAT(...)` would otherwise arrive as the formula text.
    """
    import io

    from openpyxl import load_workbook
    from openpyxl.utils.exceptions import InvalidFileException

    try:
        workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except InvalidFileException as exc:
        raise ValueError(
            "That file could not be read as a spreadsheet. Save it as .xlsx and try again."
        ) from exc
    except Exception as exc:
        # openpyxl raises a wide range of types on a corrupt archive, and the
        # vendor's own message is not something to show a user.
        log.warning("could not read an uploaded workbook: %s", type(exc).__name__)
        raise ValueError(
            "That file could not be read as a spreadsheet. Save it as .xlsx and try again."
        ) from exc

    try:
        sheet = workbook.worksheets[0] if workbook.worksheets else None
        if sheet is None:
            raise ValueError("That workbook has no sheets.")

        rows: list[list[Any]] = []
        for row in sheet.iter_rows(values_only=True):
            rows.append(list(row))
            if len(rows) > MAX_ROWS:
                raise SheetTooLarge(
                    f"This sheet has more than {MAX_ROWS:,} rows. "
                    "Split it into smaller uploads."
                )
        return rows
    finally:
        workbook.close()
