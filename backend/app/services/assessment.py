"""
AssessmentType and Assessment CRUD.

Assessment.is_published gates report card access (parent portal checks this).
Publishing is one-way — there is no un-publish endpoint.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm
from app.models.assessments import Assessment, AssessmentType, Score
from app.models.school import School
from app.models.students import StudentClassAssignment
from app.schemas.assessments import (
    AssessmentCreate, AssessmentRead, AssessmentUpdate,
    AssessmentTypeCreate, AssessmentTypeRead, AssessmentTypeUpdate,
)
from app.services import sms_notifications as sms_svc


# ── AssessmentType ────────────────────────────────────────────────────────────

def _type_read(t: AssessmentType) -> AssessmentTypeRead:
    return AssessmentTypeRead.model_validate(t)


async def create_assessment_type(
    req: AssessmentTypeCreate, school_id: uuid.UUID, db: AsyncSession
) -> AssessmentTypeRead:
    existing = await db.scalar(
        select(AssessmentType).where(
            AssessmentType.school_id == school_id,
            (AssessmentType.code == req.code) | (AssessmentType.name == req.name),
        )
    )
    if existing:
        field = "code" if existing.code == req.code else "name"
        value = req.code if field == "code" else req.name
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Assessment type with {field} '{value}' already exists.",
        )
    t = AssessmentType(
        school_id=school_id,
        name=req.name,
        code=req.code,
        weight=req.weight,
    )
    db.add(t)
    await db.flush()
    return _type_read(t)


async def update_assessment_type(
    type_id: uuid.UUID, req: AssessmentTypeUpdate, school_id: uuid.UUID, db: AsyncSession
) -> AssessmentTypeRead:
    t = await db.scalar(
        select(AssessmentType).where(
            AssessmentType.id == type_id, AssessmentType.school_id == school_id
        )
    )
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment type not found.")
    if req.name is not None or req.code is not None:
        conflict = await db.scalar(
            select(AssessmentType).where(
                AssessmentType.school_id == school_id,
                AssessmentType.id != type_id,
                (AssessmentType.name == req.name) | (AssessmentType.code == req.code),
            )
        )
        if conflict:
            field = "name" if conflict.name == req.name else "code"
            value = req.name if field == "name" else req.code
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Assessment type with {field} '{value}' already exists.",
            )
    if req.name is not None:
        t.name = req.name
    if req.code is not None:
        t.code = req.code
    if req.weight is not None:
        t.weight = req.weight
    await db.flush()
    return _type_read(t)


async def list_assessment_types(
    school_id: uuid.UUID, db: AsyncSession
) -> list[AssessmentTypeRead]:
    rows = await db.scalars(
        select(AssessmentType)
        .where(AssessmentType.school_id == school_id, AssessmentType.is_active.is_(True))
        .order_by(AssessmentType.name)
    )
    return [_type_read(t) for t in rows]


# ── Assessment ────────────────────────────────────────────────────────────────

def _assessment_read(a: Assessment) -> AssessmentRead:
    return AssessmentRead.model_validate(a)


async def create_assessment(
    req: AssessmentCreate, school_id: uuid.UUID, db: AsyncSession
) -> AssessmentRead:
    atype = await db.scalar(
        select(AssessmentType).where(
            AssessmentType.id == req.assessment_type_id,
            AssessmentType.school_id == school_id,
        )
    )
    if not atype:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment type not found.")
    term = await db.scalar(
        select(AcademicTerm).where(
            AcademicTerm.id == req.academic_term_id, AcademicTerm.school_id == school_id,
        )
    )
    if not term:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Academic term not found.")
    if req.due_date and not (term.start_date <= req.due_date <= term.end_date):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"due_date {req.due_date} falls outside the term ({term.start_date} – {term.end_date}).",
        )
    a = Assessment(
        school_id=school_id,
        class_id=req.class_id,
        subject_id=req.subject_id,
        assessment_type_id=req.assessment_type_id,
        academic_term_id=req.academic_term_id,
        name=req.name,
        max_score=req.max_score,
        due_date=req.due_date,
    )
    db.add(a)
    await db.flush()
    return _assessment_read(a)


async def list_assessments(
    class_id: uuid.UUID, term_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> list[AssessmentRead]:
    rows = await db.scalars(
        select(Assessment).where(
            Assessment.class_id == class_id,
            Assessment.academic_term_id == term_id,
            Assessment.school_id == school_id,
        ).order_by(Assessment.due_date, Assessment.name)
    )
    return [_assessment_read(a) for a in rows]


async def get_assessment(
    assessment_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> AssessmentRead:
    a = await db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.school_id == school_id
        )
    )
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment not found.")
    return _assessment_read(a)


async def update_assessment(
    assessment_id: uuid.UUID, req: AssessmentUpdate, school_id: uuid.UUID, db: AsyncSession
) -> AssessmentRead:
    a = await db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.school_id == school_id
        )
    )
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment not found.")
    if a.is_published:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Cannot edit a published assessment.")
    if req.due_date is not None:
        term = await db.get(AcademicTerm, a.academic_term_id)
        if term and not (term.start_date <= req.due_date <= term.end_date):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"due_date {req.due_date} falls outside the term ({term.start_date} – {term.end_date}).",
            )
    if req.max_score is not None:
        max_entered = await db.scalar(
            select(func.max(Score.raw_score)).where(Score.assessment_id == assessment_id)
        )
        if max_entered is not None and max_entered > req.max_score:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Cannot reduce max score: existing score of {max_entered} would exceed it.",
            )
    if req.name is not None:
        a.name = req.name
    if req.max_score is not None:
        a.max_score = req.max_score
    if req.due_date is not None:
        a.due_date = req.due_date
    await db.flush()
    return _assessment_read(a)


async def delete_assessment(
    assessment_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> None:
    a = await db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.school_id == school_id
        )
    )
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment not found.")
    if a.is_published:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Cannot delete a published assessment.")
    await db.delete(a)
    await db.flush()


async def publish_assessment(
    assessment_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> AssessmentRead:
    a = await db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.school_id == school_id
        )
    )
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment not found.")
    a.is_published = True
    await db.flush()

    # Notify guardians of all class members for this academic year
    school = await db.get(School, school_id)
    term = await db.get(AcademicTerm, a.academic_term_id)
    if school and term:
        assignments = await db.scalars(
            select(StudentClassAssignment).where(
                StudentClassAssignment.class_id == a.class_id,
                StudentClassAssignment.academic_year_id == term.academic_year_id,
                StudentClassAssignment.school_id == school_id,
                StudentClassAssignment.is_active.is_(True),
            )
        )
        for sca in assignments:
            await sms_svc.notify_report_published(
                student_id=sca.student_id,
                school_id=school_id,
                school_short=school.short_name or school.name,
                school_code=school.school_code,
                term_name=term.name,
                entity_id=a.id,
                db=db,
            )

    return _assessment_read(a)
