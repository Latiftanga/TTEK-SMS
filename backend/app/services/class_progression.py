"""
Whether a proposed promotion target class actually continues a student's
existing programme/stream track — "1BUS-A should promote to 2BUS-A, not
2ART-A" — and whether the chosen graduation_type (PROMOTED/REPEATED/DEMOTED)
matches the real relationship between the source and target class.

CLASS LEVEL LADDER
-------------------
Ghana Basic schools ladder Creche -> Nursery -> KG -> Basic 1..9, so "KG 2 ->
Basic 1" is a genuine promotion with a *decreasing* year_group. Comparing raw
year_group alone would reject the single most common Basic-school promotion
in the country — direction must compare the composite (level_rank, year_group)
ordinal below instead.

PROGRAMME/STREAM MATCHING
--------------------------
programme_mismatch()/stream_mismatch() are None-safe: a Basic school class
has programme_id=None on both sides, and Python's None != None is False, so
that comparison is a match, never a mismatch, with no special-casing needed —
this is the exact trap the whole fix exists to avoid getting backwards.

VALIDATION (see validate_promotion_batch)
-------------------------------------------
Two categories, both computed up front before any write (mirrors
student_subject_registration.py's "validate every item up front" precedent):
  - Hard errors (no source class to promote from, wrong graduation_type
    direction) are never overridable — they're not judgment calls, they're
    just wrong.
  - Overridable mismatches (programme, stream) are blocked by default (423)
    unless the caller supplies a non-blank override_reason on the request,
    mirroring core/permissions.py::check_term_lock_override()'s shape.

A retired target class (Class.is_active=False) is excluded from
target_by_id entirely, so it 404s the same as a nonexistent one — promoting
a student into a class that's no longer offered makes no sense.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import Class, SHSProgramme
from app.models.documents import GraduationRecord, GraduationType
from app.models.students import Student
from app.schemas.student_lifecycle import BulkPromoteRequest
from app.services.student_display import _active_class_assignment_subquery, _class_display_name

# Pedagogical order — Class.level is a free-text column, not a DB-enforced
# enum, so plain alphabetical comparison would put "Basic" before "Creche".
# The single source of truth; student_list.py imports this rather than
# keeping its own copy.
CLASS_LEVEL_ORDER = ["Creche", "Nursery", "KG", "Basic", "SHS"]


def level_rank(level: str) -> int:
    try:
        return CLASS_LEVEL_ORDER.index(level)
    except ValueError:
        return -1


def class_ordinal(cls: Class) -> tuple[int, int]:
    return (level_rank(cls.level), cls.year_group)


def expected_graduation_type(source: Class, target: Class) -> GraduationType | None:
    """PROMOTED if target's ordinal is ahead of source's, REPEATED if equal,
    DEMOTED if behind. None if either level isn't on the ladder at all (an
    unrecognized level string) — direction simply isn't comparable, so the
    caller should skip the check rather than guess."""
    s_rank, t_rank = level_rank(source.level), level_rank(target.level)
    if s_rank == -1 or t_rank == -1:
        return None
    source_ord, target_ord = class_ordinal(source), class_ordinal(target)
    if target_ord > source_ord:
        return GraduationType.PROMOTED
    if target_ord == source_ord:
        return GraduationType.REPEATED
    return GraduationType.DEMOTED


def programme_mismatch(source: Class, target: Class) -> bool:
    return source.programme_id != target.programme_id


def stream_mismatch(source: Class, target: Class) -> bool:
    return (source.stream or None) != (target.stream or None)


def _join_capped(messages: list[str], cap: int = 3) -> str:
    shown = messages[:cap]
    text = "; ".join(shown)
    if len(messages) > cap:
        text += f" (+{len(messages) - cap} more)"
    return text


async def validate_promotion_batch(
    req: BulkPromoteRequest,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> dict[uuid.UUID, tuple[uuid.UUID, str | None]]:
    """
    Validates every record in the batch up front, before any write — mirrors
    student_subject_registration.py's "validate every item up front" precedent
    so a mixed batch can never partially apply.

    Raises 422 for hard errors (no active class to promote from, or a
    graduation_type that doesn't match the real relationship between source
    and target class — never overridable, these aren't judgment calls).
    Raises 423 for an overridable programme/stream mismatch with no
    override_reason supplied on the request.

    Returns {student_id: (source_class_id, override_reason_or_None)} for the
    caller's write loop to stamp onto each new GraduationRecord. Students who
    already have a GraduationRecord this year are omitted entirely — they're
    idempotent no-ops in the write loop, and validating them against rules
    that may be stricter than when they were first (successfully) processed
    would break re-posting an already-processed batch.
    """
    student_ids = [r.student_id for r in req.records]
    if not student_ids:
        return {}

    # Every student_id must belong to the calling school before anything else
    # touches it — without this, a cross-school id's active class assignment
    # (level/year_group/programme/stream) could be resolved as its "source"
    # class below and echoed back in a 422/423 message, even though the
    # eventual write is separately blocked by create_class_assignment's own
    # ownership check. Same convention as the target-class check just below.
    owned_student_ids = set(await db.scalars(
        select(Student.id).where(Student.id.in_(student_ids), Student.school_id == school_id)
    ))
    if set(student_ids) - owned_student_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found.")

    already_processed = set(await db.scalars(
        select(GraduationRecord.student_id).where(
            GraduationRecord.student_id.in_(student_ids),
            GraduationRecord.academic_year_id == req.academic_year_id,
            GraduationRecord.school_id == school_id,
        )
    ))
    to_validate = [r for r in req.records if r.student_id not in already_processed]
    if not to_validate:
        return {}

    target_ids = {r.class_id for r in to_validate}
    target_by_id = {c.id: c for c in (await db.scalars(
        select(Class).where(
            Class.id.in_(target_ids), Class.school_id == school_id, Class.is_active.is_(True),
        )
    )).all()}
    if target_ids - target_by_id.keys():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Class not found.")

    # Most recent active assignment per student, excluding this batch's own
    # target year — see _active_class_assignment_subquery()'s docstring for
    # why (an already-created target-year assignment would otherwise be
    # mistaken for the student's own "source").
    active_sca = _active_class_assignment_subquery(exclude_academic_year_id=req.academic_year_id)
    source_by_student: dict[uuid.UUID, Class] = {
        row.student_id: row[1]
        for row in (await db.execute(
            select(active_sca.c.student_id, Class)
            .join(Class, Class.id == active_sca.c.class_id)
            .where(active_sca.c.student_id.in_([r.student_id for r in to_validate]))
        )).all()
    }

    programme_ids = {
        cls.programme_id for cls in [*target_by_id.values(), *source_by_student.values()]
        if cls.programme_id is not None
    }
    programme_names: dict[uuid.UUID, str] = dict((await db.execute(
        select(SHSProgramme.id, SHSProgramme.name).where(SHSProgramme.id.in_(programme_ids))
    )).all()) if programme_ids else {}

    def display(cls: Class) -> str:
        return _class_display_name(cls.level, cls.year_group, programme_names.get(cls.programme_id), cls.stream)

    def programme_label(cls: Class) -> str:
        return programme_names.get(cls.programme_id) or "no programme"

    no_source_count = 0
    direction_groups: dict[tuple, dict] = {}
    mismatch_groups: dict[tuple, dict] = {}
    result: dict[uuid.UUID, tuple[uuid.UUID, str | None]] = {}
    mismatched_student_ids: set[uuid.UUID] = set()

    for item in to_validate:
        source = source_by_student.get(item.student_id)
        if source is None:
            no_source_count += 1
            continue
        target = target_by_id[item.class_id]

        expected = expected_graduation_type(source, target)
        if expected is not None and expected != item.graduation_type:
            key = (source.id, target.id, item.graduation_type, expected)
            group = direction_groups.setdefault(key, {
                "source": source, "target": target,
                "actual": item.graduation_type, "expected": expected, "count": 0,
            })
            group["count"] += 1
            continue

        result[item.student_id] = (source.id, None)
        prog, strm = programme_mismatch(source, target), stream_mismatch(source, target)
        if prog or strm:
            mismatched_student_ids.add(item.student_id)
            key = (source.id, target.id)
            group = mismatch_groups.setdefault(key, {
                "source": source, "target": target, "programme": False, "stream": False, "count": 0,
            })
            group["programme"] = group["programme"] or prog
            group["stream"] = group["stream"] or strm
            group["count"] += 1

    hard_messages: list[str] = []
    if no_source_count:
        hard_messages.append(
            f"{no_source_count} student(s) have no active class assignment to promote from "
            "— assign them a class first."
        )
    for group in direction_groups.values():
        hard_messages.append(
            f"'{display(group['source'])}' → '{display(group['target'])}' is "
            f"{group['expected'].value.lower()}, not {group['actual'].value.lower()} — "
            f"set graduation_type to {group['expected'].value} ({group['count']} student(s))."
        )
    if hard_messages:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, _join_capped(hard_messages))

    if mismatch_groups:
        reason = (req.override_reason or "").strip()
        if not reason:
            messages = []
            for group in mismatch_groups.values():
                parts = []
                if group["programme"]:
                    parts.append(
                        f"{programme_label(group['source'])} cannot be promoted into "
                        f"{programme_label(group['target'])}"
                    )
                if group["stream"]:
                    parts.append(
                        f"stream {group['source'].stream or '—'} cannot be promoted into "
                        f"stream {group['target'].stream or '—'}"
                    )
                messages.append(
                    f"{' and '.join(parts)} — {group['count']} student(s) moving "
                    f"{display(group['source'])} → {display(group['target'])}. "
                    "Supply an override_reason to proceed."
                )
            raise HTTPException(status.HTTP_423_LOCKED, _join_capped(messages))
        for student_id in mismatched_student_ids:
            source_id, _ = result[student_id]
            result[student_id] = (source_id, reason)

    return result
