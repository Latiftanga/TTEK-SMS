"""
Chronic-absenteeism early warning.

TIERS (term-to-date attendance rate, only computed once at least
MIN_MARKABLE_DAYS have elapsed in the term — a 2-day-old term's percentage
is noise, not signal):

  WATCH    rate < 95%  (missing ~5%+) — dashboard-visible only, no guardian
                        contact. Research backs flagging risk well before the
                        traditional 10% "chronic absenteeism" threshold, but
                        alerting a guardian on a soft signal risks fatigue.
  AT_RISK  rate < 90%  (missing 10%+) — guardian SMS+email once per crossing.
  SEVERE   rate < 80%  (missing 20%+) — guardian SMS+email once per crossing,
                        a distinct stronger message.

AttendanceRiskAlert stores the highest tier already notified per
(student, term) so a guardian isn't re-alerted on every subsequent absence
within the same tier — only an actual tier increase fires again.

Separately, a CONSECUTIVE-ABSENCE trigger (3 markable school days in a row,
all ABSENT) fires an immediate guardian alert independent of the cumulative
tiers — research flags a short run of consecutive absences as an earlier,
stronger signal than a slow percentage drift, and it needs no term-to-date
history to be meaningful.
"""
from __future__ import annotations
import uuid
from datetime import date as _date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.teacher_scope import classes_for_scope, resolve_attendance_scope, year_for_term
from app.models.academic import AcademicTerm
from app.models.attendance import (
    AttendanceRecord, AttendanceRiskAlert, AttendanceRiskTier, AttendanceStatus, SchoolCalendar,
)
from app.models.students import Student, StudentClassAssignment
from app.schemas.attendance_risk import AtRiskStudentRead
from app.services import email_notifications as email_svc
from app.services import sms_notifications as sms_svc
from app.services.attendance_stats import MARKABLE_DAY_TYPES
from app.services.student_display import _class_display_name, _display_name, _get_class_map

MIN_MARKABLE_DAYS = 10

_TIER_ORDER = [AttendanceRiskTier.WATCH, AttendanceRiskTier.AT_RISK, AttendanceRiskTier.SEVERE]


def compute_risk_tier(present: int, total: int) -> AttendanceRiskTier | None:
    if total < MIN_MARKABLE_DAYS:
        return None
    rate = present / total * 100
    if rate < 80:
        return AttendanceRiskTier.SEVERE
    if rate < 90:
        return AttendanceRiskTier.AT_RISK
    if rate < 95:
        return AttendanceRiskTier.WATCH
    return None


async def _stats_as_of(
    student_id: uuid.UUID, term_id: uuid.UUID, as_of_date: _date, school_id: uuid.UUID, db: AsyncSession,
) -> tuple[int, int]:
    """(days_present, total_markable_days) for this term, counting only
    calendar days up to and including as_of_date.

    Deliberately NOT attendance_stats.py::compute_attendance_stats() — that
    function's "total" is the WHOLE term's calendar (correct for a report
    card, generated after the fact), but generate_calendar() creates every
    day of a term up front, so using the whole-term total here would make a
    single absence in week 1 look like the student missed nearly the entire
    term, mis-triggering SEVERE on day one — a false alarm that (by design)
    can never be un-escalated even as the student's real rate improves.
    """
    markable = [t.value for t in MARKABLE_DAY_TYPES]
    total = await db.scalar(
        select(func.count()).select_from(SchoolCalendar).where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.academic_term_id == term_id,
            SchoolCalendar.day_type.in_(markable),
            SchoolCalendar.date <= as_of_date,
        )
    ) or 0
    present = await db.scalar(
        select(func.count())
        .select_from(AttendanceRecord)
        .join(SchoolCalendar, SchoolCalendar.id == AttendanceRecord.school_calendar_id)
        .where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.school_id == school_id,
            AttendanceRecord.status == AttendanceStatus.PRESENT,
            AttendanceRecord.period_id.is_(None),
            SchoolCalendar.academic_term_id == term_id,
            SchoolCalendar.day_type.in_(markable),
            SchoolCalendar.date <= as_of_date,
        )
    ) or 0
    return present, total


async def check_and_notify_risk(
    student_ids: list[uuid.UUID], term_id: uuid.UUID, as_of_date: _date,
    school_id: uuid.UUID, db: AsyncSession,
) -> None:
    """Recompute risk as of as_of_date for each student and notify the
    guardian only on an actual tier increase (WATCH is dashboard-only,
    never notified)."""
    school = None
    for student_id in set(student_ids):
        present, total = await _stats_as_of(student_id, term_id, as_of_date, school_id, db)
        tier = compute_risk_tier(present, total)
        if tier not in (AttendanceRiskTier.AT_RISK, AttendanceRiskTier.SEVERE):
            continue

        existing = await db.scalar(
            select(AttendanceRiskAlert).where(
                AttendanceRiskAlert.student_id == student_id,
                AttendanceRiskAlert.academic_term_id == term_id,
            )
        )
        if existing and _TIER_ORDER.index(existing.tier) >= _TIER_ORDER.index(tier):
            continue  # already alerted at this tier or higher

        now = datetime.now(timezone.utc)
        if existing:
            existing.tier = tier
            existing.alerted_at = now
            alert = existing
        else:
            alert = AttendanceRiskAlert(
                school_id=school_id, student_id=student_id, academic_term_id=term_id,
                tier=tier, alerted_at=now,
            )
            db.add(alert)
        await db.flush()

        if school is None:
            from app.models.school import School
            school = await db.get(School, school_id)
        school_short = (school.short_name or school.name) if school else ""
        rate = round(present / total * 100, 1) if total else 0.0
        await sms_svc.notify_attendance_risk(
            student_id=student_id, school_id=school_id, school_short=school_short,
            tier=tier.value, rate=rate, entity_id=alert.id, db=db,
        )
        await email_svc.notify_attendance_risk_email(
            student_id=student_id, school_id=school_id, school_short=school_short,
            tier=tier.value, rate=rate, entity_id=alert.id, db=db,
        )


