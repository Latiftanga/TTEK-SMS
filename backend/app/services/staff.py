"""Staff member CRUD: create, list, get, update, emergency contacts, qualifications.
Promotions/leave: services/staff_leave.py. Photo upload/delete: services/staff_photo.py.
Last-administrator protection: services/staff_admin_guard.py.
"""
from __future__ import annotations
import uuid
from fastapi import HTTPException, status
from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sqlalchemy import func
from app.models.staff import StaffMember, staff_member_positions
from app.models.auth import StaffPosition, User
from app.services.staff_query import staff_search_condition
from app.schemas.staff import (
    QualificationRead,
    EmergencyContactRead,
    StaffMemberCreate,
    StaffMemberDetail,
    StaffMemberSummary,
    StaffMemberUpdate,
)
from app.services.staff_admin_guard import guard_last_admin, guard_last_admin_deactivation


def _photo_url(photo_path: str | None) -> str | None:
    """Stored path -> absolute URL. Mirrors student_display.py::_photo_url as
    its own small copy rather than a cross-domain import."""
    if not photo_path:
        return None
    from app.core.config import settings
    if settings.storage_backend == "CLOUDFLARE_R2":
        return f"{settings.r2_public_url.rstrip('/')}/{photo_path}"
    return f"{settings.app_base_url.rstrip('/')}/uploads/{photo_path}"


async def _assert_positions_owned(
    position_ids: list[uuid.UUID],
    school_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Every position_id being assigned must be either a shared platform
    template (school_id IS NULL) or one this school owns/forked — without
    this, nothing stopped a caller from linking a staff member to a
    *different* school's own forked position (routers/permissions.py's
    fork-on-edit, 12ap). resolve_permissions() unions permissions purely by
    position_id with no school check of its own, so that would directly
    grant the foreign position's exact permission set — and keep tracking
    it, so a later edit to that other school's fork silently changes this
    staff member's permissions too."""
    if not position_ids:
        return
    owned = set(await db.scalars(
        select(StaffPosition.id).where(
            StaffPosition.id.in_(position_ids),
            or_(StaffPosition.school_id == school_id, StaffPosition.school_id.is_(None)),
        )
    ))
    if set(position_ids) - owned:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found.")


def _display_name(first: str, middle: str | None, last: str) -> str:
    parts = [first]
    if middle:
        parts.append(middle)
    parts.append(last)
    return " ".join(parts)


def _to_summary(member: StaffMember) -> StaffMemberSummary:
    return StaffMemberSummary(
        id=member.id,
        school_id=member.school_id,
        staff_number=member.staff_number,
        first_name=member.first_name,
        middle_name=member.middle_name,
        last_name=member.last_name,
        display_name=_display_name(member.first_name, member.middle_name, member.last_name),
        category_id=member.category_id,
        category_name=member.category.name if member.category else None,
        staff_type=member.category.staff_type if member.category else None,
        gender=member.gender,
        employment_type=member.employment_type,
        phone=member.phone,
        email=member.email,
        position_ids=[p.id for p in member.positions],
        position_names=[p.name for p in member.positions],
        is_active=member.is_active,
        joined_date=member.joined_date,
        photo_url=_photo_url(member.photo_path),
    )


def _to_detail(member: StaffMember, has_account: bool = False) -> StaffMemberDetail:
    return StaffMemberDetail(
        **_to_summary(member).model_dump(),
        date_of_birth=member.date_of_birth,
        marital_status=member.marital_status,
        national_id=member.national_id,
        ssnit_number=member.ssnit_number,
        address=member.address,
        photo_path=member.photo_path,
        has_account=has_account,
        qualifications=[QualificationRead.model_validate(q) for q in member.qualifications],
        emergency_contacts=[EmergencyContactRead.model_validate(c) for c in member.emergency_contacts],
    )


async def create_staff(
    req: StaffMemberCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> StaffMemberDetail:
    await _assert_positions_owned(req.position_ids, school_id, db)
    member = StaffMember(
        school_id=school_id,
        staff_number=req.staff_number.strip(),
        first_name=req.first_name.strip(),
        middle_name=req.middle_name.strip() if req.middle_name else None,
        last_name=req.last_name.strip(),
        category_id=req.category_id,
        date_of_birth=req.date_of_birth,
        gender=req.gender,
        employment_type=req.employment_type,
        marital_status=req.marital_status,
        national_id=req.national_id,
        ssnit_number=req.ssnit_number,
        address=req.address,
        phone=req.phone,
        email=req.email.lower().strip() if req.email else None,
        is_active=True,
        joined_date=req.joined_date,
    )
    db.add(member)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Staff number '{req.staff_number}' is already in use at this school.",
        )
    if req.position_ids:
        await db.execute(
            staff_member_positions.insert(),
            [{"staff_member_id": member.id, "position_id": pid} for pid in req.position_ids],
        )
    await db.refresh(member, attribute_names=["positions", "qualifications", "emergency_contacts", "category"])
    return _to_detail(member)


