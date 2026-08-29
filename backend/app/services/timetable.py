"""
Class timetable service — "what do I teach tomorrow?"

A TimetableSlot is "this class has this subject during this bell period this
year"; day_of_week/start_time/end_time are read by joining SchoolPeriod, and
the teacher by joining SubjectTeacher on (class_id, subject_id,
academic_year_id) — never duplicated onto the slot itself.

A slot is keyed by (class_id, period_id, academic_year_id), so assigning a
class's cell is naturally an upsert — one subject per class per period per
year, with no separate "class double-booking" check needed beyond that key.
Teacher double-booking (the same teacher already scheduled into a different
class at the same period) is checked explicitly in upsert_timetable_slot.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import Class, SHSProgramme, Subject, SubjectTeacher, TimetableSlot
from app.models.attendance import DayOfWeek, SchoolPeriod
from app.models.staff import StaffMember
from app.schemas.timetable import ScheduleEntry, TimetableSlotRead, TimetableSlotUpsert
from app.services.academic_class import get_active_class
from app.services.academic_year import get_current_year
from app.services.staff import _display_name as _staff_display_name
from app.services.student_display import _class_display_name
from app.services.subject_roster import class_subject_exists, subject_teacher_assigned

_DAY_ORDER = {d: i for i, d in enumerate(DayOfWeek)}


async def _staff_member_id_for(user_id: uuid.UUID, db: AsyncSession) -> uuid.UUID | None:
    """Duplicated rather than imported — matches the established convention
    in core/teacher_scope.py/student_scope.py/housing_scope.py, each of
    which keeps its own private copy instead of cross-importing another
    module's underscore-prefixed helper."""
    from app.models.auth import User

    user = await db.get(User, user_id)
    if not user or user.is_superadmin:
        return None
    return user.staff_member_id


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
        select(SubjectTeacher.subject_id, StaffMember.first_name, StaffMember.middle_name, StaffMember.last_name)
        .join(StaffMember, StaffMember.id == SubjectTeacher.staff_member_id)
        .where(
            SubjectTeacher.class_id == class_id,
            SubjectTeacher.academic_year_id == academic_year_id,
            SubjectTeacher.subject_id.in_(subject_ids),
            SubjectTeacher.is_active.is_(True),
        )
    )
    teacher_by_subject = {
        subject_id: _staff_display_name(first, middle, last)
        for subject_id, first, middle, last in teacher_rows
    }
    return [
        TimetableSlotRead(
            period_id=s.period_id,
            subject_id=s.subject_id,
            subject_name=subjects_by_id.get(s.subject_id, "—"),
            teacher_name=teacher_by_subject.get(s.subject_id),
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

    if not await class_subject_exists(class_id, req.subject_id, school_id, db):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That subject is not on this class's curriculum.")

    # Mirrors 12at's "who will teach the student" precedent for subject
    # registration — a subject can't be timetabled until someone actually
    # teaches it.
    if not await subject_teacher_assigned(class_id, req.subject_id, academic_year_id, school_id, db):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "This subject has no teacher assigned for this class yet — assign one before timetabling it.",
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

    subject = await db.get(Subject, req.subject_id)
    teacher_name = None
    if teacher_id:
        staff = await db.get(StaffMember, teacher_id)
        if staff:
            teacher_name = _staff_display_name(staff.first_name, staff.middle_name, staff.last_name)
    return TimetableSlotRead(
        period_id=period_id,
        subject_id=req.subject_id,
        subject_name=subject.name if subject else "—",
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


async def get_my_schedule(
    staff_id: uuid.UUID, academic_year_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession,
) -> list[ScheduleEntry]:
    """The caller's own full weekly schedule (every day at once — a
    timetable is a recurring structure, not date-specific), derived from
    their own active SubjectTeacher rows this year. Serves both the "My
    Timetable" page and the dashboard's "tomorrow" card, which filters this
    same list to tomorrow's weekday."""
    rows = await db.execute(
        select(
            SchoolPeriod.day_of_week, SchoolPeriod.start_time, SchoolPeriod.end_time,
            TimetableSlot.class_id, TimetableSlot.subject_id,
        )
        .select_from(TimetableSlot)
        .join(
            SubjectTeacher,
            (SubjectTeacher.class_id == TimetableSlot.class_id)
            & (SubjectTeacher.subject_id == TimetableSlot.subject_id)
            & (SubjectTeacher.academic_year_id == TimetableSlot.academic_year_id),
        )
        .join(SchoolPeriod, SchoolPeriod.id == TimetableSlot.period_id)
        .where(
            TimetableSlot.school_id == school_id,
            TimetableSlot.academic_year_id == academic_year_id,
            SubjectTeacher.staff_member_id == staff_id,
            SubjectTeacher.is_active.is_(True),
        )
    )
    rows = list(rows)
    if not rows:
        return []

    class_ids = {r.class_id for r in rows}
    subject_ids = {r.subject_id for r in rows}
    class_rows = await db.execute(
        select(Class, SHSProgramme.name.label("prog_name"))
        .outerjoin(SHSProgramme, Class.programme_id == SHSProgramme.id)
        .where(Class.id.in_(class_ids))
    )
    classes_by_id = {
        cls.id: _class_display_name(cls.level, cls.year_group, prog_name, cls.stream)
        for cls, prog_name in class_rows
    }
    subjects_by_id = {
        s.id: s.name for s in await db.scalars(select(Subject).where(Subject.id.in_(subject_ids)))
    }

    entries = [
        ScheduleEntry(
            day_of_week=r.day_of_week, start_time=r.start_time, end_time=r.end_time,
            class_id=r.class_id, class_name=classes_by_id.get(r.class_id, "—"),
            subject_id=r.subject_id, subject_name=subjects_by_id.get(r.subject_id, "—"),
        )
        for r in rows
    ]
    entries.sort(key=lambda e: (_DAY_ORDER[e.day_of_week], e.start_time))
    return entries


async def resolve_my_schedule(
    user_id: uuid.UUID, academic_year_id: uuid.UUID | None, school_id: uuid.UUID, db: AsyncSession,
) -> list[ScheduleEntry]:
    """Router-facing entrypoint for get_my_schedule() — resolves the caller's
    staff_member_id and defaults academic_year_id to the school's current
    year when omitted."""
    resolved_year_id = academic_year_id
    if resolved_year_id is None:
        year = await get_current_year(school_id, db)
        if year is None:
            return []
        resolved_year_id = year.id
    staff_id = await _staff_member_id_for(user_id, db)
    if staff_id is None:
        return []
    return await get_my_schedule(staff_id, resolved_year_id, school_id, db)
