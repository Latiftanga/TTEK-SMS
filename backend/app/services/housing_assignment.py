from __future__ import annotations
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.housing_scope import assert_house_in_scope, current_year_id, resolve_house_scope
from app.models.housing import House, HouseGender, Room, StudentHouseAssignment
from app.models.students import Student
from app.schemas.housing import (
    AssignmentCreate, AssignmentRead, AssignmentVacate, StudentInHouseRead,
)


def _to_assignment(a: StudentHouseAssignment) -> AssignmentRead:
    return AssignmentRead.model_validate(a)


async def assign_student(
    req: AssignmentCreate, user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession,
) -> AssignmentRead:
    student = await db.scalar(
        select(Student).where(Student.id == req.student_id, Student.school_id == school_id)
    )
    if not student:
        raise HTTPException(404, "Student not found.")
    house = await db.scalar(
        select(House).where(House.id == req.house_id, House.school_id == school_id)
    )
    if not house:
        raise HTTPException(404, "House not found.")
    await assert_house_in_scope(req.house_id, user_id, school_id, req.academic_year_id, db)
    if house.gender != HouseGender.MIXED:
        if student.gender is None:
            raise HTTPException(
                422, "Student gender must be recorded before assigning to a single-gender house."
            )
        if student.gender.value != house.gender.value:
            raise HTTPException(
                422,
                f"{house.gender.value.title()} house cannot accept a {student.gender.value.title()} student.",
            )
    if req.room_id:
        room = await db.scalar(
            select(Room).where(
                Room.id == req.room_id,
                Room.house_id == req.house_id,
                Room.school_id == school_id,
            )
        )
        if not room:
            raise HTTPException(404, "Room not found in this house.")
    existing = await db.scalar(
        select(StudentHouseAssignment).where(
            StudentHouseAssignment.student_id == req.student_id,
            StudentHouseAssignment.academic_year_id == req.academic_year_id,
            StudentHouseAssignment.school_id == school_id,
            StudentHouseAssignment.vacated_at.is_(None),
        )
    )
    if existing:
        raise HTTPException(409, "Student already has an active house assignment for this academic year.")
    assignment = StudentHouseAssignment(
        school_id=school_id,
        student_id=req.student_id,
        house_id=req.house_id,
        room_id=req.room_id,
        academic_year_id=req.academic_year_id,
        assigned_at=req.assigned_at,
    )
    db.add(assignment)
    # A student living in a house is a boarder by definition — keeps boarding_only
    # fee structures (services/fees.py) from silently missing them. Vacating a room
    # deliberately does not reverse this — that's a separate administrative decision.
    if not student.is_boarding:
        student.is_boarding = True
    await db.flush()
    return _to_assignment(assignment)


async def vacate_assignment(
    assignment_id: uuid.UUID, req: AssignmentVacate, user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> AssignmentRead:
    assignment = await db.scalar(
        select(StudentHouseAssignment).where(
            StudentHouseAssignment.id == assignment_id,
            StudentHouseAssignment.school_id == school_id,
        )
    )
    if not assignment:
        raise HTTPException(404, "Assignment not found.")
    await assert_house_in_scope(assignment.house_id, user_id, school_id, assignment.academic_year_id, db)
    if assignment.vacated_at:
        raise HTTPException(409, "Assignment is already vacated.")
    if req.vacated_at < assignment.assigned_at:
        raise HTTPException(422, "vacated_at must be on or after assigned_at.")
    assignment.vacated_at = req.vacated_at
    await db.flush()
    return _to_assignment(assignment)


async def get_student_current_assignment(
    student_id: uuid.UUID, year_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> AssignmentRead | None:
    assignment = await db.scalar(
        select(StudentHouseAssignment).where(
            StudentHouseAssignment.student_id == student_id,
            StudentHouseAssignment.academic_year_id == year_id,
            StudentHouseAssignment.school_id == school_id,
            StudentHouseAssignment.vacated_at.is_(None),
        )
    )
    if not assignment:
        return None
    # A scoped housemaster looking up a student outside their own house gets
    # the same "nothing to see" response as no assignment at all — never a
    # signal that the student is (or was) assigned somewhere else.
    scope = await resolve_house_scope(user_id, school_id, year_id, db)
    if scope is not None and assignment.house_id not in scope:
        return None
    return _to_assignment(assignment)


async def list_house_students(
    house_id: uuid.UUID, user_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> list[StudentInHouseRead]:
    await assert_house_in_scope(house_id, user_id, school_id, await current_year_id(school_id, db), db)
    rows = (await db.execute(
        select(
            StudentHouseAssignment.id,
            StudentHouseAssignment.student_id,
            StudentHouseAssignment.assigned_at,
            Student.first_name, Student.last_name,
            Student.admission_number, Student.gender,
            Room.room_number,
        )
        .join(Student, Student.id == StudentHouseAssignment.student_id)
        .outerjoin(Room, Room.id == StudentHouseAssignment.room_id)
        .where(
            StudentHouseAssignment.house_id == house_id,
            StudentHouseAssignment.school_id == school_id,
            StudentHouseAssignment.vacated_at.is_(None),
        )
        .order_by(Student.last_name, Student.first_name)
    )).all()
    return [
        StudentInHouseRead(
            assignment_id=r.id,
            student_id=r.student_id,
            student_name=f"{r.first_name} {r.last_name}",
            admission_number=r.admission_number,
            gender=r.gender,
            room_number=r.room_number,
            assigned_at=r.assigned_at,
        )
        for r in rows
    ]
