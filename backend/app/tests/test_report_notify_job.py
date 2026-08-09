"""
ARQ job integration tests — services/report_notify_job.py.

_run() (the ARQ job's pure core, called by notify_class_report_published once
it unwraps ctx["db"]) is tested directly against a real DB, same convention
as test_bulk_report_job.py — there's no JSON endpoint exposing "notified"
counts, and driving this through the actual ARQ/Redis queue would test the
queue, not the job logic. Enqueue-once-per-class+term behavior (the caller's
responsibility, not this job's) is covered separately in test_assessments.py.

Run inside Docker: docker compose exec api pytest app/tests/test_report_notify_job.py -v
"""
import unittest.mock as mock
import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class
from app.models.school import EmailConfig, EmailLog, EmailProvider, School
from app.models.students import Guardian, Student, StudentClassAssignment, StudentGuardian
from app.services.report_notify_job import _run


@pytest.mark.asyncio
async def test_run_notifies_every_active_guardian_in_the_class(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_term: AcademicTerm, student: Student,
):
    guardian = Guardian(
        school_id=school.id, first_name="Ama", last_name="Owusu",
        phone="0244000002", email="ama.owusu@example.com",
    )
    db_session.add(guardian)
    await db_session.flush()
    db_session.add(StudentGuardian(
        school_id=school.id, student_id=student.id, guardian_id=guardian.id,
        relation_type="Mother", is_primary=True,
    ))
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=school_class.id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    db_session.add(EmailConfig(
        school_id=school.id, provider=EmailProvider.SENDGRID,
        username="test-sendgrid-key", from_name="Test School",
        from_address="noreply@testschool.edu.gh", is_active=True,
    ))
    await db_session.flush()

    class _MockTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(202, json={})

    original_init = httpx.AsyncClient.__init__
    with mock.patch("httpx.AsyncClient.__init__", lambda self, **kw: original_init(
        self, transport=_MockTransport(), **{k: v for k, v in kw.items() if k != "transport"}
    )):
        result = await _run(
            db_session,
            class_id=school_class.id,
            academic_term_id=academic_term.id,
            school_id=school.id,
            entity_id=uuid.uuid4(),
        )

    assert result == {"notified": 1}
    logs = (await db_session.scalars(
        select(EmailLog).where(
            EmailLog.school_id == school.id, EmailLog.entity_type == "REPORT_CARD",
        )
    )).all()
    assert len(logs) == 1
    assert logs[0].recipient == "ama.owusu@example.com"


@pytest.mark.asyncio
async def test_run_only_notifies_active_class_assignments(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_term: AcademicTerm, student: Student,
):
    """A withdrawn/transferred student (StudentClassAssignment deactivated,
    not deleted, by student_lifecycle.py) must not receive a notification —
    same is_active convention every other read site in this codebase uses."""
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=school_class.id,
        academic_year_id=academic_term.academic_year_id, is_active=False,
    ))
    await db_session.flush()

    result = await _run(
        db_session,
        class_id=school_class.id,
        academic_term_id=academic_term.id,
        school_id=school.id,
        entity_id=uuid.uuid4(),
    )
    assert result == {"notified": 0}


@pytest.mark.asyncio
async def test_run_returns_zero_for_unknown_term(db_session: AsyncSession, school: School, school_class: Class):
    result = await _run(
        db_session,
        class_id=school_class.id,
        academic_term_id=uuid.uuid4(),
        school_id=school.id,
        entity_id=uuid.uuid4(),
    )
    assert result == {"notified": 0}
