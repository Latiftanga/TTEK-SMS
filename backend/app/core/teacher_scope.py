"""
Class/Subject-teacher scoping for Attendance, Assessments/Scoring, and Report
Cards — restricts a CLASS_TEACHER-tier staff member to only the class(es)
they are assigned ClassTeacher of, or the (class, subject) pairs they are
assigned SubjectTeacher of, for a given academic year.

Senior/approval-tier staff (attendance.approve / assessments.approve_scores —
held only by HEAD, DEPUTY_HEAD, HOD, EXAM_OFFICER per
scripts/reference_data.py) are never scoped: they need cross-class oversight
to do their job (approving another teacher's scores, generating school-wide
reports, etc.), mirroring the existing bypass convention in
services/student_list.py.

Unlike the "absence of registration data" backward-compat convention used
elsewhere in this codebase (subject registration/electives, services/
student_subject_registration.py), scoping here is a hard access-control
boundary, not a curriculum-completeness fallback: a teacher with zero
recorded ClassTeacher/SubjectTeacher assignments sees zero classes/subjects
until an admin actually assigns them — never a silent full-access fallback.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import user_has_permission
from app.models.academic import AcademicTerm, Class, ClassTeacher, SHSProgramme, SubjectTeacher
from app.schemas.academic import ClassRead


async def _staff_member_id_for(user_id: uuid.UUID, db: AsyncSession) -> uuid.UUID | None:
    from app.models.auth import User

    user = await db.get(User, user_id)
    if not user or user.is_superadmin:
        return None
    return user.staff_member_id


async def year_for_term(academic_term_id: uuid.UUID | None, db: AsyncSession) -> uuid.UUID | None:
    """Resolve academic_year_id from a term id — None if the term is missing
    or unset, in which case scoping has nothing to check against and every
    resolve_*_scope caller treats it as unrestricted for that one lookup."""
    if academic_term_id is None:
        return None
    term = await db.get(AcademicTerm, academic_term_id)
    return term.academic_year_id if term else None


async def resolve_attendance_scope(
    user_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    db: AsyncSession,
) -> set[uuid.UUID] | None:
    """None = unrestricted (attendance.approve holder, superadmin, or a
    non-staff login). Otherwise the exact set of class_ids the caller is an
    active ClassTeacher of this year — including empty."""
    if await user_has_permission(user_id, "attendance", "approve", db):
        return None
    staff_id = await _staff_member_id_for(user_id, db)
    if staff_id is None:
        return None
    rows = await db.scalars(
        select(ClassTeacher.class_id).where(
            ClassTeacher.staff_member_id == staff_id,
            ClassTeacher.academic_year_id == academic_year_id,
            ClassTeacher.is_active.is_(True),
        )
    )
    return set(rows)


async def resolve_assessment_scope(
    user_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    db: AsyncSession,
) -> set[tuple[uuid.UUID, uuid.UUID]] | None:
    """None = unrestricted (assessments.approve_scores holder, superadmin, or
    a non-staff login). Otherwise the exact set of (class_id, subject_id)
    pairs from the caller's active SubjectTeacher rows this year — including
    empty."""
    if await user_has_permission(user_id, "assessments", "approve_scores", db):
        return None
    staff_id = await _staff_member_id_for(user_id, db)
    if staff_id is None:
        return None
    rows = await db.execute(
        select(SubjectTeacher.class_id, SubjectTeacher.subject_id).where(
            SubjectTeacher.staff_member_id == staff_id,
            SubjectTeacher.academic_year_id == academic_year_id,
            SubjectTeacher.is_active.is_(True),
        )
    )
    return {(r.class_id, r.subject_id) for r in rows}


async def resolve_report_card_scope(
    user_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    db: AsyncSession,
) -> set[uuid.UUID] | None:
    """Same shape/query as resolve_attendance_scope, gated on
    assessments.approve_scores instead — report cards are a class-teacher
    responsibility, gated the same way score approval already is."""
    if await user_has_permission(user_id, "assessments", "approve_scores", db):
        return None
    staff_id = await _staff_member_id_for(user_id, db)
    if staff_id is None:
        return None
    rows = await db.scalars(
        select(ClassTeacher.class_id).where(
            ClassTeacher.staff_member_id == staff_id,
            ClassTeacher.academic_year_id == academic_year_id,
            ClassTeacher.is_active.is_(True),
        )
    )
    return set(rows)


async def enforce_current_term_for_attendance(
    user_id: uuid.UUID,
    academic_term_id: uuid.UUID | None,
    db: AsyncSession,
) -> None:
    """A scoped (non-attendance.approve) caller may only mark attendance for
    the term admins have set as current — going back to mark a past term (or
    ahead to a future one) doesn't make sense for a class teacher. Senior
    staff are unrestricted, same bypass as resolve_attendance_scope."""
    if academic_term_id is None or await user_has_permission(user_id, "attendance", "approve", db):
        return
    term = await db.get(AcademicTerm, academic_term_id)
    if term and not term.is_current:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Attendance can only be marked for the current term.",
        )


async def enforce_current_term_for_scoring(
    user_id: uuid.UUID,
    academic_term_id: uuid.UUID | None,
    db: AsyncSession,
) -> None:
    """Same as enforce_current_term_for_attendance, gated on
    assessments.approve_scores instead — a class/subject teacher only enters
    scores for the term that's currently running."""
    if academic_term_id is None or await user_has_permission(user_id, "assessments", "approve_scores", db):
        return
    term = await db.get(AcademicTerm, academic_term_id)
    if term and not term.is_current:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Scores can only be entered for the current term.",
        )


