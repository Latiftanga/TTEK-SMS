"""Dashboard service — role-detection and role-specific views.

Admin and finance views live in dashboard_admin.py to respect the 300-line limit.
"""
from __future__ import annotations
import uuid
from datetime import date  # noqa: F401 (used in submodule)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import resolve_permissions
from app.models.academic import AcademicTerm, Class, ClassTeacher, SHSProgramme
from app.models.assessments import Assessment, Score
from app.models.attendance import AttendanceRecord, AttendanceStatus, SchoolCalendar
from app.models.auth import User
from app.models.staff import StaffMember
from app.models.students import Student, StudentClassAssignment, TermEnrollment
from app.schemas.dashboard import (
    AbsentStudent,
    ClassSnapshot,
    ApproverDashboard,
    DashboardData,
    HousemasterDashboard,
    TeacherDashboard,
)
from app.services.academic_class import _display_name
from app.services.dashboard_admin import admin_view, finance_view


def _class_label(cls: Class, prog_name: str | None) -> str:
    return _display_name(cls.level, cls.year_group, prog_name, cls.stream)


async def _current_term(school_id: uuid.UUID, db: AsyncSession) -> AcademicTerm | None:
    return await db.scalar(
        select(AcademicTerm).where(
            AcademicTerm.school_id == school_id,
            AcademicTerm.is_current.is_(True),
        )
    )


async def _teacher_view(
    school_id: uuid.UUID,
    staff_id: uuid.UUID,
    greeting_name: str,
    db: AsyncSession,
) -> TeacherDashboard:
    today_iso = date.today().isoformat()
    term = await _current_term(school_id, db)
    if not term:
        return TeacherDashboard(
            greeting_name=greeting_name, today_iso=today_iso,
            my_class=None, pending_score_assessments=0,
        )

    ct = await db.scalar(
        select(ClassTeacher).where(
            ClassTeacher.staff_member_id == staff_id,
            ClassTeacher.academic_term_id == term.id,
            ClassTeacher.is_active.is_(True),
        )
    )
    if not ct:
        return TeacherDashboard(
            greeting_name=greeting_name, today_iso=today_iso,
            my_class=None, pending_score_assessments=0,
        )

    cls = await db.get(Class, ct.class_id)
    prog_name: str | None = None
    if cls and cls.programme_id:
        prog = await db.get(SHSProgramme, cls.programme_id)
        prog_name = prog.name if prog else None

    student_count = await db.scalar(
        select(func.count(StudentClassAssignment.id)).where(
            StudentClassAssignment.class_id == ct.class_id,
            StudentClassAssignment.academic_year_id == term.academic_year_id,
            StudentClassAssignment.is_active.is_(True),
        )
    ) or 0

    today_cal: SchoolCalendar | None = await db.scalar(
        select(SchoolCalendar).where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.date == date.today(),
        )
    )

    absent_students: list[AbsentStudent] = []
    present_count = 0

    if today_cal:
        rows = await db.execute(
            select(
                AttendanceRecord.status,
                Student.id, Student.first_name,
                Student.last_name, Student.admission_number,
            )
            .join(Student, Student.id == AttendanceRecord.student_id)
            .join(
                StudentClassAssignment,
                StudentClassAssignment.student_id == AttendanceRecord.student_id,
            )
            .where(
                AttendanceRecord.school_calendar_id == today_cal.id,
                AttendanceRecord.period_id.is_(None),
                StudentClassAssignment.class_id == ct.class_id,
                StudentClassAssignment.academic_year_id == term.academic_year_id,
            )
        )
        for row in rows:
            if row.status == AttendanceStatus.PRESENT:
                present_count += 1
            elif row.status == AttendanceStatus.ABSENT:
                absent_students.append(AbsentStudent(
                    id=row.id,
                    name=f"{row.first_name} {row.last_name}",
                    admission_number=row.admission_number,
                ))

    pending = await db.scalar(
        select(func.count(Assessment.id)).where(
            Assessment.class_id == ct.class_id,
            Assessment.academic_term_id == term.id,
            Assessment.is_published.is_(False),
        )
    ) or 0

    attendance_marked = bool(today_cal and (present_count + len(absent_students)) > 0)
    snapshot = ClassSnapshot(
        id=cls.id,
        name=_class_label(cls, prog_name),
        student_count=student_count,
        present_today=present_count,
        absent_today=len(absent_students),
        attendance_marked_today=attendance_marked,
        absent_students=absent_students[:5],
    )
    return TeacherDashboard(
        greeting_name=greeting_name,
        today_iso=today_iso,
        my_class=snapshot,
        pending_score_assessments=pending,
    )


