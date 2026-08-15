"""
Class/Subject-teacher scoping for the Students module — mirrors
core/teacher_scope.py's pattern (used for Attendance/Assessments/Report
Cards), bypassed on `students.delete` instead of an `*.approve*` action.

`students.delete` has no actual "delete a student" endpoint behind it —
today it only gates the transfer-approval queue — so it already functions
as this module's de-facto "senior/admin tier" action. Reusing it (rather
than adding a new `students.manage` permission) keeps the students module
at 4 actions instead of 5.

Senior/administrative staff (`students.delete` holders — HEAD, and per
this change DEPUTY_HEAD/HOD — plus superadmin) are never scoped: they need
cross-school visibility to do their job (reviewing a transfer from any
class, editing a student a class teacher hasn't been assigned to yet,
etc.), mirroring the existing bypass convention in teacher_scope.py and
services/student_list.py.

Unlike the "absence of registration data" backward-compat convention used
elsewhere in this codebase (subject registration/electives), scoping here
is a hard access-control boundary: a teacher with zero recorded
ClassTeacher/SubjectTeacher assignments sees/touches zero students until
an admin actually assigns them — never a silent full-access fallback.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import user_has_permission
from app.models.academic import ClassTeacher, SubjectTeacher
from app.models.housing import HouseMaster, StudentHouseAssignment
from app.models.students import StudentClassAssignment
from app.services.student_display import _active_class_assignment_subquery


async def _staff_member_id_for(user_id: uuid.UUID, db: AsyncSession) -> uuid.UUID | None:
    from app.models.auth import User

    user = await db.get(User, user_id)
    if not user or user.is_superadmin:
        return None
    return user.staff_member_id


async def _is_unrestricted(user_id: uuid.UUID, db: AsyncSession) -> bool:
    return await user_has_permission(user_id, "students", "delete", db)


async def resolve_student_view_scope(
    user_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> set[uuid.UUID] | None:
    """None = unrestricted (students.delete holder, superadmin, non-staff
    login, or one of the existing broad-access permissions — fees.collect/
    manage, housing.assign/manage, assessments.approve_scores — held by
    staff whose own job legitimately needs cross-class visibility).
    Otherwise the exact set of student_ids the caller is responsible for:
    students in a class they're ClassTeacher/SubjectTeacher of, plus any
    house they manage as HouseMaster."""
    if await _is_unrestricted(user_id, db):
        return None
    broad_access_perms = (
        "fees.collect", "fees.manage",
        "housing.assign", "housing.manage",
        "assessments.approve_scores",
    )
    staff_id = await _staff_member_id_for(user_id, db)
    if staff_id is None:
        return None
    from app.core.permissions import resolve_permissions

    perms = await resolve_permissions(staff_id, db)
    if any(perms.get(p, False) for p in broad_access_perms):
        return None

    taught_class_ids = (
        select(ClassTeacher.class_id).where(
            ClassTeacher.staff_member_id == staff_id,
            ClassTeacher.is_active == True,  # noqa: E712
        )
    ).union(
        select(SubjectTeacher.class_id).where(
            SubjectTeacher.staff_member_id == staff_id,
            SubjectTeacher.is_active == True,  # noqa: E712
        )
    )
    in_taught_class = select(StudentClassAssignment.student_id).where(
        StudentClassAssignment.class_id.in_(taught_class_ids),
        StudentClassAssignment.is_active == True,  # noqa: E712
        StudentClassAssignment.school_id == school_id,
    )
    managed_house_ids = select(HouseMaster.house_id).where(
        HouseMaster.staff_member_id == staff_id,
        HouseMaster.is_active == True,  # noqa: E712
    )
    in_managed_house = select(StudentHouseAssignment.student_id).where(
        StudentHouseAssignment.house_id.in_(managed_house_ids),
        StudentHouseAssignment.vacated_at.is_(None),
        StudentHouseAssignment.school_id == school_id,
    )
    rows = await db.scalars(in_taught_class.union(in_managed_house))
    return set(rows)


async def resolve_class_teacher_scope(
    user_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    db: AsyncSession,
) -> set[uuid.UUID] | None:
    """None = unrestricted (students.delete holder, superadmin, non-staff
    login). Otherwise the exact set of class_ids the caller is an active
    ClassTeacher of this year — including empty."""
    if await _is_unrestricted(user_id, db):
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


async def resolve_subject_teacher_scope(
    user_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    db: AsyncSession,
) -> set[tuple[uuid.UUID, uuid.UUID]] | None:
    """None = unrestricted (students.delete holder, superadmin, non-staff
    login). Otherwise the exact set of (class_id, subject_id) pairs from
    the caller's active SubjectTeacher rows this year — including empty."""
    if await _is_unrestricted(user_id, db):
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


