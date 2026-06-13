"""
AssessmentType and Assessment CRUD.

Assessment.is_published gates report card access (parent portal checks this).
Publishing is one-way — there is no un-publish endpoint.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessments import Assessment, AssessmentType
from app.models.school import School
from app.models.students import TermEnrollment
from app.schemas.assessments import (
    AssessmentCreate, AssessmentRead,
    AssessmentTypeCreate, AssessmentTypeRead,
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
            AssessmentType.code == req.code,
            AssessmentType.school_id == school_id,
        )
    )
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Assessment type with code '{req.code}' already exists.",
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

    # Notify guardians of all enrolled students in this class+term
    school = await db.get(School, school_id)
    from app.models.academic import AcademicTerm
    term = await db.get(AcademicTerm, a.academic_term_id)
    if school and term:
        enrollments = await db.scalars(
            select(TermEnrollment).where(
                TermEnrollment.class_id == a.class_id,
                TermEnrollment.academic_term_id == a.academic_term_id,
                TermEnrollment.school_id == school_id,
                TermEnrollment.is_active.is_(True),
            )
        )
        for enrollment in enrollments:
            await sms_svc.notify_report_published(
                student_id=enrollment.student_id,
                school_id=school_id,
                school_short=school.short_name or school.name,
                school_code=school.school_code,
                term_name=term.name,
                entity_id=a.id,
                db=db,
            )

    return _assessment_read(a)