async def list_staff(
    school_id: uuid.UUID,
    db: AsyncSession,
    *,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 50,
    search: str | None = None,
    gender: str | None = None,
    category_id: uuid.UUID | None = None,
) -> tuple[list[StaffMemberSummary], int]:
    base = select(StaffMember).where(StaffMember.school_id == school_id)
    if active_only:
        base = base.where(StaffMember.is_active == True)
    if category_id:
        base = base.where(StaffMember.category_id == category_id)
    if gender:
        base = base.where(StaffMember.gender == gender)
    if search:
        base = base.where(staff_search_condition(search))

    total = await db.scalar(select(func.count()).select_from(base.subquery()))

    q = (
        base
        .options(selectinload(StaffMember.positions), selectinload(StaffMember.category))
        .order_by(StaffMember.last_name, StaffMember.first_name)
        .offset(skip)
        .limit(limit)
    )
    members = await db.scalars(q)
    return [_to_summary(m) for m in members], total


async def get_staff(
    staff_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> StaffMemberDetail:
    member = await db.scalar(
        select(StaffMember)
        .where(StaffMember.id == staff_id, StaffMember.school_id == school_id)
        .options(
            selectinload(StaffMember.positions),
            selectinload(StaffMember.qualifications),
            selectinload(StaffMember.emergency_contacts),
            selectinload(StaffMember.category),
        )
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")
    has_account = bool(await db.scalar(select(User.id).where(User.staff_member_id == staff_id)))
    return _to_detail(member, has_account=has_account)


async def update_staff(
    staff_id: uuid.UUID,
    req: StaffMemberUpdate,
    school_id: uuid.UUID,
    db: AsyncSession,
    changed_by_id: uuid.UUID | None = None,
) -> StaffMemberDetail:
    member = await db.scalar(
        select(StaffMember)
        .where(StaffMember.id == staff_id, StaffMember.school_id == school_id)
        .options(
            selectinload(StaffMember.positions),
            selectinload(StaffMember.qualifications),
            selectinload(StaffMember.emergency_contacts),
            selectinload(StaffMember.category),
        )
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")

    update_data = req.model_dump(exclude_unset=True)
    new_position_ids: list[uuid.UUID] | None = update_data.pop("position_ids", None)

    was_active   = member.is_active
    deactivating = was_active and update_data.get("is_active") is False
    reactivating = (not was_active) and update_data.get("is_active") is True

    if deactivating:
        await guard_last_admin_deactivation(staff_id, school_id, db)

    for field, val in update_data.items():
        setattr(member, field, val)

    if new_position_ids is not None:
        await _assert_positions_owned(new_position_ids, school_id, db)
        await guard_last_admin(staff_id, school_id, new_position_ids, db)

        old_position_ids = [p.id for p in member.positions]

        await db.execute(
            delete(staff_member_positions).where(
                staff_member_positions.c.staff_member_id == staff_id
            )
        )
        if new_position_ids:
            await db.execute(
                staff_member_positions.insert(),
                [{"staff_member_id": staff_id, "position_id": pid} for pid in new_position_ids],
            )
        await db.refresh(member, attribute_names=["positions"])
        from app.core.permissions import invalidate_permissions
        await invalidate_permissions(staff_id)

        # Grants system access — the router requires school.manage_users to
        # even reach here, but log it regardless of caller (e.g. superadmin)
        # since this is a security-sensitive change, not just a profile edit.
        from datetime import datetime, timezone
        from app.models.auth import AuditLog
        db.add(AuditLog(
            school_id=school_id, user_id=changed_by_id, action="STAFF_POSITION_CHANGE",
            entity_type="StaffMember", entity_id=staff_id,
            old_values={"position_ids": [str(p) for p in old_position_ids]},
            new_values={"position_ids": [str(p) for p in new_position_ids]},
            created_at=datetime.now(timezone.utc),
        ))

    if deactivating or reactivating:
        # StaffMember.is_active and User.is_active are separate fields — without this,
        # a "deactivated" staff member keeps a fully working login and permission cache.
        user = await db.scalar(select(User).where(User.staff_member_id == staff_id))
        if user:
            user.is_active = reactivating

        from app.core.permissions import invalidate_permissions
        await invalidate_permissions(staff_id)

    if deactivating:
        # A deactivated staff member shouldn't keep appearing as an active class
        # teacher / subject teacher / house master — report cards, dashboards, and
        # student-visibility scoping all key off these tables' own is_active flags,
        # not the staff member's. Reactivating does NOT restore these: the class/
        # house may already have a new assignee, so re-assignment is a manual step.
        from app.models.academic import ClassTeacher, SubjectTeacher
        from app.models.housing import HouseMaster

        for model in (ClassTeacher, SubjectTeacher, HouseMaster):
            await db.execute(
                update(model)
                .where(model.staff_member_id == staff_id, model.is_active == True)  # noqa: E712
                .values(is_active=False)
            )

    if "category_id" in update_data:
        await db.refresh(member, attribute_names=["category"])

    await db.flush()
    return _to_detail(member)
