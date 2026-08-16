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
    StaffDashboard,
)
from app.services.academic_year import get_current_term
from app.services.dashboard_admin import admin_view, finance_view
from app.services.dashboard_staff import staff_view


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


# ── Role-signal detection ────────────────────────────────────────────────────
# A staff member can hold several responsibilities at once (Class Teacher +
# Housemaster is the reported case). The cascade below still returns ONE
# primary view by seniority (admin/finance/approver win over everything),
# but is_class_teacher/is_subject_teacher/is_housemaster are computed
# independently of which view wins so nav gating stays correct regardless —
# see _role_signals() below. Deliberately cheap (a couple of COUNT queries
# each) — the full per-class/per-subject/per-house snapshot lives in
# dashboard_staff.py's StaffDashboard, not here.

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


async def _role_signals(
    primary: str, staff_id: uuid.UUID, school_id: uuid.UUID, perms: dict, db: AsyncSession,
) -> tuple[bool, bool, bool, list[RoleBadge]]:
    """Returns (is_class_teacher, is_subject_teacher, is_housemaster,
    badges). The three booleans are always computed, independent of which
    view is primary — this is what lets nav gating stop depending on the
    `view` string. badges are only built when primary is admin/finance/
    approver: the `staff` view already shows class/subject/house
    responsibilities directly as full sections, so a badge there would just
    repeat itself."""
    ct_classes, ct_pending = await _class_teacher_info(staff_id, school_id, db)
    subj_count = await _subject_teacher_count(staff_id, school_id, db)
    hm_houses, hm_pending = await _housemaster_info(staff_id, school_id, db)

    is_class_teacher = ct_classes > 0
    is_subject_teacher = subj_count > 0
    is_housemaster = hm_houses > 0

    badges: list[RoleBadge] = []
    if primary != "staff":
        if is_class_teacher:
            detail = _plural(ct_classes, "class")
            if ct_pending:
                detail += f" · {_plural(ct_pending, 'pending score')}"
            badges.append(RoleBadge(role="teacher", label="Class Teacher", detail=detail, href="/attendance"))

        if is_subject_teacher:
            badges.append(RoleBadge(
                role="subject_teacher", label="Subject Teacher",
                detail=_plural(subj_count, "subject"), href="/assessments",
            ))

        if is_housemaster:
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

    return is_class_teacher, is_subject_teacher, is_housemaster, badges


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
        return StaffDashboard(
            greeting_name="Welcome",
            today_iso=date.today().isoformat(),
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
    # Catches senior non-teaching staff who hold none of the above (e.g.
    # someone granted staff.edit via a personal permission override for an
    # administrative portfolio, but no fees.collect/assessments.approve_scores)
    # — without this they'd otherwise fall through to the staff dashboard
    # ("my classes/subjects/houses: none"), which reads as broken for someone
    # who doesn't teach or house at all.
    elif perms.get("staff.edit"):
        primary, result = "approver", await _approver_view(school_id, greeting_name, db)
    else:
        # Everyone else — Class Teacher, Subject Teacher, Housemaster, any
        # combination, or none yet — gets the one composed staff view; each
        # section is populated independently from real assignment rows, not
        # from a seniority pick, so holding several responsibilities at once
        # shows all of them rather than just one.
        primary, result = "staff", await staff_view(school_id, user.staff_member_id, greeting_name, db)

    is_class_teacher, is_subject_teacher, is_housemaster, other_roles = await _role_signals(
        primary, user.staff_member_id, school_id, perms, db,
    )
    return result.model_copy(update={
        "is_class_teacher": is_class_teacher,
        "is_subject_teacher": is_subject_teacher,
        "is_housemaster": is_housemaster,
        "other_roles": other_roles,
    })