async def _approver_view(
    school_id: uuid.UUID,
    greeting_name: str,
    db: AsyncSession,
) -> ApproverDashboard:
    term = await _current_term(school_id, db)
    pending = 0
    total_assessments = 0
    if term:
        pending = await db.scalar(
            select(func.count(Score.id)).where(
                Score.school_id == school_id, Score.is_approved.is_(False),
            )
        ) or 0
        total_assessments = await db.scalar(
            select(func.count(Assessment.id)).where(
                Assessment.school_id == school_id, Assessment.academic_term_id == term.id,
            )
        ) or 0
    return ApproverDashboard(
        greeting_name=greeting_name,
        pending_approvals=pending,
        assessments_this_term=total_assessments,
    )


async def _housemaster_view(
    school_id: uuid.UUID,
    staff_member_id: uuid.UUID,
    greeting_name: str,
    db: AsyncSession,
) -> HousemasterDashboard:
    from app.models.housing import Exeat, ExeatStatus, ExeatType, House, HouseMaster, StudentHouseAssignment

    hm = await db.scalar(
        select(HouseMaster).where(
            HouseMaster.staff_member_id == staff_member_id,
            HouseMaster.school_id == school_id,
            HouseMaster.is_active.is_(True),
        )
    )
    if not hm:
        return HousemasterDashboard(greeting_name=greeting_name)

    house = await db.get(House, hm.house_id)

    total_residents = await db.scalar(
        select(func.count(StudentHouseAssignment.id)).where(
            StudentHouseAssignment.house_id == hm.house_id,
            StudentHouseAssignment.school_id == school_id,
            StudentHouseAssignment.vacated_at.is_(None),
        )
    ) or 0

    active_students = (
        select(StudentHouseAssignment.student_id).where(
            StudentHouseAssignment.house_id == hm.house_id,
            StudentHouseAssignment.school_id == school_id,
            StudentHouseAssignment.vacated_at.is_(None),
        )
    )
    pending_exeats = await db.scalar(
        select(func.count(Exeat.id)).where(
            Exeat.school_id == school_id,
            Exeat.status == ExeatStatus.PENDING,
            Exeat.student_id.in_(active_students),
        )
    ) or 0
    off_campus = await db.scalar(
        select(func.count(Exeat.id)).where(
            Exeat.school_id == school_id,
            Exeat.status == ExeatStatus.APPROVED,
            Exeat.exeat_type == ExeatType.EXTERNAL,
            Exeat.student_id.in_(active_students),
        )
    ) or 0

    return HousemasterDashboard(
        greeting_name=greeting_name,
        house_id=hm.house_id,
        house_name=house.name if house else None,
        total_residents=total_residents,
        pending_exeats=pending_exeats,
        off_campus_count=off_campus,
    )


async def get_dashboard(
    user_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> DashboardData:
    user = await db.get(User, user_id)
    if not user or not user.staff_member_id:
        return TeacherDashboard(
            greeting_name="Welcome",
            today_iso=date.today().isoformat(),
            my_class=None,
            pending_score_assessments=0,
        )

    staff = await db.get(StaffMember, user.staff_member_id)
    greeting_name = f"{staff.first_name} {staff.last_name}" if staff else "Staff"

    if user.is_superadmin:
        return await admin_view(school_id, greeting_name, db)

    perms = await resolve_permissions(user.staff_member_id, db)

    if perms.get("school.manage_users"):
        return await admin_view(school_id, greeting_name, db)
    if perms.get("fees.collect"):
        return await finance_view(school_id, greeting_name, db)
    if perms.get("assessments.approve_scores"):
        return await _approver_view(school_id, greeting_name, db)
    if perms.get("housing.manage"):
        return await _housemaster_view(school_id, user.staff_member_id, greeting_name, db)
    return await _teacher_view(school_id, user.staff_member_id, greeting_name, db)
