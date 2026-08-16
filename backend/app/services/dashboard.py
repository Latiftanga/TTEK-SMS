"""Dashboard service — role-detection and role-specific views.

Admin and finance views live in dashboard_admin.py to respect the 300-line limit.
"""
from __future__ import annotations
import uuid
from datetime import date
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import resolve_permissions
from app.models.academic import ClassTeacher, SubjectTeacher
from app.models.assessments import Assessment, Score
from app.models.auth import User
from app.models.fees import StudentFeeSummary
from app.models.housing import Exeat, ExeatStatus, HouseMaster, StudentHouseAssignment
from app.models.staff import StaffMember
from app.schemas.dashboard import (
    ApproverDashboard,
    DashboardData,
    RoleBadge,
    TeacherDashboard,
)
from app.services.academic_year import get_current_term
from app.services.dashboard_admin import admin_view, finance_view
from app.services.dashboard_housemaster import housemaster_view
from app.services.dashboard_teacher import teacher_view


async def _approver_view(
    school_id: uuid.UUID,
    greeting_name: str,
    db: AsyncSession,
) -> ApproverDashboard:
    term = await get_current_term(school_id, db)
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


# ── Secondary-role detection ─────────────────────────────────────────────────
# A staff member can hold several responsibilities at once (Class Teacher +
# Housemaster is the reported case), but the cascade below only ever returns
# ONE full view, chosen by seniority. These helpers compute lightweight
# signals for every OTHER responsibility, independent of which view wins, so
# get_dashboard() can attach them as `other_roles` badges + the
# nav-correctness `is_class_teacher` flag. Deliberately cheap (a couple of
# COUNT queries each) — a full per-class/per-house snapshot belongs to the
# view itself, not a "you also..." badge.

