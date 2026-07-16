"""Dashboard service — role-detection and role-specific views.

Admin and finance views live in dashboard_admin.py to respect the 300-line limit.
"""
from __future__ import annotations
import uuid
from datetime import date
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import resolve_permissions
from app.models.academic import AcademicTerm
from app.models.assessments import Assessment, Score
from app.models.auth import User
from app.models.staff import StaffMember
from app.schemas.dashboard import (
    ApproverDashboard,
    DashboardData,
    HousemasterDashboard,
    TeacherDashboard,
)
from app.services.dashboard_admin import admin_view, finance_view
from app.services.dashboard_teacher import teacher_view


async def _current_term(school_id: uuid.UUID, db: AsyncSession) -> AcademicTerm | None:
    return await db.scalar(
        select(AcademicTerm).where(
            AcademicTerm.school_id == school_id,
            AcademicTerm.is_current.is_(True),
        )
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
            my_classes=[],
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
    return await teacher_view(school_id, user.staff_member_id, greeting_name, db)
