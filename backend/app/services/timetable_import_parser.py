"""
TTEK-SMS's own generic timetable CSV format — pure parsing, no DB access, so
it's testable in isolation from services/timetable_import.py's DB-aware
orchestration (same split as report_card_scoring.py being a shared leaf
module for report_card.py/report_card_rank.py).

Required columns, exact header text (Day,Period,Subject,Classes) — this is
our own format, not a mirror of any scheduling tool's export (FET, aSc,
etc.), so headers are matched strictly rather than leniently: any missing
or unrecognized column rejects the whole file with a clear 422 instead of
guessing. A `Classes` cell may list more than one class separated by `;`
— our own feature for a genuinely shared/combined period (e.g. assembly,
games) where one teacher runs the same period for several classes at once;
see services/timetable_import.py's same-source-line exemption for how that
stays distinct from an actual double-booking. `;` (not `,`) is the
separator deliberately: `,` is CSV's own field delimiter, so an unquoted
comma-separated list inside one cell is ambiguous by construction.
"""
from __future__ import annotations
import csv
import io
import re
from dataclasses import dataclass, field

from fastapi import HTTPException, status

_REQUIRED_HEADERS = ["Day", "Period", "Subject", "Classes"]

_DAY_ALIASES: dict[str, str] = {
    "MON": "MON", "MONDAY": "MON",
    "TUE": "TUE", "TUESDAY": "TUE", "TUES": "TUE",
    "WED": "WED", "WEDNESDAY": "WED",
    "THU": "THU", "THURSDAY": "THU", "THUR": "THU", "THURS": "THU",
    "FRI": "FRI", "FRIDAY": "FRI",
    "SAT": "SAT", "SATURDAY": "SAT",
    "SUN": "SUN", "SUNDAY": "SUN",
}


@dataclass
class ParsedTimetableRow:
    """One (day, period, subject, class) combination after expanding a CSV
    line's multi-class cell — row_number is the *source* CSV line, so
    several ParsedTimetableRow can legitimately share one when a line lists
    more than one class."""
    row_number: int
    day_code: str | None       # None if day_raw wasn't recognized
    day_raw: str
    period_token: str
    subject_name: str
    class_label: str
    raw: dict = field(default_factory=dict)


def parse_timetable_csv(file_bytes: bytes) -> list[ParsedTimetableRow]:
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Could not read the file as text — save it as a CSV file and try again.",
        )

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The CSV file has no header row.")

    found = [h.strip() for h in reader.fieldnames]
    # Blank trailing header(s) are ignored — a common Excel/Sheets export
    # artifact (a stray trailing column separator) — but any other unlisted
    # column still rejects the file, e.g. an old FET-shaped file that still
    # carries a real "Teacher(s)" column.
    non_blank = [h for h in found if h]
    if non_blank != _REQUIRED_HEADERS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"CSV headers must be exactly: {', '.join(_REQUIRED_HEADERS)}. Found: {', '.join(found)}.",
        )
    # If Classes is the last real column, an unquoted comma-separated list
    # there (e.g. `...,2 A, 2 B`) produces a row with MORE fields than
    # headers — csv.DictReader dumps the overflow into row[None] instead of
    # the Classes column. Fold it back in (rather than silently dropping it)
    # so the row still surfaces as a clear "class not found" error below
    # instead of vanishing outright; `;` remains the only real separator.
    classes_col_is_last = all(not h for h in found[found.index("Classes") + 1:])

    rows: list[ParsedTimetableRow] = []
    for row_number, raw in enumerate(reader, start=2):  # header is line 1
        day_raw = (raw.get("Day") or "").strip()
        period_token = (raw.get("Period") or "").strip()
        subject_name = (raw.get("Subject") or "").strip()
        classes_raw = (raw.get("Classes") or "").strip()
        overflow = raw.get(None)
        if classes_col_is_last and overflow:
            classes_raw = ",".join([classes_raw, *overflow])
        if not any([day_raw, period_token, subject_name, classes_raw]):
            continue  # blank line

        day_code = _DAY_ALIASES.get(re.sub(r"[^A-Z]", "", day_raw.upper()))
        class_tokens = [c.strip() for c in classes_raw.split(";") if c.strip()]
        if not class_tokens:
            # Day/Period/Subject were filled in but Classes was blank —
            # still report the row (with an empty class label) so the
            # DB-aware orchestrator's "class not found" error surfaces it,
            # rather than the row silently vanishing from the results.
            class_tokens = [""]

        for class_label in class_tokens:
            rows.append(ParsedTimetableRow(
                row_number=row_number, day_code=day_code, day_raw=day_raw,
                period_token=period_token, subject_name=subject_name,
                class_label=class_label, raw=dict(raw),
            ))
    return rows
