"""Staff promotions and leave management.

Separated from services/staff.py to keep files under 300 lines.

PROMOTION INVARIANT
-------------------
Promotions track Ghana GES civil-service grade changes (Teaching or Non-Teaching).
from_grade is null for the first recorded promotion.

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

from sqlalchemy import or_
from app.models.auth import StaffPosition
from app.models.staff import LeaveStatus, StaffLeave, StaffMember, StaffPromotion, staff_member_positions
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
    if req.staff_category == "NON_TEACHING" and not req.non_teaching_group:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="non_teaching_group is required for NON_TEACHING category.")

    promotion = StaffPromotion(
        school_id=school_id,
        staff_member_id=staff_id,
        staff_category=req.staff_category,
        non_teaching_group=req.non_teaching_group,
        from_grade=req.from_grade,
        to_grade=req.to_grade,
        effective_date=req.effective_date,
        reason=req.reason,
        approved_by_id=approved_by_id,
        created_at=_utcnow(),
    )
    db.add(promotion)
    await db.flush()

    # Auto-assign the Teacher position when a TEACHING promotion is recorded.
    if req.staff_category == "TEACHING":
        await _ensure_teacher_position(staff_id, school_id, db)

    return PromotionRead.model_validate(promotion)


async def _ensure_teacher_position(
    staff_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Add the TEACHER position to a staff member if they don't already have it."""
    teacher_pos = await db.scalar(
        select(StaffPosition).where(
            StaffPosition.code == "TEACHER",
            or_(StaffPosition.school_id == school_id, StaffPosition.school_id.is_(None)),
        ).order_by(StaffPosition.school_id.nulls_last()).limit(1)
    )
    if not teacher_pos:
        return

    existing = await db.scalar(
        select(staff_member_positions).where(
            staff_member_positions.c.staff_member_id == staff_id,
            staff_member_positions.c.position_id == teacher_pos.id,
        )
    )
    if not existing:
        await db.execute(
            staff_member_positions.insert().values(
                staff_member_id=staff_id, position_id=teacher_pos.id
            )
        )
        from app.core.permissions import invalidate_permissions
        await invalidate_permissions(staff_id)


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
    return [PromotionRead.model_validate(p) for p in rows]


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


