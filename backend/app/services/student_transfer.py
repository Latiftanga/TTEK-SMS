"""Transfer request CRUD and review logic."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import School
from app.models.students import Student, TransferRequest, TransferStatus
from app.schemas.students import TransferRequestCreate, TransferRequestRead, TransferRequestReview
from app.services import email_notifications as email_svc
from app.services import sms_notifications as sms_svc
from app.services.student_lifecycle import deactivate_student


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def create_transfer_request(
    student_id: uuid.UUID,
    req: TransferRequestCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> TransferRequestRead:
    student = await db.get(Student, student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=404, detail="Student not found.")

    if req.requesting_school_id is not None:
        requesting_school = await db.get(School, req.requesting_school_id)
        if not requesting_school:
            raise HTTPException(status_code=404, detail="Requesting school not found.")

    existing_pending = await db.scalar(
        select(TransferRequest).where(
            TransferRequest.student_id == student_id,
            TransferRequest.school_id == school_id,
            TransferRequest.status == TransferStatus.PENDING,
        )
    )
    if existing_pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A transfer request is already pending for this student.",
        )

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
    transfers = list(await db.scalars(
        select(TransferRequest).where(
            TransferRequest.school_id == school_id,
            TransferRequest.status == TransferStatus.PENDING,
        ).order_by(TransferRequest.created_at)
    ))
    if not transfers:
        return []

    student_ids = list({t.student_id for t in transfers})
    students = {
        s.id: s for s in await db.scalars(
            select(Student).where(Student.id.in_(student_ids))
        )
    }

    result = []
    for t in transfers:
        data = TransferRequestRead.model_validate(t)
        stu = students.get(t.student_id)
        if stu:
            data.student_name = f"{stu.first_name} {stu.last_name}"
            data.admission_number = stu.admission_number
        result.append(data)
    return result


async def list_transfers_for_student(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[TransferRequestRead]:
    transfers = list(await db.scalars(
        select(TransferRequest).where(
            TransferRequest.student_id == student_id,
            TransferRequest.school_id == school_id,
        ).order_by(TransferRequest.created_at.desc())
    ))
    return [TransferRequestRead.model_validate(t) for t in transfers]


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
        # Leaving the school entirely — deactivate every active class assignment
        # and term enrollment (not just the current year's), and revoke portal login.
        await deactivate_student(tr.student_id, school_id, db)

    await db.flush()

    if req.status in (TransferStatus.APPROVED, TransferStatus.REJECTED):
        school = await db.get(School, school_id)
        await sms_svc.notify_transfer_decision(
            student_id=tr.student_id,
            school_id=school_id,
            school_short=(school.short_name or school.name) if school else "",
            approved=req.status == TransferStatus.APPROVED,
            entity_id=tr.id,
            db=db,
        )
        await email_svc.notify_transfer_decision_email(
            student_id=tr.student_id,
            school_id=school_id,
            school_short=(school.short_name or school.name) if school else "",
            approved=req.status == TransferStatus.APPROVED,
            entity_id=tr.id,
            db=db,
        )

    return TransferRequestRead.model_validate(tr)
