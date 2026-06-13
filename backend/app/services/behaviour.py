from __future__ import annotations
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm
from app.models.assessments import StudentBehaviourRecord
from app.models.students import Student
from app.schemas.assessments import BehaviourRecordCreate, BehaviourRecordRead


def _to_read(r: StudentBehaviourRecord) -> BehaviourRecordRead:
    return BehaviourRecordRead.model_validate(r)


async def create_behaviour_record(
    req: BehaviourRecordCreate, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> BehaviourRecordRead:
    student = await db.scalar(
        select(Student).where(Student.id == req.student_id, Student.school_id == school_id)
    )
    if not student:
        raise HTTPException(404, "Student not found.")
    term = await db.scalar(
        select(AcademicTerm).where(
            AcademicTerm.id == req.academic_term_id, AcademicTerm.school_id == school_id
        )
    )
    if not term:
        raise HTTPException(404, "Academic term not found.")
    rec = StudentBehaviourRecord(
        school_id=school_id,
        student_id=req.student_id,
        academic_term_id=req.academic_term_id,
        incident_type=req.incident_type,
        description=req.description,
        severity=req.severity,
        action_taken=req.action_taken,
        incident_date=req.incident_date,
        recorded_by_id=user_id,
    )
    db.add(rec)
    await db.flush()
    return _to_read(rec)


async def list_behaviour_records(
    student_id: uuid.UUID, term_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> list[BehaviourRecordRead]:
    student = await db.scalar(
        select(Student).where(Student.id == student_id, Student.school_id == school_id)
    )
    if not student:
        raise HTTPException(404, "Student not found.")
    rows = (await db.scalars(
        select(StudentBehaviourRecord)
        .where(
            StudentBehaviourRecord.student_id == student_id,
            StudentBehaviourRecord.academic_term_id == term_id,
            StudentBehaviourRecord.school_id == school_id,
        )
        .order_by(StudentBehaviourRecord.incident_date)
    )).all()
    return [_to_read(r) for r in rows]


async def delete_behaviour_record(
    record_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> None:
    rec = await db.scalar(
        select(StudentBehaviourRecord).where(
            StudentBehaviourRecord.id == record_id,
            StudentBehaviourRecord.school_id == school_id,
        )
    )
    if not rec:
        raise HTTPException(404, "Behaviour record not found.")
    await db.delete(rec)
