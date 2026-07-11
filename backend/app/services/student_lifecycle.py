"""
Shared cascade for a student who is exiting the school (graduated / withdrawn /
transferred). Deactivating Student.is_active alone leaves a working portal login
and open class/term enrollments — this mirrors the staff-deactivation fix
(StaffMember.is_active and User.is_active are separate columns) for students.
"""
from __future__ import annotations
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm
from app.models.auth import User
from app.models.students import Student, StudentClassAssignment, TermEnrollment


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
    student = await db.get(Student, student_id)
    if student:
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
