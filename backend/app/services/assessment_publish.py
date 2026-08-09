"""
Assessment publishing — split out of services/assessment.py to stay under
the 300-line cap.

Publishing is one-way — there is no un-publish endpoint — and stays
assessments.approve_scores-gated (routers/assessments.py), unlike
create/update/delete: it's a guardian-facing, notification-firing
finalization step, not "creating an assignment".

Guardian notifications fire only on the FIRST assessment published for a
(class, term) — matching services/portal.py::is_report_published(), which
already unlocks the whole report the moment any one assessment is published
and stays unlocked regardless of how many more are published after. Without
this guard, a class with (typically) dozens of assessments across a term
would re-send the identical "report is ready" SMS/email to every guardian on
every subsequent publish — real SMS cost, and confusing/spammy either way.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm
from app.models.assessments import Assessment
from app.models.school import School
from app.models.students import StudentClassAssignment
from app.schemas.assessments import AssessmentRead
from app.services import email_notifications as email_svc
from app.services import sms_notifications as sms_svc


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

    # Only the first assessment published for this class+term actually
    # changes anything a guardian can see — is_report_published() unlocks on
    # the first one and stays unlocked, so every later publish is a no-op for
    # notification purposes. See the module docstring.
    already_unlocked = await db.scalar(
        select(Assessment.id).where(
            Assessment.class_id == a.class_id,
            Assessment.academic_term_id == a.academic_term_id,
            Assessment.school_id == school_id,
            Assessment.is_published.is_(True),
            Assessment.id != a.id,
        )
    ) is not None

    # Notify guardians of all class members for this academic year
    school = await db.get(School, school_id)
    term = await db.get(AcademicTerm, a.academic_term_id)
    if school and term and not already_unlocked:
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
            await email_svc.notify_report_published_email(
                student_id=sca.student_id,
                school_id=school_id,
                school_short=school.short_name or school.name,
                school_code=school.school_code,
                term_name=term.name,
                entity_id=a.id,
                db=db,
            )

    return AssessmentRead.model_validate(a)
