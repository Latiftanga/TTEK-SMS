"""Staff promotions and leave management.

Separated from services/staff.py to keep files under 300 lines.

PROMOTION INVARIANT
-------------------
record_promotion() updates StaffMember.position_id in the same flush so the
staff member's current position is always consistent with their promotion history.

LEAVE INVARIANT
---------------
days_count is caller-supplied — the server does not compute it because the school
calendar (weekends, public holidays) affects the count and is not resolved here.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import StaffPosition
from app.models.staff import LeaveStatus, StaffLeave, StaffMember, StaffPromotion
from app.schemas.staff import LeaveCreate, LeaveRead, LeaveReview, PromotionCreate, PromotionRead


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def record_promotion(
    staff_id: uuid.UUID,
    req: PromotionCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
    approved_by_id: uuid.UUID,
) -> PromotionRead:
    member = await db.scalar(
        select(StaffMember).where(StaffMember.id == staff_id, StaffMember.school_id == school_id)
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")

    promotion = StaffPromotion(
        school_id=school_id,
        staff_member_id=staff_id,
        from_position_id=req.from_position_id or member.position_id,
        to_position_id=req.to_position_id,
        effective_date=req.effective_date,
        reason=req.reason,
        approved_by_id=approved_by_id,
        created_at=_utcnow(),
    )
    db.add(promotion)
    member.position_id = req.to_position_id
    await db.flush()
    return await _promotion_read(promotion, db)


async def list_promotions(
    staff_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[PromotionRead]:
    rows = await db.scalars(
        select(StaffPromotion)
        .where(StaffPromotion.staff_member_id == staff_id, StaffPromotion.school_id == school_id)
        .order_by(StaffPromotion.effective_date.desc())
    )
    return [await _promotion_read(p, db) for p in rows]


async def submit_leave(
    staff_id: uuid.UUID,
    req: LeaveCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> StaffLeave:
    member = await db.get(StaffMember, staff_id)
    if not member or member.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")
    if req.end_date < req.start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be on or after start_date.",
        )
    leave = StaffLeave(
        school_id=school_id,
        staff_member_id=staff_id,
        leave_type=req.leave_type.strip(),
        start_date=req.start_date,
        end_date=req.end_date,
        days_count=req.days_count,
        reason=req.reason,
        status=LeaveStatus.PENDING,
    )
    db.add(leave)
    await db.flush()
    return leave


async def list_leave(
    staff_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[StaffLeave]:
    rows = await db.scalars(
        select(StaffLeave)
        .where(StaffLeave.staff_member_id == staff_id, StaffLeave.school_id == school_id)
        .order_by(StaffLeave.start_date.desc())
    )
    return list(rows)


async def list_pending_leave(school_id: uuid.UUID, db: AsyncSession) -> list[StaffLeave]:
    rows = await db.scalars(
        select(StaffLeave)
        .where(StaffLeave.school_id == school_id, StaffLeave.status == LeaveStatus.PENDING)
        .order_by(StaffLeave.created_at)
    )
    return list(rows)


async def review_leave(
    leave_id: uuid.UUID,
    req: LeaveReview,
    school_id: uuid.UUID,
    db: AsyncSession,
    reviewed_by_id: uuid.UUID,
) -> StaffLeave:
    leave = await db.scalar(
        select(StaffLeave).where(StaffLeave.id == leave_id, StaffLeave.school_id == school_id)
    )
    if not leave:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found.")
    if leave.status != LeaveStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Leave has already been {leave.status.value.lower()}.",
        )
    leave.status = req.status
    leave.notes = req.notes
    leave.approved_by_id = reviewed_by_id
    leave.reviewed_at = _utcnow()
    await db.flush()
    return leave


async def _promotion_read(promotion: StaffPromotion, db: AsyncSession) -> PromotionRead:
    from_pos = await db.get(StaffPosition, promotion.from_position_id) if promotion.from_position_id else None
    to_pos = await db.get(StaffPosition, promotion.to_position_id)
    return PromotionRead(
        id=promotion.id,
        staff_member_id=promotion.staff_member_id,
        from_position_id=promotion.from_position_id,
        from_position_name=from_pos.name if from_pos else None,
        to_position_id=promotion.to_position_id,
        to_position_name=to_pos.name if to_pos else "Unknown",
        effective_date=promotion.effective_date,
        reason=promotion.reason,
        created_at=promotion.created_at,
    )
