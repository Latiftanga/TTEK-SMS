"""
Initial enrollment and term enrollment.

FLOW
----
1. Admin creates Student record.
2. Admin creates StudentClassAssignment (student → class → academic year).
   See student_class_assignment.py.
3. Teacher creates TermEnrollment when the student physically reports for a term.
   Requires a StudentClassAssignment for the same academic year to exist first.
4. Teacher registers subjects (SubjectRegistration) against the TermEnrollment —
   see student_subject_registration.py.

Transfer requests live in student_transfer.py.

FEE GATE
--------
When AcademicTerm.block_owing_students is True, create_term_enrollment blocks
a student whose StudentFeeSummary balance (total_due - total_paid -
total_discounted, computed live — never stored) is positive for that term. A
student with no StudentFeeSummary row at all (no fees assigned yet) is never
blocked. The block is bypassed only if the caller holds fees.manage AND
supplies a non-blank fee_waiver_reason in the same request — a caller without
that permission has any fee_waiver_reason they send silently ignored, they
still get blocked. bulk_term_enrollment treats a fee-gate block the same way
it treats a duplicate-enrollment conflict: skip and continue, so bulk-enrolling
a class doesn't abort entirely because one student owes fees.
"""
from __future__ import annotations
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import resolve_permissions
from app.models.academic import AcademicTerm, Class, SHSProgramme
from app.models.auth import User
from app.models.fees import StudentFeeSummary
from app.models.students import (
    Student,
    StudentClassAssignment,
    StudentEnrollment,
    TermEnrollment,
)
from app.schemas.students import (
    EnrollmentCreate,
    EnrollmentRead,
    TermEnrollmentCreate,
    TermEnrollmentRead,
)


class FeeGateBlockedError(HTTPException):
    """Raised when a fee-owing student is blocked from term enrollment.

    A distinct subclass (rather than a bare HTTPException) so
    bulk_term_enrollment can skip-and-continue on this specific case while
    still aborting the whole batch on other 422s (e.g. missing class
    assignment) — see module docstring.
    """
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


async def _outstanding_balance(student_id: uuid.UUID, term_id: uuid.UUID, db: AsyncSession) -> Decimal | None:
    """None = no StudentFeeSummary row yet (nothing assigned — never blocks)."""
    summary = await db.scalar(
        select(StudentFeeSummary).where(
            StudentFeeSummary.student_id == student_id,
            StudentFeeSummary.academic_term_id == term_id,
        )
    )
    if not summary:
        return None
    return summary.total_due - summary.total_paid - summary.total_discounted


async def _can_waive_fee_gate(user_id: uuid.UUID, db: AsyncSession) -> bool:
    user = await db.get(User, user_id)
    if not user:
        return False
    if user.is_superadmin:
        return True
    if not user.staff_member_id:
        return False
    perms = await resolve_permissions(user.staff_member_id, db)
    return perms.get("fees.manage", False)


def _display_name(level: str, year_group: int, programme_name: str | None, stream: str | None) -> str:
    if level.upper() == "SHS":
        parts = [str(year_group)]
        if programme_name:
            parts.append(programme_name)
    else:
        parts = [level, str(year_group)]
    if stream:
        parts.append(stream)
    return " ".join(parts)


def _te_query(*where_clauses):
    """
    Joins TermEnrollment → AcademicTerm → StudentClassAssignment → Class → SHSProgramme
    to include class context in the response.
    """
    return (
        select(
            TermEnrollment,
            StudentClassAssignment.class_id,
            Class.level,
            Class.year_group,
            Class.stream,
            SHSProgramme.name,
        )
        .join(AcademicTerm, AcademicTerm.id == TermEnrollment.academic_term_id)
        .outerjoin(
            StudentClassAssignment,
            (StudentClassAssignment.student_id == TermEnrollment.student_id)
            & (StudentClassAssignment.academic_year_id == AcademicTerm.academic_year_id),
        )
        .outerjoin(Class, Class.id == StudentClassAssignment.class_id)
        .outerjoin(SHSProgramme, SHSProgramme.id == Class.programme_id)
        .where(*where_clauses)
        .order_by(TermEnrollment.created_at.desc())
    )


