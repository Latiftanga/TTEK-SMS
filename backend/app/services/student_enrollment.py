"""
Student enrollment, term enrollment, subject registration, and transfer requests.

TERM ENROLLMENT INVARIANT
--------------------------
A TermEnrollment is created only when the class teacher confirms the student
has physically arrived for the term.  enrolled_by_id is always the authenticated
user who calls POST /students/term-enrollments.

TRANSFER INVARIANT
------------------
Approving a transfer deactivates the student (is_active=False) so they no longer
appear in class lists while remaining in historical data.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class, SHSProgramme
from app.models.students import (
    Student,
    StudentEnrollment,
    SubjectRegistration,
    TermEnrollment,
    TransferRequest,
    TransferStatus,
)
from app.schemas.students import (
    EnrollmentCreate,
    EnrollmentRead,
    SubjectRegistrationItem,
    SubjectRegistrationRead,
    TermEnrollmentCreate,
    TermEnrollmentRead,
    TransferRequestCreate,
    TransferRequestRead,
    TransferRequestReview,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
    return (
        select(TermEnrollment, Class.level, Class.year_group, Class.stream, SHSProgramme.name)
        .join(Class, Class.id == TermEnrollment.class_id)
        .outerjoin(SHSProgramme, SHSProgramme.id == Class.programme_id)
        .where(*where_clauses)
        .order_by(TermEnrollment.created_at.desc())
    )


def _to_te_read(row) -> TermEnrollmentRead:
    te, level, year_group, stream, prog_name = row
    return TermEnrollmentRead(
        id=te.id,
        student_id=te.student_id,
        class_id=te.class_id,
        academic_term_id=te.academic_term_id,
        class_display_name=_display_name(level, year_group, prog_name, stream),
        is_active=te.is_active,
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
    # Verify student, class, and term all belong to this school
    student = await db.get(Student, req.student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=404, detail="Student not found.")

    cls = await db.get(Class, req.class_id)
    if not cls or cls.school_id != school_id:
        raise HTTPException(status_code=404, detail="Class not found.")

    term = await db.get(AcademicTerm, req.academic_term_id)
    if not term or term.school_id != school_id:
        raise HTTPException(status_code=404, detail="Academic term not found.")

    te = TermEnrollment(
        school_id=school_id,
        student_id=req.student_id,
        class_id=req.class_id,
        academic_term_id=req.academic_term_id,
        enrolled_by_id=user_id,
        is_active=True,
    )
    db.add(te)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student is already enrolled in a class for this term.",
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


# ── Subject registration ──────────────────────────────────────────────────────

async def register_subjects(
    te_id: uuid.UUID,
    items: list[SubjectRegistrationItem],
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[SubjectRegistrationRead]:
    te = await db.scalar(
        select(TermEnrollment).where(
            TermEnrollment.id == te_id, TermEnrollment.school_id == school_id
        )
    )
    if not te:
        raise HTTPException(status_code=404, detail="Term enrollment not found.")

    results: list[SubjectRegistration] = []
    for item in items:
        reg = SubjectRegistration(
            school_id=school_id,
            term_enrollment_id=te_id,
            subject_id=item.subject_id,
            registration_type=item.registration_type,
        )
        try:
            async with db.begin_nested():
                db.add(reg)
                await db.flush()
            results.append(reg)
        except IntegrityError:
            try:
                db.expunge(reg)
            except Exception:
                pass  # already registered — skip silently

    return [SubjectRegistrationRead.model_validate(r) for r in results]


async def list_subject_registrations(
    te_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[SubjectRegistrationRead]:
    rows = await db.scalars(
        select(SubjectRegistration).where(
            SubjectRegistration.term_enrollment_id == te_id,
            SubjectRegistration.school_id == school_id,
        )
    )
    return [SubjectRegistrationRead.model_validate(r) for r in rows]


async def create_transfer_request(
    student_id: uuid.UUID,
    req: TransferRequestCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> TransferRequestRead:
    student = await db.get(Student, student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=404, detail="Student not found.")

    tr = TransferRequest(
        school_id=school_id,
        student_id=student_id,
        requesting_school_id=req.requesting_school_id,
        status=TransferStatus.PENDING,
        reason=req.reason,
    )
    db.add(tr)
    await db.flush()
    return TransferRequestRead.model_validate(tr)


async def list_pending_transfers(
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[TransferRequestRead]:
    rows = await db.scalars(
        select(TransferRequest).where(
            TransferRequest.school_id == school_id,
            TransferRequest.status == TransferStatus.PENDING,
        ).order_by(TransferRequest.created_at)
    )
    return [TransferRequestRead.model_validate(r) for r in rows]


async def bulk_term_enrollment(
    items: list[TermEnrollmentCreate],
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    enrolled = skipped = 0
    for item in items:
        try:
            await create_term_enrollment(item, school_id, user_id, db)
            enrolled += 1
        except HTTPException as e:
            if e.status_code != 409:
                raise
            skipped += 1
    return {"enrolled": enrolled, "skipped": skipped}


async def review_transfer(
    tr_id: uuid.UUID,
    req: TransferRequestReview,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> TransferRequestRead:
    tr = await db.scalar(
        select(TransferRequest).where(
            TransferRequest.id == tr_id, TransferRequest.school_id == school_id
        )
    )
    if not tr:
        raise HTTPException(status_code=404, detail="Transfer request not found.")
    if tr.status != TransferStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transfer has already been {tr.status.value.lower()}.",
        )

    tr.status = req.status
    tr.reviewed_by_id = user_id
    tr.reviewed_at = _utcnow()

    if req.status == TransferStatus.APPROVED:
        student = await db.get(Student, tr.student_id)
        if student:
            student.is_active = False

    await db.flush()
    return TransferRequestRead.model_validate(tr)
