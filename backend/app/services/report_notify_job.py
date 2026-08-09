"""
ARQ job: notify_class_report_published

Fires the "report is ready" SMS + email to every active guardian in a class
for a term — the guardian-facing side effect of publish_assessment() /
bulk_publish_assessments() (services/assessment_publish.py), moved off the
request path since it's O(class size) sequential external calls (SMS
gateway + SMTP) that would otherwise block the publish HTTP request. Same
fire-and-forget guarantee as the notify_* functions themselves — a failed
send here never affects anything else, it just doesn't log a SENT row.

_run() only flushes, never commits — matching every other service function
in this codebase (the commit boundary belongs to whichever layer owns the
session: get_db() for an HTTP request, notify_class_report_published's own
`async with AsyncSessionLocal()` here). Tests call _run() directly against
the shared db_session fixture, same convention as bulk_report_job.py.
"""
from __future__ import annotations
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm
from app.models.school import School
from app.models.students import StudentClassAssignment
from app.services import email_notifications as email_svc
from app.services import sms_notifications as sms_svc


async def notify_class_report_published(
    ctx: dict,
    class_id: str,
    academic_term_id: str,
    school_id: str,
    entity_id: str,
) -> dict:
    """ARQ job — runs in the worker process."""
    AsyncSessionLocal = ctx["db"]
    async with AsyncSessionLocal() as db:
        result = await _run(
            db,
            class_id=uuid.UUID(class_id),
            academic_term_id=uuid.UUID(academic_term_id),
            school_id=uuid.UUID(school_id),
            entity_id=uuid.UUID(entity_id),
        )
        await db.commit()
        return result


async def _run(
    db: AsyncSession,
    class_id: uuid.UUID,
    academic_term_id: uuid.UUID,
    school_id: uuid.UUID,
    entity_id: uuid.UUID,
) -> dict:
    school = await db.get(School, school_id)
    term = await db.get(AcademicTerm, academic_term_id)
    if not school or not term:
        return {"notified": 0}

    assignments = await db.scalars(
        select(StudentClassAssignment).where(
            StudentClassAssignment.class_id == class_id,
            StudentClassAssignment.academic_year_id == term.academic_year_id,
            StudentClassAssignment.school_id == school_id,
            StudentClassAssignment.is_active.is_(True),
        )
    )
    notified = 0
    for sca in assignments:
        await sms_svc.notify_report_published(
            student_id=sca.student_id,
            school_id=school_id,
            school_short=school.short_name or school.name,
            school_code=school.school_code,
            term_name=term.name,
            entity_id=entity_id,
            db=db,
        )
        await email_svc.notify_report_published_email(
            student_id=sca.student_id,
            school_id=school_id,
            school_short=school.short_name or school.name,
            school_code=school.school_code,
            term_name=term.name,
            entity_id=entity_id,
            db=db,
        )
        notified += 1

    return {"notified": notified}
