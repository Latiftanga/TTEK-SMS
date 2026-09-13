"""
Class timetable service — a class's weekly slot grid.

A TimetableSlot is "this class has this subject during this bell period this
year"; day_of_week/start_time/end_time are read by joining SchoolPeriod, and
the teacher by joining SubjectTeacher on (class_id, subject_id,
academic_year_id) — never duplicated onto the slot itself.

A slot is keyed by (class_id, period_id, academic_year_id), so assigning a
class's cell is naturally an upsert — one subject per class per period per
year, with no separate "class double-booking" check needed beyond that key.
Teacher double-booking (the same teacher already scheduled into a different
class at the same period) is checked explicitly in upsert_timetable_slot.

A teacher's own weekly schedule ("what do I teach tomorrow?") is a distinct
concern split out into services/my_schedule.py.

upsert_timetable_slot() auto-creates whatever curriculum (ClassSubject) and
teacher (SubjectTeacher) records a slot needs but doesn't already have —
scheduling a subject into a class's timetable is itself the deliberate
statement that the class studies it and who teaches it, so there's no
separate "add this subject to the curriculum first" or "assign a teacher
first" step required before transcribing a printed timetable slot by slot.
The bulk CSV import path (services/timetable_import.py) is intentionally
stricter and unaffected by this — it still requires both to already exist,
since a whole-school import creating curriculum/teacher records as a side
effect of a CSV cell would be much harder to review before it happens.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import Class, ClassSubject, SHSProgramme, Subject, SubjectTeacher, TimetableSlot
from app.models.attendance import SchoolPeriod
from app.models.staff import StaffMember
from app.schemas.timetable import TimetableSlotRead, TimetableSlotUpsert
from app.services.academic_class import get_active_class
from app.services.academic_teachers import _assert_staff_owned, _upsert_subject_teacher_row
from app.services.staff import _display_name as _staff_display_name
from app.services.student_display import _class_display_name
from app.services.subject_roster import class_subject_exists, subject_teacher_assigned


async def _resolve_teacher_id(
    class_id: uuid.UUID, subject_id: uuid.UUID, academic_year_id: uuid.UUID, db: AsyncSession,
) -> uuid.UUID | None:
    return await db.scalar(
        select(SubjectTeacher.staff_member_id).where(
            SubjectTeacher.class_id == class_id,
            SubjectTeacher.subject_id == subject_id,
            SubjectTeacher.academic_year_id == academic_year_id,
            SubjectTeacher.is_active.is_(True),
        )
    )


async def _class_label(cls: Class, db: AsyncSession) -> str:
    prog_name = None
    if cls.programme_id:
        prog = await db.get(SHSProgramme, cls.programme_id)
        prog_name = prog.name if prog else None
    return _class_display_name(cls.level, cls.year_group, prog_name, cls.stream)


async def get_class_timetable(
    class_id: uuid.UUID, academic_year_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession,
) -> list[TimetableSlotRead]:
    """Every slot assigned to this class this year — the frontend merges
    this with the already-fetched period list to render a full grid with
    empty cells for periods that aren't timetabled yet."""
    cls = await db.get(Class, class_id)
    if not cls or cls.school_id != school_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Class not found.")

    slots = list(await db.scalars(
        select(TimetableSlot).where(
            TimetableSlot.class_id == class_id,
            TimetableSlot.academic_year_id == academic_year_id,
            TimetableSlot.school_id == school_id,
        )
    ))
    if not slots:
        return []

    subject_ids = {s.subject_id for s in slots}
    subjects_by_id = {
        s.id: s.name
        for s in await db.scalars(select(Subject).where(Subject.id.in_(subject_ids)))
    }
    teacher_rows = await db.execute(
        select(
            SubjectTeacher.subject_id, SubjectTeacher.staff_member_id,
            StaffMember.first_name, StaffMember.middle_name, StaffMember.last_name,
        )
        .join(StaffMember, StaffMember.id == SubjectTeacher.staff_member_id)
        .where(
            SubjectTeacher.class_id == class_id,
            SubjectTeacher.academic_year_id == academic_year_id,
            SubjectTeacher.subject_id.in_(subject_ids),
            SubjectTeacher.is_active.is_(True),
        )
    )
    teacher_by_subject = {
        subject_id: (staff_id, _staff_display_name(first, middle, last))
        for subject_id, staff_id, first, middle, last in teacher_rows
    }
    return [
        TimetableSlotRead(
            period_id=s.period_id,
            subject_id=s.subject_id,
            subject_name=subjects_by_id.get(s.subject_id, "—"),
            staff_member_id=teacher_by_subject.get(s.subject_id, (None, None))[0],
            teacher_name=teacher_by_subject.get(s.subject_id, (None, None))[1],
        )
        for s in slots
    ]


