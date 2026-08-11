"""Staff promotions and leave management.

Separated from services/staff.py to keep files under 300 lines.

PROMOTION INVARIANT
-------------------
Promotions track rank changes via FK to StaffRank.
from_rank_id is null for the first recorded promotion.
Current rank is derived at query time from the most recent promotion's to_rank.title.

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
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.staff import StaffMember, StaffRank
from app.models.staff_history import LeaveStatus, StaffLeave, StaffPromotion
from app.schemas.staff import LeaveCreate, LeaveRead, LeaveReview, PromotionCreate, PromotionRead, PromotionUpdate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _assert_rank_visible(rank_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> None:
    """A StaffRank is visible to a school if it's a shared GES template
    (school_id IS NULL) or the school's own private rank. Without this, a
    promotion could reference a completely different school's private rank —
    its title would then leak into this school's promotion history display,
    and an edit/delete on the other school's rank would silently ripple into
    this one. Same cross-tenant gap already closed for Subject/Programme/
    Position/StaffCategory elsewhere in this codebase."""
    rank = await db.get(StaffRank, rank_id)
    if not rank or (rank.school_id is not None and rank.school_id != school_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rank not found.")


def _promotion_to_read(p: StaffPromotion) -> PromotionRead:
    return PromotionRead(
        id=p.id,
        staff_member_id=p.staff_member_id,
        from_rank_id=p.from_rank_id,
        to_rank_id=p.to_rank_id,
        from_rank_title=p.from_rank.title if p.from_rank else None,
        to_rank_title=p.to_rank.title if p.to_rank else None,
        effective_date=p.effective_date,
        reason=p.reason,
        created_at=p.created_at,
    )


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

    await _assert_rank_visible(req.to_rank_id, school_id, db)
    if req.from_rank_id is not None:
        await _assert_rank_visible(req.from_rank_id, school_id, db)

    promotion = StaffPromotion(
        school_id=school_id,
        staff_member_id=staff_id,
        from_rank_id=req.from_rank_id,
        to_rank_id=req.to_rank_id,
        effective_date=req.effective_date,
        reason=req.reason,
        approved_by_id=approved_by_id,
        created_at=_utcnow(),
    )
    db.add(promotion)
    await db.flush()
    await db.refresh(promotion, attribute_names=["from_rank", "to_rank"])
    return _promotion_to_read(promotion)


async def list_promotions(
    staff_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[PromotionRead]:
    rows = await db.scalars(
        select(StaffPromotion)
        .where(StaffPromotion.staff_member_id == staff_id, StaffPromotion.school_id == school_id)
        .options(selectinload(StaffPromotion.from_rank), selectinload(StaffPromotion.to_rank))
        .order_by(StaffPromotion.effective_date.desc())
    )
    return [_promotion_to_read(p) for p in rows]


async def delete_promotion(
    staff_id: uuid.UUID,
    promotion_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    p = await db.scalar(
        select(StaffPromotion).where(
            StaffPromotion.id == promotion_id,
            StaffPromotion.staff_member_id == staff_id,
            StaffPromotion.school_id == school_id,
        )
    )
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found.")
    await db.delete(p)
    await db.flush()


async def update_promotion(
    staff_id: uuid.UUID,
    promotion_id: uuid.UUID,
    req: PromotionUpdate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> PromotionRead:
    p = await db.scalar(
        select(StaffPromotion)
        .where(
            StaffPromotion.id == promotion_id,
            StaffPromotion.staff_member_id == staff_id,
            StaffPromotion.school_id == school_id,
        )
        .options(selectinload(StaffPromotion.from_rank), selectinload(StaffPromotion.to_rank))
    )
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found.")
    if req.to_rank_id is not None:
        await _assert_rank_visible(req.to_rank_id, school_id, db)
        p.to_rank_id = req.to_rank_id
    if req.from_rank_id is not None:
        await _assert_rank_visible(req.from_rank_id, school_id, db)
        p.from_rank_id = req.from_rank_id
    if req.effective_date is not None:
        p.effective_date = req.effective_date
    if req.reason is not None:
        p.reason = req.reason or None
    await db.flush()
    await db.refresh(p, attribute_names=["from_rank", "to_rank"])
    return _promotion_to_read(p)


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


async def list_pending_leave(school_id: uuid.UUID, db: AsyncSession) -> list[LeaveRead]:
    leaves = list(await db.scalars(
        select(StaffLeave)
        .where(StaffLeave.school_id == school_id, StaffLeave.status == LeaveStatus.PENDING)
        .order_by(StaffLeave.created_at)
    ))
    if not leaves:
        return []

    staff_ids = list({l.staff_member_id for l in leaves})
    members = {
        m.id: m for m in await db.scalars(
            select(StaffMember).where(StaffMember.id.in_(staff_ids))
        )
    }

    result = []
    for l in leaves:
        data = LeaveRead.model_validate(l)
        member = members.get(l.staff_member_id)
        if member:
            data.staff_name = f"{member.first_name} {member.last_name}"
            data.staff_number = member.staff_number
        result.append(data)
    return result


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