async def resolve_term_enrollment_scope(
    user_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    db: AsyncSession,
) -> set[uuid.UUID] | None:
    """None = unrestricted (students.delete holder, superadmin, non-staff
    login). Otherwise the set of class_ids the caller may register a
    TermEnrollment against this year: classes they're ClassTeacher of, OR —
    deliberately wider than resolve_class_teacher_scope — classes where they
    hold any active SubjectTeacher assignment this year, regardless of
    subject. Not narrowed to a specific (class, subject) pair like
    resolve_subject_teacher_scope: a term enrollment is the pastoral
    "physically reported" gate that attendance marking hangs off, and
    attendance isn't subject-scoped, so any teacher with a legitimate
    reason to touch this class this year (scoring OR attendance) may
    register a student for the term. Same union shape as
    resolve_student_view_scope's taught_class_ids, kept separate since that
    one returns student_ids school-wide, not class_ids for one year."""
    if await _is_unrestricted(user_id, db):
        return None
    staff_id = await _staff_member_id_for(user_id, db)
    if staff_id is None:
        return None
    rows = await db.scalars(
        select(ClassTeacher.class_id).where(
            ClassTeacher.staff_member_id == staff_id,
            ClassTeacher.academic_year_id == academic_year_id,
            ClassTeacher.is_active.is_(True),
        ).union(
            select(SubjectTeacher.class_id).where(
                SubjectTeacher.staff_member_id == staff_id,
                SubjectTeacher.academic_year_id == academic_year_id,
                SubjectTeacher.is_active.is_(True),
            )
        )
    )
    return set(rows)


async def current_class_assignment(
    student_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID] | None:
    """(class_id, academic_year_id) of the student's one active
    StudentClassAssignment row, or None if they have none."""
    active_sca = _active_class_assignment_subquery()
    row = (
        await db.execute(
            select(active_sca.c.class_id, active_sca.c.academic_year_id).where(
                active_sca.c.student_id == student_id
            )
        )
    ).first()
    return (row.class_id, row.academic_year_id) if row else None


async def can_write_student(user_id: uuid.UUID, student_id: uuid.UUID, db: AsyncSession) -> bool:
    """True for a Category A pastoral write (profile/guardians/medical/photo/
    enrollment) on this specific student: unrestricted (students.delete
    holder/superadmin), or the student's current class is one the caller is
    an active ClassTeacher of this year. A student with no active class
    assignment can only be touched by an unrestricted caller — never a
    silent scoped-fallback."""
    if await _is_unrestricted(user_id, db):
        return True
    assignment = await current_class_assignment(student_id, db)
    if assignment is None:
        return False
    class_id, academic_year_id = assignment
    scope = await resolve_class_teacher_scope(user_id, academic_year_id, db)
    return scope is None or class_id in scope


async def assert_can_write_student(user_id: uuid.UUID, student_id: uuid.UUID, db: AsyncSession) -> None:
    """404 (not 403) — matches teacher_scope.py's convention of hiding
    existence rather than revealing a permission boundary."""
    if not await can_write_student(user_id, student_id, db):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found.")


async def assert_can_view_student(
    user_id: uuid.UUID, student_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> None:
    scope = await resolve_student_view_scope(user_id, school_id, db)
    if scope is not None and student_id not in scope:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found.")