def _to_te_read(row) -> TermEnrollmentRead:
    te, class_id, level, year_group, stream, prog_name = row
    display = _display_name(level, year_group, prog_name, stream) if level else None
    return TermEnrollmentRead(
        id=te.id,
        student_id=te.student_id,
        academic_term_id=te.academic_term_id,
        class_id=class_id,
        class_display_name=display,
        is_active=te.is_active,
        fee_waived=te.fee_waived,
        created_at=te.created_at,
    )


# ── Initial enrollment ────────────────────────────────────────────────────────

async def create_enrollment(
    student_id: uuid.UUID,
    req: EnrollmentCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> EnrollmentRead:
    student = await db.get(Student, student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    enrollment = StudentEnrollment(
        school_id=school_id,
        student_id=student_id,
        enrolled_at=req.enrolled_at,
        enrollment_type=req.enrollment_type,
        transfer_from_school=req.transfer_from_school,
    )
    db.add(enrollment)
    await db.flush()
    return EnrollmentRead.model_validate(enrollment)


# ── Term enrollment ───────────────────────────────────────────────────────────

async def create_term_enrollment(
    req: TermEnrollmentCreate,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> TermEnrollmentRead:
    student = await db.get(Student, req.student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=404, detail="Student not found.")

    term = await db.get(AcademicTerm, req.academic_term_id)
    if not term or term.school_id != school_id:
        raise HTTPException(status_code=404, detail="Academic term not found.")

    sca = await db.scalar(
        select(StudentClassAssignment).where(
            StudentClassAssignment.student_id == req.student_id,
            StudentClassAssignment.academic_year_id == term.academic_year_id,
            StudentClassAssignment.school_id == school_id,
        )
    )
    if not sca:
        raise HTTPException(
            status_code=422,
            detail="Student has no class assignment for this academic year. "
                   "Assign the student to a class before creating a term enrollment.",
        )

    fee_waived = False
    fee_waived_by_id = None
    fee_waiver_reason = None
    if term.block_owing_students:
        balance = await _outstanding_balance(req.student_id, req.academic_term_id, db)
        if balance is not None and balance > 0:
            waiver_reason = (req.fee_waiver_reason or "").strip()
            if waiver_reason and await _can_waive_fee_gate(user_id, db):
                fee_waived = True
                fee_waived_by_id = user_id
                fee_waiver_reason = waiver_reason
            else:
                raise FeeGateBlockedError(
                    detail=f"{student.first_name} {student.last_name} owes {balance:.2f} for this term "
                           "and cannot be enrolled while the fee gate is on. A user with fees.manage can "
                           "push this through by supplying a waiver reason."
                )

    te = TermEnrollment(
        school_id=school_id,
        student_id=req.student_id,
        academic_term_id=req.academic_term_id,
        enrolled_by_id=user_id,
        is_active=True,
        fee_waived=fee_waived,
        fee_waived_by_id=fee_waived_by_id,
        fee_waiver_reason=fee_waiver_reason,
    )
    db.add(te)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student is already enrolled for this term.",
        )

    rows = await db.execute(_te_query(TermEnrollment.id == te.id))
    return _to_te_read(rows.one())


async def list_term_enrollments(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[TermEnrollmentRead]:
    rows = await db.execute(
        _te_query(
            TermEnrollment.student_id == student_id,
            TermEnrollment.school_id == school_id,
        )
    )
    return [_to_te_read(row) for row in rows]


async def bulk_term_enrollment(
    items: list[TermEnrollmentCreate],
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    """Each item runs in its own SAVEPOINT (db.begin_nested()) — the whole
    batch shares one outer transaction (one request = one session, committed
    once at the end by get_db()), so a plain db.rollback() on a skipped item
    would discard every earlier item's already-flushed success in the same
    batch, not just the failed one. See register_subjects() in this file for
    the same pattern."""
    enrolled = skipped = 0
    for item in items:
        try:
            async with db.begin_nested():
                await create_term_enrollment(item, school_id, user_id, db)
            enrolled += 1
        except FeeGateBlockedError:
            skipped += 1
        except HTTPException as e:
            if e.status_code != 409:
                raise
            skipped += 1
    return {"enrolled": enrolled, "skipped": skipped}