async def enforce_current_term_for_subject_registration(
    user_id: uuid.UUID,
    academic_term_id: uuid.UUID | None,
    requested_reason: str | None,
    db: AsyncSession,
) -> str | None:
    """A scoped (non-assessments.approve_scores) caller may only register or
    remove subjects for the term admins have set as current — same idea as
    enforce_current_term_for_attendance/scoring. A caller who does hold
    assessments.approve_scores may still backfill a non-current term (that's
    the whole point of the permission), but — unlike the original version of
    this check — must now supply an override_reason, exactly like the
    results_locked override this same registration flow already enforces
    (check_term_lock_override in core/permissions.py). Returns the resolved
    reason (None if the term is current, i.e. nothing to record) so the
    caller can write it to SubjectRegistrationAuditLog; a plain teacher who
    somehow supplies a reason still gets rejected, since the permission
    check is what actually gates this, not the reason's mere presence."""
    if academic_term_id is None:
        return None
    term = await db.get(AcademicTerm, academic_term_id)
    if not term or term.is_current:
        return None
    reason = (requested_reason or "").strip()
    if not reason or not await user_has_permission(user_id, "assessments", "approve_scores", db):
        raise HTTPException(
            status.HTTP_423_LOCKED,
            "Subjects can only be registered or removed for the current term. A user with "
            "assessments.approve_scores can override by supplying an override_reason.",
        )
    return reason


async def classes_for_scope(
    class_ids: set[uuid.UUID] | None,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[ClassRead]:
    """Resolve a scope set (from resolve_attendance_scope/resolve_report_card_scope)
    into ClassRead rows — every class in the school when unrestricted (None),
    or exactly the scoped ids (possibly none). Reuses academic_class.py's own
    rendering so display_name stays computed in one place."""
    from app.services.academic_class import _to_class_read

    if class_ids is not None and not class_ids:
        return []
    where = [Class.school_id == school_id]
    if class_ids is not None:
        where.append(Class.id.in_(class_ids))
    rows = await db.execute(
        select(Class, SHSProgramme.name.label("prog_name"))
        .outerjoin(SHSProgramme, Class.programme_id == SHSProgramme.id)
        .where(*where)
        .order_by(Class.level, Class.year_group, Class.stream)
    )
    return [_to_class_read(cls, prog_name) for cls, prog_name in rows]
