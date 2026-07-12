"""
Parent/student portal integration tests.
Run inside Docker: docker compose exec api pytest app/tests/test_portal.py -v
"""
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import (
    AcademicTerm, Class, SchoolLevel, Subject, SubjectCatalogue, SubjectType,
)
from app.models.assessments import Assessment, AssessmentType
from app.models.auth import LoginType, User
from app.models.school import School
from app.models.students import Student, StudentClassAssignment, TermEnrollment


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _make_enrollment(
    db: AsyncSession, school: School, student: Student,
    school_class: Class, academic_term: AcademicTerm, enrolled_by: User,
) -> TermEnrollment:
    # Class assignment must exist before term enrollment
    sca = StudentClassAssignment(
        school_id=school.id,
        student_id=student.id,
        class_id=school_class.id,
        academic_year_id=academic_term.academic_year_id,
        assigned_by_id=enrolled_by.id,
        is_active=True,
    )
    db.add(sca)
    await db.flush()

    te = TermEnrollment(
        school_id=school.id,
        student_id=student.id,
        academic_term_id=academic_term.id,
        enrolled_by_id=enrolled_by.id,
        is_active=True,
    )
    db.add(te)
    await db.flush()
    return te


async def _make_student_user(db: AsyncSession, school: School, student: Student) -> User:
    user = User(
        school_id=school.id,
        login_type=LoginType.ADMISSION_ID,
        admission_id=student.admission_number,
        password_hash=hash_password("portal1234"),
        is_active=True,
        student_id=student.id,
    )
    db.add(user)
    await db.flush()
    return user


async def _publish_assessment(
    db: AsyncSession, school: School, school_class: Class, academic_term: AcademicTerm,
) -> None:
    catalogue = SubjectCatalogue(
        school_id=school.id, code="MATH", name="Mathematics",
        subject_type=SubjectType.CORE, level=SchoolLevel.SHS, is_active=True,
    )
    db.add(catalogue)
    await db.flush()
    subject = Subject(
        school_id=school.id, catalogue_id=catalogue.id,
        code="MATH", name="Mathematics", is_active=True,
    )
    at = AssessmentType(
        school_id=school.id, name="End of Term", code="EOT",
        weight=Decimal("100.00"), is_active=True,
    )
    db.add(subject)
    db.add(at)
    await db.flush()
    db.add(Assessment(
        school_id=school.id, class_id=school_class.id,
        subject_id=subject.id, assessment_type_id=at.id,
        academic_term_id=academic_term.id,
        name="End of Term Exam", max_score=Decimal("100.00"), is_published=True,
    ))
    await db.flush()


async def _portal_login(client: AsyncClient, school: School, student: Student) -> dict:
    resp = await client.post("/auth/login", json={
        "login_type": "ADMISSION_ID",
        "identifier": student.admission_number,
        "school_code": school.school_code,
        "password": "portal1234",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_portal_rejects_staff_token(
    client: AsyncClient, auth: dict,
    db_session: AsyncSession, school: School, student: Student,
    school_class: Class, academic_term: AcademicTerm, school_admin: User,
):
    """Staff Bearer token is rejected — portal is for student accounts only."""
    te = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    resp = await client.get(f"/portal/report-cards/{te.id}", headers=auth)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_portal_report_not_published(
    client: AsyncClient,
    db_session: AsyncSession, school: School, student: Student,
    school_class: Class, academic_term: AcademicTerm, school_admin: User,
):
    """403 when no assessment is published for the term."""
    await _make_student_user(db_session, school, student)
    te = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    portal_auth = await _portal_login(client, school, student)

    resp = await client.get(f"/portal/report-cards/{te.id}", headers=portal_auth)
    assert resp.status_code == 403
    assert "published" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_portal_report_pdf_when_published(
    client: AsyncClient,
    db_session: AsyncSession, school: School, student: Student,
    school_class: Class, academic_term: AcademicTerm, school_admin: User,
):
    """200 PDF returned once at least one assessment is published."""
    await _make_student_user(db_session, school, student)
    te = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    await _publish_assessment(db_session, school, school_class, academic_term)
    portal_auth = await _portal_login(client, school, student)

    resp = await client.get(f"/portal/report-cards/{te.id}", headers=portal_auth)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 1000


@pytest.mark.asyncio
async def test_portal_cannot_access_other_student_report(
    client: AsyncClient,
    db_session: AsyncSession, school: School, student: Student,
    school_class: Class, academic_term: AcademicTerm, school_admin: User,
):
    """Student 1 cannot read student 2's enrollment ID."""
    other = Student(
        school_id=school.id, admission_number="STU002",
        first_name="Ama", last_name="Boateng", is_active=True,
    )
    db_session.add(other)
    await db_session.flush()

    other_te = await _make_enrollment(db_session, school, other, school_class, academic_term, school_admin)
    await _make_student_user(db_session, school, student)
    await _publish_assessment(db_session, school, school_class, academic_term)
    portal_auth = await _portal_login(client, school, student)

    resp = await client.get(f"/portal/report-cards/{other_te.id}", headers=portal_auth)
    assert resp.status_code == 404


# ── Self-service discovery (GET /portal/me, GET /portal/term-enrollments) ──────
# Added alongside the frontend portal build: previously a logged-in student had
# no way to discover their own name/class, or which enrollment_id to request a
# report card for.

@pytest.mark.asyncio
async def test_portal_me_returns_own_profile(
    client: AsyncClient,
    db_session: AsyncSession, school: School, student: Student,
    school_class: Class, academic_term: AcademicTerm, school_admin: User,
):
    await _make_student_user(db_session, school, student)
    await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    portal_auth = await _portal_login(client, school, student)

    resp = await client.get("/portal/me", headers=portal_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["admission_number"] == student.admission_number
    assert data["display_name"] == f"{student.first_name} {student.last_name}"
    assert data["current_class_name"]
    assert data["school_name"] == school.name


@pytest.mark.asyncio
async def test_portal_me_rejects_staff_token(client: AsyncClient, auth: dict):
    resp = await client.get("/portal/me", headers=auth)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_portal_list_term_enrollments_reflects_publish_state(
    client: AsyncClient,
    db_session: AsyncSession, school: School, student: Student,
    school_class: Class, academic_term: AcademicTerm, school_admin: User,
):
    await _make_student_user(db_session, school, student)
    te = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    portal_auth = await _portal_login(client, school, student)

    resp = await client.get("/portal/term-enrollments", headers=portal_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == str(te.id)
    assert data[0]["term_name"] == academic_term.name
    assert data[0]["is_published"] is False

    await _publish_assessment(db_session, school, school_class, academic_term)
    resp2 = await client.get("/portal/term-enrollments", headers=portal_auth)
    assert resp2.json()[0]["is_published"] is True


@pytest.mark.asyncio
async def test_portal_list_term_enrollments_only_own(
    client: AsyncClient,
    db_session: AsyncSession, school: School, student: Student,
    school_class: Class, academic_term: AcademicTerm, school_admin: User,
):
    other = Student(
        school_id=school.id, admission_number="STU003",
        first_name="Kofi", last_name="Owusu", is_active=True,
    )
    db_session.add(other)
    await db_session.flush()
    await _make_enrollment(db_session, school, other, school_class, academic_term, school_admin)

    await _make_student_user(db_session, school, student)
    portal_auth = await _portal_login(client, school, student)

    resp = await client.get("/portal/term-enrollments", headers=portal_auth)
    assert resp.status_code == 200
    assert resp.json() == []
