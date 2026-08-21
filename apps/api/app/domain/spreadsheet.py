"""Turning an uploaded sheet into contact rows.

The rules a spreadsheet has to satisfy before anything is dialled, as pure
functions over cell values. No file handling and no HTTP: the route hands this a
list of rows and gets back rows that are either valid or carry the reason they
are not.

`name`, `phone` and `note` are recognised by header name; every other headed
column becomes that contact's own context, which is what lets one sheet produce
a different conversation per person. `apps/web/lib/contacts.ts` applies the same
rules to a pasted CSV, and the two must agree - a row the browser accepts and
the server rejects is a row someone has no way to fix.

Invalid rows come back flagged rather than dropped. Silently discarding one
means a contact never gets called and nobody finds out why.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.domain.prompt_assembly import DETAIL_KEY, RESERVED_CONTEXT_KEYS
from app.domain.safety import is_e164

#: The three columns CallFlow reads by name. Everything else is context.
KNOWN_HEADERS = ("name", "phone", "note")

#: A sheet larger than this is refused rather than parsed. Well past any real
#: contact list, and the point past which one upload can occupy a worker long
#: enough to matter. The per-run ceiling in Settings → Safety is the limit that
#: actually governs how many calls happen; this only bounds the parse.
MAX_ROWS = 20_000

_DIGITS = re.compile(r"[^\d+]")


@dataclass(frozen=True)
class ParsedRow:
    """One row, with either a phone number or a reason it has none."""

    row: int
    name: str
    phone: str
    note: str
    context: dict[str, str] = field(default_factory=dict)
    error: str | None = None

    @property
    def valid(self) -> bool:
        return self.error is None


class SheetTooLarge(ValueError):
    """The upload has more rows than one run can sensibly parse."""


def to_context_key(header: str) -> str:
    """A header as a context key: lowercased, spaces and dashes to underscores.

    So `Trip type` and `trip_type` are the same column rather than two.
    """
    cleaned = re.sub(r"[^a-z0-9_\s-]", "", header.strip().lower())
    return re.sub(r"[\s-]+", "_", cleaned)[:40]


def cell_text(value: Any) -> str:
    """A cell as the text a person typed into it.

    Excel stores a phone number typed as `919876543210` as a float, so the plain
    `str()` of it is `9.19876543210e+11` - which then fails E.164 validation for
    a number that is actually fine. Integral floats are rendered as integers for
    that reason.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def normalise_phone(raw: str) -> str:
    """A phone number with the punctuation a person types stripped out.

    Only characters removed, never digits added: guessing a country code is how
    a run dials the wrong country. A number without one fails validation and the
    row says so.

    A leading `+` is kept and any other one dropped - a `+` in the middle is a
    typo, not a second country code.
    """
    text = raw.strip()
    if not text:
        return ""
    digits = _DIGITS.sub("", text).replace("+", "")
    return f"+{digits}" if text.startswith("+") else digits


def validate(name: str, phone: str, raw_phone: str | None = None) -> str | None:
    """Why this row cannot be dialled, or None if it can.

    `raw_phone` is what was actually in the cell, which is the difference
    between two messages that must not be swapped: an empty cell needs a number
    added, while a cell holding `not a number` needs the one that is there
    corrected. Normalisation strips both to the same empty string, so without
    the original the second row is told to fill in a field it already filled in.
    """
    if not name:
        return "Add a name for this row."
    if not phone:
        if raw_phone and raw_phone.strip():
            return "Not a valid E.164 number - try +919876543210."
        return "Add a phone number for this row."
    if not is_e164(phone):
        return "Not a valid E.164 number - try +919876543210."
    return None


def parse_rows(rows: list[list[Any]]) -> list[ParsedRow]:
    """Sheet rows into contact rows, header row included.

    A sheet with no recognisable header is refused rather than read
    positionally: unnamed columns have no key to travel under, so the context
    that makes each conversation different would be silently dropped - and an
    upload that appears to work while losing the point of the feature is worse
    than one that says what is wrong.
    """
    if len(rows) > MAX_ROWS:
        raise SheetTooLarge(
            f"This sheet has more than {MAX_ROWS:,} rows. Split it into smaller uploads."
        )

    body = [r for r in rows if any(cell_text(c) for c in r)]
    if not body:
        return []

    headers = [to_context_key(cell_text(c)) for c in body[0]]
    if not any(h in KNOWN_HEADERS for h in headers):
        raise ValueError(
            "The first row must name the columns. Add a header row with at least "
            "name and phone."
        )

    index_of = {h: headers.index(h) for h in KNOWN_HEADERS if h in headers}
    context_columns = {
        position: header
        for position, header in enumerate(headers)
        if header
        and header not in KNOWN_HEADERS
        # A column named `goal` or `voice_agent` would otherwise land in the same
        # metadata dict the worker reads its own instructions from. Dropped here
        # as well as stripped downstream, so the upload can be honest about it.
        and header not in RESERVED_CONTEXT_KEYS
    }

    def cell(raw_row: list[Any], column: str) -> str:
        position = index_of.get(column)
        if position is None or position >= len(raw_row):
            return ""
        return cell_text(raw_row[position])

    parsed: list[ParsedRow] = []
    for offset, raw_row in enumerate(body[1:], start=2):
        name = cell(raw_row, "name")
        note = cell(raw_row, "note")
        raw_phone = cell(raw_row, "phone")
        phone = normalise_phone(raw_phone)

        context = {
            header: cell_text(raw_row[position])
            for position, header in context_columns.items()
            if position < len(raw_row) and cell_text(raw_row[position])
        }

        parsed.append(
            ParsedRow(
                row=offset,
                name=name,
                phone=phone,
                note=note,
                context=context,
                error=validate(name, phone, raw_phone),
            )
        )

    return parsed


def to_contact_payload(row: ParsedRow) -> dict[str, Any]:
    """One valid row as the shape `POST /api/v1/runs` accepts.

    The note becomes `DETAIL_KEY`, which is the key `render_call_prompt` reads
    for "what this call is about" - and which it then excludes from the
    "what else we know" block, so the note is stated once rather than twice.
    `note` is kept alongside it for prompts written against the older key.

    Set here rather than passed through as a context column precisely because
    `detail` is reserved: a spreadsheet cannot claim it, but CallFlow can.
    """
    context = dict(row.context)
    if row.note:
        context[DETAIL_KEY] = row.note
        context["note"] = row.note
    return {"name": row.name, "phone": row.phone, "context": context}


__all__ = [
    "KNOWN_HEADERS",
    "MAX_ROWS",
    "ParsedRow",
    "SheetTooLarge",
    "cell_text",
    "normalise_phone",
    "parse_rows",
    "to_contact_payload",
    "to_context_key",
    "validate",
]
