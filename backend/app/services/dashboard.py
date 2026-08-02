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
    TeacherDashboard,
)
from app.services.dashboard_admin import admin_view, finance_view
from app.services.dashboard_housemaster import housemaster_view
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
            select(func.count(Score.id))
            .join(Assessment, Assessment.id == Score.assessment_id)
            .where(
                Score.school_id == school_id,
                Score.is_approved.is_(False),
                Assessment.academic_term_id == term.id,
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


async def get_dashboard(
    user_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> DashboardData:
    user = await db.get(User, user_id)
    if not user or not user.staff_member_id:
        # Covers the platform superadmin (school_id=None, staff_member_id=None,
        # never tied to a single school — see scripts/create_superadmin.py) along
        # with any other non-staff caller. The superadmin's real dashboard is
        # /superadmin; this generic fallback is only what they'd see if they
        # landed on /dashboard directly.
        return TeacherDashboard(
            greeting_name="Welcome",
            today_iso=date.today().isoformat(),
            my_classes=[],
            pending_score_assessments=0,
        )

    staff = await db.get(StaffMember, user.staff_member_id)
    greeting_name = f"{staff.first_name} {staff.last_name}" if staff else "Staff"

    perms = await resolve_permissions(user.staff_member_id, db)

    if perms.get("school.manage_users"):
        return await admin_view(school_id, greeting_name, db)
    if perms.get("fees.collect"):
        return await finance_view(school_id, greeting_name, db)
    if perms.get("assessments.approve_scores"):
        return await _approver_view(school_id, greeting_name, db)
    if perms.get("housing.manage"):
        return await housemaster_view(school_id, user.staff_member_id, greeting_name, db)
    # Catches senior non-teaching staff who hold none of the above (e.g. an
    # Assistant Head - Administration, who has no fees/assessments-approve/
    # housing.manage) — without this they'd otherwise fall through to the
    # teacher dashboard ("my classes: none"), which reads as broken for
    # someone who doesn't teach at all.
    if perms.get("staff.edit"):
        return await _approver_view(school_id, greeting_name, db)
    return await teacher_view(school_id, user.staff_member_id, greeting_name, db)
