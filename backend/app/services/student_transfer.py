"""Transfer request CRUD and review logic."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.students import Student, TransferRequest, TransferStatus
from app.schemas.students import TransferRequestCreate, TransferRequestRead, TransferRequestReview


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
