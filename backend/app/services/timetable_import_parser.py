"""
FET CSV timetable parser — pure parsing, no DB access, so it's testable in
isolation from services/timetable_import.py's DB-aware orchestration (same
split as report_card_scoring.py being a shared leaf module for
report_card.py/report_card_rank.py).

Expected columns follow FET's ("Free Timetabling Software") standard
"export timetable to one CSV" layout: Day, Hour, Subject, Teacher(s),
Students/Class(es) — an optional Room(s) column, if present, is read and
discarded (no room model exists in this codebase). Header names are matched
leniently (case/whitespace/punctuation-insensitive against a small alias
list in _ALIASES) since no real FET export sample was available when this
was written — if a real file's headers differ further, this raises a clear
422 rather than silently misparsing, so the fix stays localized to
_ALIASES below instead of the orchestration logic.
"""
from __future__ import annotations
import csv
import io
import re
from dataclasses import dataclass, field

from fastapi import HTTPException, status

_ALIASES: dict[str, set[str]] = {
    "day": {"day"},
    "hour": {"hour", "period", "time", "hournumber"},
    "subject": {"subject", "subjects"},
    "teachers": {"teachers", "teacher"},
    "classes": {"studentsclasses", "students", "classes", "class"},
}

_DAY_ALIASES: dict[str, str] = {
    "MON": "MON", "MONDAY": "MON",
    "TUE": "TUE", "TUESDAY": "TUE", "TUES": "TUE",
    "WED": "WED", "WEDNESDAY": "WED",
    "THU": "THU", "THURSDAY": "THU", "THUR": "THU", "THURS": "THU",
    "FRI": "FRI", "FRIDAY": "FRI",
    "SAT": "SAT", "SATURDAY": "SAT",
    "SUN": "SUN", "SUNDAY": "SUN",
}


def _normalize_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "", h.strip().lower())


@dataclass
class ParsedTimetableRow:
    """One (day, hour, subject, class) combination after expanding a CSV
    line's multi-class/multi-teacher cells — row_number is the *source* CSV
    line, so several ParsedTimetableRow can legitimately share one when a
    line lists more than one class."""
    row_number: int
    day_code: str | None       # None if day_raw wasn't recognized
    day_raw: str
    hour_token: str
    subject_name: str
    class_label: str
    teacher_name: str
    extra_teacher_names: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


def parse_fet_csv(file_bytes: bytes) -> list[ParsedTimetableRow]:
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Could not read the file as text — export it as CSV from FET and try again.",
        )

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The CSV file has no header row.")

    header_by_key = {_normalize_header(h): h for h in reader.fieldnames}
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for key, aliases in _ALIASES.items():
        match = next((header_by_key[a] for a in aliases if a in header_by_key), None)
        if match is None:
            missing.append(key)
        else:
            resolved[key] = match
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Unexpected CSV columns — expected a FET timetable export with columns for "
            f"Day, Hour, Subject, Teacher(s), and Students/Class(es). Missing: {', '.join(missing)}. "
            f"Found: {', '.join(reader.fieldnames)}.",
        )
    # When "classes" is the last real header column, a user typing an
    # unquoted comma-separated list there (e.g. `...,2 A, 2 B`) produces a
    # row with MORE fields than headers — csv.DictReader dumps the overflow
    # into row[None] instead of the classes column. Fold it back in so a
    # trailing multi-class cell still expands whether or not it was quoted.
    classes_col_is_last = reader.fieldnames.index(resolved["classes"]) == len(reader.fieldnames) - 1

    rows: list[ParsedTimetableRow] = []
    for row_number, raw in enumerate(reader, start=2):  # header is line 1
        day_raw = (raw.get(resolved["day"]) or "").strip()
        hour_token = (raw.get(resolved["hour"]) or "").strip()
        subject_name = (raw.get(resolved["subject"]) or "").strip()
        teachers_raw = (raw.get(resolved["teachers"]) or "").strip()
        classes_raw = (raw.get(resolved["classes"]) or "").strip()
        overflow = raw.get(None)
        if classes_col_is_last and overflow:
            classes_raw = ",".join([classes_raw, *overflow])
        if not any([day_raw, hour_token, subject_name, teachers_raw, classes_raw]):
            continue  # blank line

        day_code = _DAY_ALIASES.get(re.sub(r"[^A-Z]", "", day_raw.upper()))
        teacher_tokens = [t.strip() for t in re.split(r"[;,]", teachers_raw) if t.strip()]
        class_tokens = [c.strip() for c in re.split(r"[;,]", classes_raw) if c.strip()]
        teacher_name = teacher_tokens[0] if teacher_tokens else ""
        extra_teachers = teacher_tokens[1:]

        for class_label in class_tokens:
            rows.append(ParsedTimetableRow(
                row_number=row_number, day_code=day_code, day_raw=day_raw,
                hour_token=hour_token, subject_name=subject_name, class_label=class_label,
                teacher_name=teacher_name, extra_teacher_names=extra_teachers, raw=dict(raw),
            ))
    return rows
