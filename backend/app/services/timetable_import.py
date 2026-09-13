"""
FET CSV timetable bulk-import orchestration — DB-aware counterpart to
services/timetable_import_parser.py (pure parsing, no DB). Mirrors
staff_import.py's per-row savepoint / best-effort pattern: valid rows are
created, invalid/conflicting rows are skipped and reported, one bad row
never aborts the batch.

Reuses the exact validation the one-at-a-time timetable write path already
enforces (services/timetable.py::upsert_timetable_slot): the subject must
be on the class's curriculum, and a SubjectTeacher must already be assigned
before a subject can be timetabled — a bulk import that auto-created
SubjectTeacher rows from CSV names would turn "who teaches what" into a
side effect of a name matching a CSV cell, so rows missing that assignment
are reported as errors instead. TimetableSlot upserts are idempotent by
(class_id, period_id, academic_year_id), so re-running the same file after
fixing a gap (assigning a missing teacher, adding a subject to a class's
curriculum) safely fills it in without duplicating what already succeeded.
"""
from __future__ import annotations
import uuid
from datetime import datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import Class, SHSProgramme, Subject, SubjectTeacher, TimetableSlot
from app.models.attendance import SchoolPeriod
from app.models.documents import ImportBatch, ImportRow, ImportStatus
from app.schemas.documents import ImportBatchResult, ImportRowResult
from app.services.student_display import _class_display_name
from app.services.subject_roster import class_subject_exists
from app.services.timetable_import_parser import ParsedTimetableRow, parse_fet_csv


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ref(row: ParsedTimetableRow) -> str:
    return f"{row.day_raw or '?'} {row.hour_token or '?'} — {row.class_label}"


async def _load_class_maps(
    school_id: uuid.UUID, db: AsyncSession,
) -> tuple[dict[str, uuid.UUID], dict[uuid.UUID, str]]:
    """(lowercased label -> class_id) for lookup, (class_id -> label) for
    error messages that need to name another class by its real casing."""
    rows = await db.execute(
        select(Class, SHSProgramme.name.label("prog_name"))
        .outerjoin(SHSProgramme, Class.programme_id == SHSProgramme.id)
        .where(Class.school_id == school_id, Class.is_active.is_(True))
    )
    by_label: dict[str, uuid.UUID] = {}
    label_by_id: dict[uuid.UUID, str] = {}
    for cls, prog_name in rows:
        label = _class_display_name(cls.level, cls.year_group, prog_name, cls.stream)
        by_label[label.strip().lower()] = cls.id
        label_by_id[cls.id] = label
    return by_label, label_by_id


async def _load_subject_map(school_id: uuid.UUID, db: AsyncSession) -> dict[str, uuid.UUID]:
    rows = await db.scalars(
        select(Subject).where(Subject.school_id == school_id, Subject.is_active.is_(True))
    )
    return {s.name.strip().lower(): s.id for s in rows}


async def _load_period_maps(
    school_id: uuid.UUID, db: AsyncSession,
) -> tuple[dict[tuple[str, int], uuid.UUID], dict[tuple[str, time], uuid.UUID]]:
    periods = list(await db.scalars(select(SchoolPeriod).where(SchoolPeriod.school_id == school_id)))
    by_number = {(p.day_of_week.value, p.period_number): p.id for p in periods}
    by_start = {(p.day_of_week.value, p.start_time): p.id for p in periods}
    return by_number, by_start


async def _load_teacher_map(
    school_id: uuid.UUID, academic_year_id: uuid.UUID, db: AsyncSession,
) -> dict[tuple[uuid.UUID, uuid.UUID], uuid.UUID]:
    rows = await db.execute(
        select(SubjectTeacher.class_id, SubjectTeacher.subject_id, SubjectTeacher.staff_member_id).where(
            SubjectTeacher.school_id == school_id,
            SubjectTeacher.academic_year_id == academic_year_id,
            SubjectTeacher.is_active.is_(True),
        )
    )
    return {(class_id, subject_id): staff_id for class_id, subject_id, staff_id in rows}