async def _class_teacher_info(staff_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> tuple[int, int]:
    """(class count, pending unpublished assessments across them) for the
    caller's own active ClassTeacher rows this year. (0, 0) if none."""
    term = await get_current_term(school_id, db)
    if not term:
        return 0, 0
    class_ids = list(await db.scalars(
        select(ClassTeacher.class_id).where(
            ClassTeacher.staff_member_id == staff_id,
            ClassTeacher.academic_year_id == term.academic_year_id,
            ClassTeacher.is_active.is_(True),
        )
    ))
    if not class_ids:
        return 0, 0
    pending = await db.scalar(
        select(func.count(Assessment.id)).where(
            Assessment.class_id.in_(class_ids),
            Assessment.academic_term_id == term.id,
            Assessment.is_published.is_(False),
        )
    ) or 0
    return len(class_ids), pending


async def _subject_teacher_count(staff_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> int:
    """Distinct subjects the caller is the assigned SubjectTeacher for this
    year — a subject-only teaching load has no dashboard view of its own
    (pre-existing gap, not addressed here), so this badge is the only place
    it's surfaced at all today."""
    term = await get_current_term(school_id, db)
    if not term:
        return 0
    return await db.scalar(
        select(func.count(func.distinct(SubjectTeacher.subject_id))).where(
            SubjectTeacher.staff_member_id == staff_id,
            SubjectTeacher.academic_year_id == term.academic_year_id,
            SubjectTeacher.is_active.is_(True),
        )
    ) or 0


async def _housemaster_info(staff_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> tuple[int, int]:
    """(house count, pending exeats across them) for the caller's own active
    HouseMaster rows. (0, 0) if none."""
    house_ids = list(await db.scalars(
        select(HouseMaster.house_id).where(
            HouseMaster.staff_member_id == staff_id,
            HouseMaster.school_id == school_id,
            HouseMaster.is_active.is_(True),
        )
    ))
    if not house_ids:
        return 0, 0
    active_residents = select(StudentHouseAssignment.student_id).where(
        StudentHouseAssignment.house_id.in_(house_ids),
        StudentHouseAssignment.school_id == school_id,
        StudentHouseAssignment.vacated_at.is_(None),
    )
    pending = await db.scalar(
        select(func.count(Exeat.id)).where(
            Exeat.school_id == school_id,
            Exeat.status == ExeatStatus.PENDING,
            Exeat.student_id.in_(active_residents),
        )
    ) or 0
    return len(house_ids), pending


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' if n != 1 else ''}"


async def _other_role_badges(
    primary: str, staff_id: uuid.UUID, school_id: uuid.UUID, perms: dict, db: AsyncSession,
) -> tuple[bool, list[RoleBadge]]:
    """Returns (is_class_teacher, badges) — is_class_teacher is reported
    unconditionally (used for nav correctness even when it IS the primary
    view), badges cover only responsibilities the primary view doesn't
    already surface."""
    badges: list[RoleBadge] = []

    ct_classes, ct_pending = await _class_teacher_info(staff_id, school_id, db)
    is_class_teacher = ct_classes > 0
    if primary != "teacher" and is_class_teacher:
        detail = _plural(ct_classes, "class")
        if ct_pending:
            detail += f" · {_plural(ct_pending, 'pending score')}"
        badges.append(RoleBadge(role="teacher", label="Class Teacher", detail=detail, href="/attendance"))

    if primary != "teacher":
        subj_count = await _subject_teacher_count(staff_id, school_id, db)
        if subj_count:
            badges.append(RoleBadge(
                role="subject_teacher", label="Subject Teacher",
                detail=_plural(subj_count, "subject"), href="/assessments",
            ))

    if primary != "housemaster":
        hm_houses, hm_pending = await _housemaster_info(staff_id, school_id, db)
        if hm_houses:
            detail = _plural(hm_houses, "house")
            if hm_pending:
                detail += f" · {_plural(hm_pending, 'pending exeat')}"
            badges.append(RoleBadge(role="housemaster", label="Housemaster", detail=detail, href="/housing"))

    if primary != "approver" and perms.get("assessments.approve_scores"):
        approver = await _approver_view(school_id, "", db)
        if approver.pending_approvals:
            badges.append(RoleBadge(
                role="approver", label="Approver",
                detail=_plural(approver.pending_approvals, "pending approval"), href="/assessments",
            ))

    if primary != "finance" and perms.get("fees.collect"):
        outstanding = await db.scalar(
            select(func.count(StudentFeeSummary.id)).where(
                StudentFeeSummary.school_id == school_id,
                StudentFeeSummary.total_paid < StudentFeeSummary.total_due,
            )
        ) or 0
        if outstanding:
            badges.append(RoleBadge(
                role="finance", label="Finance",
                detail=f"{_plural(outstanding, 'student')} owing", href="/fees",
            ))

    return is_class_teacher, badges


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
        primary, result = "admin", await admin_view(school_id, greeting_name, db)
    elif perms.get("fees.collect"):
        primary, result = "finance", await finance_view(school_id, greeting_name, db)
    elif perms.get("assessments.approve_scores"):
        primary, result = "approver", await _approver_view(school_id, greeting_name, db)
    elif perms.get("housing.manage"):
        primary, result = "housemaster", await housemaster_view(school_id, user.staff_member_id, greeting_name, db)
    # Catches senior non-teaching staff who hold none of the above (e.g.
    # someone granted staff.edit via a personal permission override for an
    # administrative portfolio, but no fees.collect/assessments.approve_scores/
    # housing.manage) — without this they'd otherwise fall through to the
    # teacher dashboard ("my classes: none"), which reads as broken for
    # someone who doesn't teach at all.
    elif perms.get("staff.edit"):
        primary, result = "approver", await _approver_view(school_id, greeting_name, db)
    else:
        primary, result = "teacher", await teacher_view(school_id, user.staff_member_id, greeting_name, db)

    is_class_teacher, other_roles = await _other_role_badges(primary, user.staff_member_id, school_id, perms, db)
    return result.model_copy(update={"is_class_teacher": is_class_teacher, "other_roles": other_roles})