async def upsert_timetable_slot(
    class_id: uuid.UUID,
    period_id: uuid.UUID,
    req: TimetableSlotUpsert,
    academic_year_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> TimetableSlotRead:
    await get_active_class(class_id, school_id, db)

    period = await db.get(SchoolPeriod, period_id)
    if not period or period.school_id != school_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Period not found.")

    subject = await db.get(Subject, req.subject_id)
    if not subject or subject.school_id != school_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subject not found.")

    if not await class_subject_exists(class_id, req.subject_id, school_id, db):
        # Scheduling a subject into this class's timetable is itself a
        # deliberate statement that the class studies it — auto-add it to
        # the curriculum (defaulting Core, same as assign_subjects()'s own
        # default) instead of requiring a separate "Add subject" step first.
        # Mirrors the SubjectTeacher auto-upsert below for the same reason:
        # the timetable transcription IS the curriculum decision for a
        # school building it from a printed FET/aSc export.
        db.add(ClassSubject(school_id=school_id, class_id=class_id, subject_id=req.subject_id, is_active=True))
        await db.flush()

    if req.staff_member_id is not None:
        # A teacher was picked right here (the class-detail Timetable tab's
        # combined subject+teacher slot editor) — upsert SubjectTeacher in
        # the same transaction as the slot below, rather than requiring a
        # separate prior call. This is a year-level assignment (see
        # SubjectTeacher's model docstring): it also updates every other
        # period this subject occupies on this class's timetable, not just
        # this one.
        await _assert_staff_owned(req.staff_member_id, school_id, db)
        await _upsert_subject_teacher_row(
            class_id, req.subject_id, req.staff_member_id, academic_year_id, school_id, db,
        )
    elif not await subject_teacher_assigned(class_id, req.subject_id, academic_year_id, school_id, db):
        # Mirrors 12at's "who will teach the student" precedent for subject
        # registration — a subject can't be timetabled until someone
        # actually teaches it.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "This subject has no teacher assigned for this class yet — pick a teacher below before saving.",
            headers={"X-Error-Code": "no_teacher_assigned"},
        )

    teacher_id = await _resolve_teacher_id(class_id, req.subject_id, academic_year_id, db)

    # Teacher double-booking: is this same teacher already scheduled into a
    # DIFFERENT class at this exact period this year?
    other_slots = await db.execute(
        select(TimetableSlot.class_id, TimetableSlot.subject_id).where(
            TimetableSlot.school_id == school_id,
            TimetableSlot.academic_year_id == academic_year_id,
            TimetableSlot.period_id == period_id,
            TimetableSlot.class_id != class_id,
        )
    )
    for other_class_id, other_subject_id in other_slots:
        other_teacher_id = await _resolve_teacher_id(other_class_id, other_subject_id, academic_year_id, db)
        if teacher_id is not None and other_teacher_id == teacher_id:
            other_cls = await db.get(Class, other_class_id)
            other_name = await _class_label(other_cls, db) if other_cls else "another class"
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"This teacher is already scheduled to teach {other_name} at this same period.",
            )

    existing = await db.scalar(
        select(TimetableSlot).where(
            TimetableSlot.class_id == class_id,
            TimetableSlot.period_id == period_id,
            TimetableSlot.academic_year_id == academic_year_id,
        )
    )
    if existing:
        existing.subject_id = req.subject_id
        slot = existing
    else:
        slot = TimetableSlot(
            school_id=school_id,
            class_id=class_id,
            subject_id=req.subject_id,
            academic_year_id=academic_year_id,
            period_id=period_id,
        )
        db.add(slot)
    await db.flush()

    teacher_name = None
    if teacher_id:
        staff = await db.get(StaffMember, teacher_id)
        if staff:
            teacher_name = _staff_display_name(staff.first_name, staff.middle_name, staff.last_name)
    return TimetableSlotRead(
        period_id=period_id,
        subject_id=req.subject_id,
        subject_name=subject.name,
        staff_member_id=teacher_id,
        teacher_name=teacher_name,
    )


async def delete_timetable_slot(
    class_id: uuid.UUID,
    period_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    slot = await db.scalar(
        select(TimetableSlot).where(
            TimetableSlot.class_id == class_id,
            TimetableSlot.period_id == period_id,
            TimetableSlot.academic_year_id == academic_year_id,
            TimetableSlot.school_id == school_id,
        )
    )
    if not slot:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No timetable slot to remove.")
    await db.delete(slot)
    await db.flush()
