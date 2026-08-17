"""
Shared cascade for a student who is exiting the school (graduated / withdrawn /
transferred), and for one who returns afterward. Deactivating Student.is_active
alone leaves a working portal login and open class/term enrollments — this
mirrors the staff-deactivation fix (StaffMember.is_active and User.is_active
are separate columns) for students.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm
from app.models.auth import User
from app.models.students import Student, StudentClassAssignment, TermEnrollment
from app.schemas.students import StudentClassAssignmentCreate, TermEnrollmentCreate
from app.services.academic_year import get_current_term, get_current_year
from app.services.student_class_assignment import create_class_assignment
from app.services.student_enrollment import create_term_enrollment


async def deactivate_student(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
    academic_year_id: uuid.UUID | None = None,
) -> None:
    """
    Fully sever a student who is exiting the school:
      - Student.is_active = False
      - active StudentClassAssignment row(s) deactivated
      - active TermEnrollment row(s) deactivated
      - linked portal User.is_active = False (revokes login)

    `academic_year_id=None` deactivates every active assignment/enrollment
    (a transfer severs ties regardless of year); passing a specific year scopes
    the cascade to that year only (graduation, which only ends this year's
    membership).
    """
    # Defense-in-depth for every current and future caller: this is a
    # shared cascade (transfer/withdrawal/graduation all route through it)
    # and, unlike the StudentClassAssignment/TermEnrollment updates below,
    # the Student row itself was previously fetched by id alone with no
    # school_id check — a caller from a different school supplying a real
    # foreign student_id could silently deactivate that student and revoke
    # their portal login.
    student = await db.get(Student, student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=404, detail="Student not found.")
    student.is_active = False

    assignment_where = [
        StudentClassAssignment.student_id == student_id,
        StudentClassAssignment.school_id == school_id,
        StudentClassAssignment.is_active == True,  # noqa: E712
    ]
    if academic_year_id is not None:
        assignment_where.append(StudentClassAssignment.academic_year_id == academic_year_id)
    await db.execute(update(StudentClassAssignment).where(*assignment_where).values(is_active=False))

    term_where = [
        TermEnrollment.student_id == student_id,
        TermEnrollment.school_id == school_id,
        TermEnrollment.is_active == True,  # noqa: E712
    ]
    if academic_year_id is not None:
        term_ids = select(AcademicTerm.id).where(AcademicTerm.academic_year_id == academic_year_id)
        term_where.append(TermEnrollment.academic_term_id.in_(term_ids))
    await db.execute(update(TermEnrollment).where(*term_where).values(is_active=False))

    user = await db.scalar(
        select(User).where(User.student_id == student_id, User.is_active == True)  # noqa: E712
    )
    if user:
        user.is_active = False


async def reactivate_student(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """
    Bring a withdrawn/transferred/graduated student back:
      - Student.is_active = True
      - linked portal User.is_active = True (restores login)
      - best-effort: the current academic year's StudentClassAssignment and
        the current term's TermEnrollment are reactivated in place if they
        exist and are inactive

    The class/term restore is scoped to whatever is_current right now, not
    "most recent ever" — StudentClassAssignment's (student, academic_year)
    uniqueness means there's at most one candidate row once scoped this way,
    and a student who left in a prior year that's since rolled over correctly
    has nothing to restore (they were never assigned to the new current year;
    staff onboard them fresh like any other student entering a new year).

    Restoring class/term is deliberately best-effort — e.g. the class was
    since deleted, or the fee gate now blocks the term — so a failure there
    must never block the Student/User restoration above. Each step runs in
    its own savepoint so one failing can't undo an earlier success.
    """
    student = await db.get(Student, student_id)
    if student:
        student.is_active = True

    user = await db.scalar(
        select(User).where(User.student_id == student_id, User.is_active == False)  # noqa: E712
    )
    if user:
        user.is_active = True

    year = await get_current_year(school_id, db)
    class_restored = False
    if year:
        sca = await db.scalar(
            select(StudentClassAssignment).where(
                StudentClassAssignment.student_id == student_id,
                StudentClassAssignment.academic_year_id == year.id,
                StudentClassAssignment.school_id == school_id,
            )
        )
        if sca and not sca.is_active:
            try:
                async with db.begin_nested():
                    await create_class_assignment(
                        StudentClassAssignmentCreate(
                            student_id=student_id, class_id=sca.class_id, academic_year_id=year.id,
                        ),
                        school_id, user_id, db,
                    )
                class_restored = True
            except HTTPException:
                pass  # class deleted/deactivated, etc. — staff finish manually via EnrollmentTab

    term = await get_current_term(school_id, db)
    if term and class_restored:
        te = await db.scalar(
            select(TermEnrollment).where(
                TermEnrollment.student_id == student_id,
                TermEnrollment.academic_term_id == term.id,
                TermEnrollment.school_id == school_id,
            )
        )
        if te and not te.is_active:
            try:
                async with db.begin_nested():
                    await create_term_enrollment(
                        TermEnrollmentCreate(student_id=student_id, academic_term_id=term.id),
                        school_id, user_id, db,
                    )
            except HTTPException:
                pass  # fee gate now blocking, etc. — staff finish manually with a waiver