async def check_consecutive_absences(
    student_id: uuid.UUID, calendar_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession,
) -> bool:
    """True iff the last 3 markable school days up to and including
    calendar_id's date are ALL marked ABSENT for this student."""
    cal = await db.get(SchoolCalendar, calendar_id)
    if not cal:
        return False
    last3_ids = list(await db.scalars(
        select(SchoolCalendar.id)
        .where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.day_type.in_([t.value for t in MARKABLE_DAY_TYPES]),
            SchoolCalendar.date <= cal.date,
        )
        .order_by(SchoolCalendar.date.desc())
        .limit(3)
    ))
    if len(last3_ids) < 3:
        return False
    absent_count = await db.scalar(
        select(func.count())
        .select_from(AttendanceRecord)
        .where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.school_calendar_id.in_(last3_ids),
            AttendanceRecord.status == AttendanceStatus.ABSENT,
            AttendanceRecord.period_id.is_(None),
        )
    ) or 0
    return absent_count == 3


async def list_at_risk(
    term_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession,
) -> list[AtRiskStudentRead]:
    term = await db.scalar(
        select(AcademicTerm).where(AcademicTerm.id == term_id, AcademicTerm.school_id == school_id)
    )
    if not term:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Academic term not found.")

    year_id = await year_for_term(term_id, db)
    scope = await resolve_attendance_scope(user_id, year_id, db) if year_id is not None else None
    classes = await classes_for_scope(scope, school_id, db)
    if not classes or year_id is None:
        return []
    class_ids = [c.id for c in classes]
    today = _date.today()

    # Scoped to date <= today, not the whole term's calendar (which
    # generate_calendar() creates up front) — see _stats_as_of()'s docstring
    # for why counting future days would make an early-term absence look
    # far worse than it really is.
    total_days = await db.scalar(
        select(func.count()).select_from(SchoolCalendar).where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.academic_term_id == term_id,
            SchoolCalendar.day_type.in_([t.value for t in MARKABLE_DAY_TYPES]),
            SchoolCalendar.date <= today,
        )
    ) or 0
    if total_days < MIN_MARKABLE_DAYS:
        return []

    active_student_ids = set(await db.scalars(
        select(StudentClassAssignment.student_id).where(
            StudentClassAssignment.class_id.in_(class_ids),
            StudentClassAssignment.academic_year_id == year_id,
            StudentClassAssignment.is_active.is_(True),
        )
    ))
    if not active_student_ids:
        return []

    present_rows = await db.execute(
        select(
            AttendanceRecord.student_id,
            func.sum(case((AttendanceRecord.status == AttendanceStatus.PRESENT, 1), else_=0)).label("present"),
        )
        .join(SchoolCalendar, SchoolCalendar.id == AttendanceRecord.school_calendar_id)
        .where(
            AttendanceRecord.student_id.in_(active_student_ids),
            AttendanceRecord.school_id == school_id,
            AttendanceRecord.period_id.is_(None),
            SchoolCalendar.academic_term_id == term_id,
            SchoolCalendar.day_type.in_([t.value for t in MARKABLE_DAY_TYPES]),
            SchoolCalendar.date <= today,
        )
        .group_by(AttendanceRecord.student_id)
    )
    present_map = {r.student_id: r.present or 0 for r in present_rows}

    class_map = await _get_class_map(list(active_student_ids), db)
    name_rows = await db.execute(
        select(Student.id, Student.first_name, Student.middle_name, Student.last_name)
        .where(Student.id.in_(active_student_ids))
    )
    name_map = {r.id: _display_name(r.first_name, r.middle_name, r.last_name) for r in name_rows}

    result: list[AtRiskStudentRead] = []
    for sid in active_student_ids:
        present = present_map.get(sid, 0)
        tier = compute_risk_tier(present, total_days)
        if tier is None:
            continue
        level, year_group, programme, stream, class_id = class_map.get(sid, (None, 0, None, None, None))
        class_name = _class_display_name(level, year_group, programme, stream) if level else None
        result.append(AtRiskStudentRead(
            student_id=sid, name=name_map.get(sid, "Unknown"),
            class_id=class_id, class_name=class_name,
            present=present, total=total_days,
            rate=round(present / total_days * 100, 1),
            tier=tier,
        ))

    result.sort(key=lambda r: (-_TIER_ORDER.index(r.tier), r.rate))
    return result