async def _load_booked(
    school_id: uuid.UUID, academic_year_id: uuid.UUID, db: AsyncSession,
) -> dict[tuple[uuid.UUID, uuid.UUID], tuple[uuid.UUID, int | None]]:
    """(period_id, staff_member_id) -> (class_id, source_row_number),
    seeded from every already-committed slot this year (source_row_number
    None — always a real conflict, it wasn't part of this CSV) and extended
    in-memory as this batch's own rows commit, tagged with the CSV line
    that created them. A CSV that double-books a teacher across two
    DIFFERENT lines is caught; a single line listing multiple classes for
    the same teacher/period (one shared/combined activity — see
    parser.py's class-token expansion) is not treated as a conflict against
    its own sibling rows, only against a genuinely different line."""
    rows = await db.execute(
        select(TimetableSlot.period_id, SubjectTeacher.staff_member_id, TimetableSlot.class_id)
        .join(
            SubjectTeacher,
            (SubjectTeacher.class_id == TimetableSlot.class_id)
            & (SubjectTeacher.subject_id == TimetableSlot.subject_id)
            & (SubjectTeacher.academic_year_id == TimetableSlot.academic_year_id),
        )
        .where(TimetableSlot.school_id == school_id, TimetableSlot.academic_year_id == academic_year_id)
    )
    return {(period_id, staff_id): (class_id, None) for period_id, staff_id, class_id in rows}


def _resolve_period(
    row: ParsedTimetableRow,
    by_number: dict[tuple[str, int], uuid.UUID],
    by_start: dict[tuple[str, time], uuid.UUID],
) -> uuid.UUID | None:
    if row.day_code is None:
        return None
    try:
        return by_number.get((row.day_code, int(row.hour_token)))
    except ValueError:
        pass
    try:
        h, m = (int(p) for p in row.hour_token.split(":")[:2])
        return by_start.get((row.day_code, time(h, m)))
    except (ValueError, IndexError):
        return None


def _fail(
    db: AsyncSession, batch_id: uuid.UUID, school_id: uuid.UUID, row: ParsedTimetableRow, msg: str,
    results: list[ImportRowResult],
) -> None:
    _log_row(db, batch_id, school_id, row, "error", msg)
    results.append(ImportRowResult(row=row.row_number, ref=_ref(row), status="failed", error=msg))


