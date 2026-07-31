"""Admin and finance dashboard views."""
from __future__ import annotations
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class, SHSProgramme
from app.models.assessments import Assessment, Score
from app.models.attendance import AttendanceRecord, AttendanceStatus, SchoolCalendar
from app.models.fees import FeePayment, StudentFeeSummary
from app.models.school import School
from app.models.students import StudentClassAssignment, TermEnrollment
from app.schemas.dashboard import (
    AdminDashboard,
    ClassAttendanceLine,
    FinanceDashboard,
)
from app.services.student_display import _class_display_name


def _class_label(cls: Class, prog_name: str | None) -> str:
    return _class_display_name(cls.level, cls.year_group, prog_name, cls.stream)


async def _current_term(school_id: uuid.UUID, db: AsyncSession) -> AcademicTerm | None:
    return await db.scalar(
        select(AcademicTerm).where(
            AcademicTerm.school_id == school_id,
            AcademicTerm.is_current.is_(True),
        )
    )


async def finance_view(
    school_id: uuid.UUID,
    greeting_name: str,
    db: AsyncSession,
) -> FinanceDashboard:
    zero = Decimal("0.00")
    term = await _current_term(school_id, db)
    if not term:
        return FinanceDashboard(
            greeting_name=greeting_name,
            term_expected=zero, term_collected=zero,
            collection_pct=0.0, payments_today=0, outstanding_students=0,
        )

    totals = (await db.execute(
        select(func.sum(StudentFeeSummary.total_due), func.sum(StudentFeeSummary.total_paid))
        .where(StudentFeeSummary.school_id == school_id, StudentFeeSummary.academic_term_id == term.id)
    )).one()
    expected: Decimal = totals[0] or zero
    collected: Decimal = totals[1] or zero
    pct = round(float(collected / expected * 100), 1) if expected else 0.0

    payments_today = await db.scalar(
        select(func.count(FeePayment.id)).where(
            FeePayment.school_id == school_id,
            FeePayment.payment_date == date.today(),
        )
    ) or 0

    outstanding = await db.scalar(
        select(func.count(StudentFeeSummary.id)).where(
            StudentFeeSummary.school_id == school_id,
            StudentFeeSummary.academic_term_id == term.id,
            StudentFeeSummary.total_paid < StudentFeeSummary.total_due,
        )
    ) or 0

    return FinanceDashboard(
        greeting_name=greeting_name,
        term_expected=expected, term_collected=collected,
        collection_pct=pct, payments_today=payments_today,
        outstanding_students=outstanding,
    )


async def admin_view(
    school_id: uuid.UUID,
    greeting_name: str,
    db: AsyncSession,
) -> AdminDashboard:
    zero = Decimal("0.00")
    school = await db.get(School, school_id)
    term = await _current_term(school_id, db)

    if not term:
        return AdminDashboard(
            greeting_name=greeting_name,
            school_name=school.name if school else "",
            total_students=0, today_present=0, today_total=0,
            attendance_pct=0.0, term_collection_pct=0.0,
            term_collected=zero, term_expected=zero,
            pending_approvals=0, class_attendance=[],
        )

    total_students = await db.scalar(
        select(func.count(TermEnrollment.id)).where(
            TermEnrollment.school_id == school_id,
            TermEnrollment.academic_term_id == term.id,
            TermEnrollment.is_active.is_(True),
        )
    ) or 0

    today_cal: SchoolCalendar | None = await db.scalar(
        select(SchoolCalendar).where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.date == date.today(),
        )
    )

    class_rows = await db.execute(
        select(Class, func.count(StudentClassAssignment.id).label("total"))
        .join(StudentClassAssignment, StudentClassAssignment.class_id == Class.id)
        .where(
            Class.school_id == school_id,
            StudentClassAssignment.academic_year_id == term.academic_year_id,
            StudentClassAssignment.is_active.is_(True),
        )
        .group_by(Class.id)
        .order_by(Class.level, Class.year_group)
        .limit(12)
    )

    present_map: dict[uuid.UUID, int] = {}
    if today_cal:
        att = await db.execute(
            select(StudentClassAssignment.class_id, func.count(AttendanceRecord.id).label("n"))
            .join(AttendanceRecord, AttendanceRecord.student_id == StudentClassAssignment.student_id)
            .where(
                AttendanceRecord.school_calendar_id == today_cal.id,
                AttendanceRecord.status == AttendanceStatus.PRESENT,
                AttendanceRecord.period_id.is_(None),
                StudentClassAssignment.academic_year_id == term.academic_year_id,
                StudentClassAssignment.school_id == school_id,
                StudentClassAssignment.is_active.is_(True),
            )
            .group_by(StudentClassAssignment.class_id)
        )
        present_map = {r.class_id: r.n for r in att}

    # class_rows is capped to 12 for the "Attendance by class" widget list — the
    # headline present/total stat must not be derived from that same capped loop,
    # so it's computed separately here across every class in the school.
    today_total = await db.scalar(
        select(func.count(StudentClassAssignment.id)).where(
            StudentClassAssignment.school_id == school_id,
            StudentClassAssignment.academic_year_id == term.academic_year_id,
            StudentClassAssignment.is_active.is_(True),
        )
    ) or 0
    today_present = sum(present_map.values())

    class_lines: list[ClassAttendanceLine] = []
    for cls, total in class_rows:
        prog_name: str | None = None
        if cls.programme_id:
            prog = await db.get(SHSProgramme, cls.programme_id)
            prog_name = prog.name if prog else None
        present = present_map.get(cls.id, 0)
        class_lines.append(ClassAttendanceLine(
            class_id=cls.id,
            name=_class_label(cls, prog_name),
            total=total, present=present,
            pct=round(present / total * 100, 1) if total else 0.0,
        ))

    ft = (await db.execute(
        select(func.sum(StudentFeeSummary.total_due), func.sum(StudentFeeSummary.total_paid))
        .where(StudentFeeSummary.school_id == school_id, StudentFeeSummary.academic_term_id == term.id)
    )).one()
    expected: Decimal = ft[0] or zero
    collected: Decimal = ft[1] or zero

    pending_approvals = await db.scalar(
        select(func.count(Score.id))
        .join(Assessment, Assessment.id == Score.assessment_id)
        .where(
            Score.school_id == school_id,
            Score.is_approved.is_(False),
            Assessment.academic_term_id == term.id,
        )
    ) or 0

    return AdminDashboard(
        greeting_name=greeting_name,
        school_name=school.name if school else "",
        total_students=total_students,
        today_present=today_present, today_total=today_total,
        attendance_pct=round(today_present / today_total * 100, 1) if today_total else 0.0,
        term_collection_pct=round(float(collected / expected * 100), 1) if expected else 0.0,
        term_collected=collected, term_expected=expected,
        pending_approvals=pending_approvals,
        class_attendance=class_lines,
    )
