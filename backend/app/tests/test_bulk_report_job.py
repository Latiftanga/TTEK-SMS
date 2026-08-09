"""
ARQ job integration tests — services/bulk_report_job.py.

_run() (the ARQ job's pure core, called by bulk_generate_report_cards once it
unwraps ctx["db"]) is tested directly against a real DB and real WeasyPrint
PDF rendering, same as test_report_cards.py's single-report tests — there's
no JSON endpoint exposing generated/failed counts (the router only returns
a queued job_id), and driving this through the actual ARQ/Redis queue would
test the queue, not the job logic.

Run inside Docker: docker compose exec api pytest app/tests/test_bulk_report_job.py -v
"""
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.academic import AcademicTerm, Class
from app.models.school import School
from app.models.students import Student, StudentClassAssignment, TermEnrollment
from app.models.auth import User
from app.services import bulk_report_job
from app.services.bulk_report_job import _run


async def _make_enrollment(
    db: AsyncSession, school: School, student: Student,
    school_class: Class, academic_term: AcademicTerm, school_admin: User
) -> TermEnrollment:
    sca = StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=school_class.id,
        academic_year_id=academic_term.academic_year_id,
        assigned_by_id=school_admin.id, is_active=True,
    )
    db.add(sca)
    await db.flush()
    te = TermEnrollment(
        school_id=school.id, student_id=student.id, academic_term_id=academic_term.id,
        enrolled_by_id=school_admin.id, is_active=True,
    )
    db.add(te)
    await db.flush()
    return te


def _read_zip_names(job_id: str) -> list[str]:
    zip_path = Path(settings.local_upload_dir) / "bulk" / f"{job_id}.zip"
    import zipfile
    with zipfile.ZipFile(zip_path) as zf:
        return zf.namelist()


@pytest.mark.asyncio
async def test_bulk_generate_report_cards_creates_zip_for_every_student(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_term: AcademicTerm, school_admin: User, student: Student,
):
    second = Student(
        school_id=school.id, admission_number="STU002",
        first_name="Ama", last_name="Owusu", is_active=True,
    )
    db_session.add(second)
    await db_session.flush()

    await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    await _make_enrollment(db_session, school, second, school_class, academic_term, school_admin)

    job_id = f"test-{uuid.uuid4()}"
    result = await _run(
        db_session, job_id=job_id, class_id=school_class.id,
        academic_term_id=academic_term.id, school_id=school.id,
        user_id=school_admin.id,
    )
    try:
        assert result == {"job_id": job_id, "generated": 2, "failed": 0}
        names = _read_zip_names(job_id)
        assert len(names) == 2
        assert all(name.endswith(".pdf") for name in names)
    finally:
        (Path(settings.local_upload_dir) / "bulk" / f"{job_id}.zip").unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_bulk_generate_report_cards_excludes_withdrawn_student(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_term: AcademicTerm, school_admin: User, student: Student,
):
    """A withdrawn/transferred student (StudentClassAssignment deactivated,
    not deleted, by student_lifecycle.py) must not end up in a class's bulk
    report ZIP alongside current students."""
    withdrawn = Student(
        school_id=school.id, admission_number="STU004",
        first_name="Kojo", last_name="Nyarko", is_active=False,
    )
    db_session.add(withdrawn)
    await db_session.flush()

    await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    await _make_enrollment(db_session, school, withdrawn, school_class, academic_term, school_admin)

    sca = await db_session.scalar(
        select(StudentClassAssignment).where(StudentClassAssignment.student_id == withdrawn.id)
    )
    sca.is_active = False
    te = await db_session.scalar(
        select(TermEnrollment).where(TermEnrollment.student_id == withdrawn.id)
    )
    te.is_active = False
    await db_session.flush()

    job_id = f"test-{uuid.uuid4()}"
    result = await _run(
        db_session, job_id=job_id, class_id=school_class.id,
        academic_term_id=academic_term.id, school_id=school.id,
        user_id=school_admin.id,
    )
    try:
        assert result == {"job_id": job_id, "generated": 1, "failed": 0}
        names = _read_zip_names(job_id)
        assert len(names) == 1
    finally:
        (Path(settings.local_upload_dir) / "bulk" / f"{job_id}.zip").unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_bulk_generate_report_cards_isolates_a_single_student_failure(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_term: AcademicTerm, school_admin: User, student: Student, monkeypatch,
):
    """One student's assemble() failing must not crash the batch or drop the
    other students — it's recorded as an error file and counted in `failed`."""
    second = Student(
        school_id=school.id, admission_number="STU003",
        first_name="Yaw", last_name="Boateng", is_active=True,
    )
    db_session.add(second)
    await db_session.flush()

    te_ok = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    await _make_enrollment(db_session, school, second, school_class, academic_term, school_admin)

    real_assemble = bulk_report_job.assemble

    async def _flaky_assemble(enrollment_id, school_id, user_id, db):
        if enrollment_id == te_ok.id:
            raise RuntimeError("simulated assembly failure")
        return await real_assemble(enrollment_id, school_id, user_id, db)

    monkeypatch.setattr(bulk_report_job, "assemble", _flaky_assemble)

    job_id = f"test-{uuid.uuid4()}"
    result = await _run(
        db_session, job_id=job_id, class_id=school_class.id,
        academic_term_id=academic_term.id, school_id=school.id,
        user_id=school_admin.id,
    )
    try:
        assert result == {"job_id": job_id, "generated": 1, "failed": 1}
        names = _read_zip_names(job_id)
        assert any(name.endswith(".pdf") for name in names)
        assert any(name.startswith("error_") for name in names)
    finally:
        (Path(settings.local_upload_dir) / "bulk" / f"{job_id}.zip").unlink(missing_ok=True)
