from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.housing_scope import assert_house_in_scope, current_year_id, resolve_house_scope
from app.models.attendance import SchoolCalendar
from app.models.housing import Exeat, ExeatStatus, House, NightRollCall, StudentHouseAssignment
from app.models.students import Student
from app.schemas.housing import (
    ExeatApprove, ExeatCreate, ExeatRead, ExeatReturn,
    RollCallCreate, RollCallRead,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_rollcall(r: NightRollCall) -> RollCallRead:
    return RollCallRead.model_validate(r)


def _row_to_exeat(exeat: Exeat, first_name: str, last_name: str, admission_number: str) -> ExeatRead:
    return ExeatRead(
        id=exeat.id,
        student_id=exeat.student_id,
        student_name=f"{first_name} {last_name}",
        admission_number=admission_number,
        exeat_type=exeat.exeat_type,
        reason=exeat.reason,
        destination=exeat.destination,
        departure_date=exeat.departure_date,
        return_date=exeat.return_date,
        status=exeat.status,
        approved_by_id=exeat.approved_by_id,
        actual_return_date=exeat.actual_return_date,
        created_at=exeat.created_at,
    )


def _exeat_select(*where_clauses):
    """Select Exeat joined with Student fields."""
    return (
        select(Exeat, Student.first_name, Student.last_name, Student.admission_number)
        .join(Student, Student.id == Exeat.student_id)
        .where(*where_clauses)
    )


async def record_roll_call(
    req: RollCallCreate, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> RollCallRead:
    house = await db.scalar(
        select(House).where(House.id == req.house_id, House.school_id == school_id)
    )
    if not house:
        raise HTTPException(404, "House not found.")
    await assert_house_in_scope(req.house_id, user_id, school_id, await current_year_id(school_id, db), db)
    cal = await db.scalar(
        select(SchoolCalendar).where(
            SchoolCalendar.id == req.school_calendar_id,
            SchoolCalendar.school_id == school_id,
        )
    )
    if not cal:
        raise HTTPException(404, "School calendar entry not found for this school.")
    rc = NightRollCall(
        school_id=school_id,
        house_id=req.house_id,
        school_calendar_id=req.school_calendar_id,
        recorded_by_id=user_id,
        recorded_at=_utcnow(),
        total_expected=req.total_expected,
        total_present=req.total_present,
        notes=req.notes,
    )
    db.add(rc)
    await db.flush()
    return _to_rollcall(rc)


async def list_roll_calls(
    house_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession,
    skip: int = 0, limit: int = 50,
) -> list[RollCallRead]:
    await assert_house_in_scope(house_id, user_id, school_id, await current_year_id(school_id, db), db)
    rows = (await db.scalars(
        select(NightRollCall)
        .where(NightRollCall.house_id == house_id, NightRollCall.school_id == school_id)
        .order_by(NightRollCall.recorded_at.desc())
        .offset(skip).limit(limit)
    )).all()
    return [_to_rollcall(r) for r in rows]


async def create_exeat(
    req: ExeatCreate, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> ExeatRead:
    student = await db.scalar(
        select(Student).where(Student.id == req.student_id, Student.school_id == school_id)
    )
    if not student:
        raise HTTPException(404, "Student not found.")

    # Housemaster scoping: if requester manages a house, student must be in that house.
    # HEAD / admin / deputy resolve unrestricted, so they bypass this check.
    scope = await resolve_house_scope(user_id, school_id, await current_year_id(school_id, db), db)
    if scope is not None:
        assignment = await db.scalar(
            select(StudentHouseAssignment).where(
                StudentHouseAssignment.student_id == req.student_id,
                StudentHouseAssignment.house_id.in_(scope),
                StudentHouseAssignment.school_id == school_id,
                StudentHouseAssignment.vacated_at.is_(None),
            )
        )
        if not assignment:
            raise HTTPException(
                403,
                "You can only issue exeats for students assigned to your house.",
            )

    exeat = Exeat(
        school_id=school_id,
        student_id=req.student_id,
        exeat_type=req.exeat_type,
        reason=req.reason,
        destination=req.destination,
        departure_date=req.departure_date,
        return_date=req.return_date,
        status=ExeatStatus.PENDING,
    )
    db.add(exeat)
    await db.flush()
    return _row_to_exeat(exeat, student.first_name, student.last_name, student.admission_number)


async def list_pending_exeats(
    user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession, house_id: uuid.UUID | None = None
) -> list[ExeatRead]:
    """Returns PENDING and APPROVED exeats (all still needing action).
    If house_id is given, restricts to students currently assigned to that
    house — checked against the caller's own scope first (404 if it isn't
    theirs). If omitted and the caller is a scoped housemaster, defaults to
    their own house(s) rather than every exeat school-wide."""
    year_id = await current_year_id(school_id, db)
    if house_id:
        await assert_house_in_scope(house_id, user_id, school_id, year_id, db)
        house_ids: list[uuid.UUID] | None = [house_id]
    else:
        scope = await resolve_house_scope(user_id, school_id, year_id, db)
        house_ids = list(scope) if scope is not None else None

    q = _exeat_select(
        Exeat.school_id == school_id,
        Exeat.status.in_([ExeatStatus.PENDING, ExeatStatus.APPROVED]),
    )
    if house_ids is not None:
        active_in_house = (
            select(StudentHouseAssignment.student_id)
            .where(
                StudentHouseAssignment.house_id.in_(house_ids),
                StudentHouseAssignment.school_id == school_id,
                StudentHouseAssignment.vacated_at.is_(None),
            )
        )
        q = q.where(Exeat.student_id.in_(active_in_house))
    rows = (await db.execute(q.order_by(Exeat.departure_date))).all()
    return [_row_to_exeat(e, fn, ln, an) for e, fn, ln, an in rows]


async def _assert_student_in_scope(
    student_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession, not_found_detail: str,
) -> None:
    """404 (not the student/exeat existing but simply out of a scoped
    housemaster's own house) if the student's current house assignment
    isn't one the caller manages. Unrestricted callers skip the lookup
    entirely."""
    scope = await resolve_house_scope(user_id, school_id, await current_year_id(school_id, db), db)
    if scope is None:
        return
    house_id = await db.scalar(
        select(StudentHouseAssignment.house_id).where(
            StudentHouseAssignment.student_id == student_id,
            StudentHouseAssignment.school_id == school_id,
            StudentHouseAssignment.vacated_at.is_(None),
        )
    )
    if house_id is None or house_id not in scope:
        raise HTTPException(404, not_found_detail)


async def review_exeat(
    exeat_id: uuid.UUID, req: ExeatApprove,
    school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession,
) -> ExeatRead:
    row = (await db.execute(
        _exeat_select(Exeat.id == exeat_id, Exeat.school_id == school_id)
    )).one_or_none()
    if not row:
        raise HTTPException(404, "Exeat not found.")
    exeat, fn, ln, an = row
    await _assert_student_in_scope(exeat.student_id, user_id, school_id, db, "Exeat not found.")
    if exeat.status != ExeatStatus.PENDING:
        raise HTTPException(409, f"Exeat has already been reviewed (status: {exeat.status.value}).")
    exeat.status = req.status
    exeat.approved_by_id = user_id
    await db.flush()
    return _row_to_exeat(exeat, fn, ln, an)


async def record_return(
    exeat_id: uuid.UUID, req: ExeatReturn, user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> ExeatRead:
    row = (await db.execute(
        _exeat_select(Exeat.id == exeat_id, Exeat.school_id == school_id)
    )).one_or_none()
    if not row:
        raise HTTPException(404, "Exeat not found.")
    exeat, fn, ln, an = row
    await _assert_student_in_scope(exeat.student_id, user_id, school_id, db, "Exeat not found.")
    if exeat.status != ExeatStatus.APPROVED:
        raise HTTPException(409, "Only approved exeats can be marked as returned.")
    exeat.status = ExeatStatus.RETURNED
    exeat.actual_return_date = req.actual_return_date
    await db.flush()
    return _row_to_exeat(exeat, fn, ln, an)


async def list_student_exeats(
    student_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> list[ExeatRead]:
    student = await db.scalar(
        select(Student).where(Student.id == student_id, Student.school_id == school_id)
    )
    if not student:
        raise HTTPException(404, "Student not found.")
    await _assert_student_in_scope(student_id, user_id, school_id, db, "Student not found.")
    rows = (await db.execute(
        _exeat_select(Exeat.student_id == student_id, Exeat.school_id == school_id)
        .order_by(Exeat.departure_date.desc())
    )).all()
    return [_row_to_exeat(e, fn, ln, an) for e, fn, ln, an in rows]