async def process_import(
    file_bytes: bytes, school_id: uuid.UUID, academic_year_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession,
) -> ImportBatchResult:
    parsed_rows = parse_fet_csv(file_bytes)

    batch = ImportBatch(
        school_id=school_id, import_type="timetable", status=ImportStatus.PROCESSING,
        total_rows=0, processed_rows=0, error_count=0,
        initiated_by_id=user_id, started_at=_utcnow(), created_at=_utcnow(),
    )
    db.add(batch)
    await db.flush()

    class_by_label, label_by_class_id = await _load_class_maps(school_id, db)
    subject_by_name = await _load_subject_map(school_id, db)
    period_by_number, period_by_start = await _load_period_maps(school_id, db)
    teacher_by_class_subject = await _load_teacher_map(school_id, academic_year_id, db)
    booked = await _load_booked(school_id, academic_year_id, db)

    results: list[ImportRowResult] = []
    warnings: list[ImportRowResult] = []
    created = failed = 0

    for row in parsed_rows:
        if row.day_code is None:
            _fail(db, batch.id, school_id, row, f"Unrecognized day '{row.day_raw}'.", results)
            failed += 1
            continue

        class_id = class_by_label.get(row.class_label.strip().lower())
        if class_id is None:
            _fail(
                db, batch.id, school_id, row,
                f"Class '{row.class_label}' not found — check it matches the name shown under Classes.",
                results,
            )
            failed += 1
            continue

        subject_id = subject_by_name.get(row.subject_name.strip().lower())
        if subject_id is None:
            _fail(db, batch.id, school_id, row, f"Subject '{row.subject_name}' not found.", results)
            failed += 1
            continue

        if not await class_subject_exists(class_id, subject_id, school_id, db):
            _fail(
                db, batch.id, school_id, row,
                f"'{row.subject_name}' is not on {row.class_label}'s curriculum — add it there first.",
                results,
            )
            failed += 1
            continue

        period_id = _resolve_period(row, period_by_number, period_by_start)
        if period_id is None:
            _fail(
                db, batch.id, school_id, row,
                f"No period configured for {row.day_raw} hour {row.hour_token} — set up School Periods first.",
                results,
            )
            failed += 1
            continue

        teacher_id = teacher_by_class_subject.get((class_id, subject_id))
        if teacher_id is None:
            _fail(
                db, batch.id, school_id, row,
                f"'{row.subject_name}' has no teacher assigned for {row.class_label} — assign one, then re-import.",
                results,
            )
            failed += 1
            continue

        existing_booking = booked.get((period_id, teacher_id))
        if existing_booking is not None:
            conflict_class_id, conflict_row_number = existing_booking
            # Same class: fine (re-upserting the same slot). A different
            # class from the SAME source CSV line is a deliberate shared/
            # combined activity (see _load_booked's docstring), not a
            # conflict — only a different class from a DIFFERENT line, or
            # from data that already existed before this import, is real.
            same_source_line = conflict_row_number is not None and conflict_row_number == row.row_number
            if conflict_class_id != class_id and not same_source_line:
                other_label = label_by_class_id.get(conflict_class_id, "another class")
                _fail(
                    db, batch.id, school_id, row,
                    f"The teacher for '{row.subject_name}' is already scheduled to teach "
                    f"{other_label} at this same period.",
                    results,
                )
                failed += 1
                continue

        try:
            async with db.begin_nested():
                existing = await db.scalar(
                    select(TimetableSlot).where(
                        TimetableSlot.class_id == class_id,
                        TimetableSlot.period_id == period_id,
                        TimetableSlot.academic_year_id == academic_year_id,
                    )
                )
                if existing:
                    existing.subject_id = subject_id
                    slot = existing
                else:
                    slot = TimetableSlot(
                        school_id=school_id, class_id=class_id, subject_id=subject_id,
                        academic_year_id=academic_year_id, period_id=period_id,
                    )
                    db.add(slot)
                await db.flush()
        except IntegrityError:
            _fail(
                db, batch.id, school_id, row,
                f"{row.class_label} already has a subject in this period from an earlier row in this file.",
                results,
            )
            failed += 1
            continue

        booked[(period_id, teacher_id)] = (class_id, row.row_number)
        _log_row(db, batch.id, school_id, row, "success", None, slot.id)
        results.append(ImportRowResult(row=row.row_number, ref=_ref(row), status="created", error=None))
        created += 1
        if row.extra_teacher_names:
            warnings.append(ImportRowResult(
                row=row.row_number, ref=_ref(row), status="created", error=None,
                warning=f"Multiple teachers listed ({', '.join(row.extra_teacher_names)}); only the first was used.",
            ))

    batch.total_rows = created + failed
    batch.processed_rows = created + failed
    batch.error_count = failed
    batch.status = (
        ImportStatus.COMPLETED if failed == 0
        else ImportStatus.PARTIAL if created > 0
        else ImportStatus.FAILED
    )
    batch.completed_at = _utcnow()
    await db.flush()

    return ImportBatchResult(
        batch_id=batch.id, total_rows=created + failed, created=created, failed=failed,
        errors=[r for r in results if r.status == "failed"], warnings=warnings,
    )


def _log_row(
    db: AsyncSession, batch_id: uuid.UUID, school_id: uuid.UUID, row: ParsedTimetableRow,
    status: str, error_message: str | None, entity_id: uuid.UUID | None = None,
) -> None:
    db.add(ImportRow(
        school_id=school_id, batch_id=batch_id, row_number=row.row_number,
        raw_data={k: (str(v) if v is not None else None) for k, v in row.raw.items()},
        status=status, error_message=error_message, entity_id=entity_id,
    ))
