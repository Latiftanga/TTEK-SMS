"""
Diagnostic report integration tests — read-only history of category=DIAGNOSTIC
assessments (services/diagnostics.py).
Run inside Docker: docker compose exec api pytest app/tests/test_diagnostics.py -v
"""
from __future__ import annotations
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import AcademicTerm, Class, ClassSubject, SchoolLevel, Subject, SubjectCatalogue, SubjectType
from app.models.assessments import Assessment, AssessmentCategory, AssessmentType, Score
from app.models.auth import LoginType, StaffPosition, User
from app.models.school import School
from app.models.students import Student


async def _login_as_position(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, position_code: str,
) -> dict:
    """Mirrors test_transcript.py's helper."""
    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == position_code))
    assert pos is not None, "Run seed_reference_data.py first"

    staff_id = (await client.post("/staff", json={
        "staff_number": f"TST-{position_code}", "first_name": "Test", "last_name": position_code.title(),
    }, headers=auth)).json()["id"]
    await client.patch(f"/staff/{staff_id}", json={"position_ids": [str(pos.id)]}, headers=auth)

    email = f"{position_code.lower()}@diag-test.edu.gh"
    db_session.add(User(
        school_id=school.id, login_type=LoginType.EMAIL, email=email,
        password_hash=hash_password("Whatever123!"), is_active=True, staff_member_id=staff_id,
    ))
    await db_session.flush()

    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL", "identifier": email, "password": "Whatever123!",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def subject(db_session: AsyncSession, school, school_class: Class) -> Subject:
    cat = SubjectCatalogue(name="Core Maths", code="MATH_DIAG", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code="MATH_DIAG", name="Core Maths", is_active=True)
    db_session.add(subj)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subj.id, is_active=True))
    await db_session.flush()
    return subj


@pytest.fixture
async def diagnostic_type(db_session: AsyncSession, school) -> AssessmentType:
    t = AssessmentType(
        school_id=school.id, name="Algebra Gap Check", code="ALG_GAP_DIAG",
        weight=Decimal("1.00"), category=AssessmentCategory.DIAGNOSTIC,
    )
    db_session.add(t)
    await db_session.flush()
    return t


@pytest.fixture
async def formative_type(db_session: AsyncSession, school) -> AssessmentType:
    t = AssessmentType(school_id=school.id, name="Class Test", code="CT_DIAG_FIXTURE", weight=Decimal("30.00"))
    db_session.add(t)
    await db_session.flush()
    return t


async def _add_score(
    db_session: AsyncSession, school: School, school_class: Class, subject: Subject,
    assessment_type: AssessmentType, academic_term: AcademicTerm, student: Student, school_admin: User,
    raw_score: Decimal = Decimal("8.00"), max_score: Decimal = Decimal("20.00"),
    recorded_date: date | None = None, is_approved: bool = True,
    description: str | None = "Struggles with fraction simplification.",
) -> Score:
    a = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        assessment_type_id=assessment_type.id, academic_term_id=academic_term.id,
        description=description, recorded_date=recorded_date or date.today(),
        max_score=max_score,
    )
    db_session.add(a)
    await db_session.flush()
    s = Score(
        school_id=school.id, assessment_id=a.id, student_id=student.id,
        raw_score=raw_score, is_approved=is_approved, entered_by_id=school_admin.id,
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.mark.asyncio
async def test_empty_for_student_with_no_diagnostic_records(client: AsyncClient, auth: dict, student: Student):
    resp = await client.get(f"/students/{student.id}/diagnostics", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_returns_approved_diagnostic_record_with_correct_fields(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school: School, student: Student, school_class: Class, subject: Subject,
    diagnostic_type: AssessmentType, academic_term: AcademicTerm, school_admin: User,
):
    await _add_score(
        db_session, school, school_class, subject, diagnostic_type, academic_term, student, school_admin,
        raw_score=Decimal("8.00"), max_score=Decimal("20.00"),
        description="Struggles with fraction simplification.",
    )

    resp = await client.get(f"/students/{student.id}/diagnostics", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    r = data[0]
    assert r["assessment_name"] == "Algebra Gap Check"
    assert r["subject_name"] == "Core Maths"
    assert Decimal(r["raw_score"]) == Decimal("8.00")
    assert Decimal(r["max_score"]) == Decimal("20.00")
    assert r["notes"] == "Struggles with fraction simplification."
    assert "grade" not in r and "letter_grade" not in r


@pytest.mark.asyncio
async def test_excludes_non_diagnostic_scores(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school: School, student: Student, school_class: Class, subject: Subject,
    diagnostic_type: AssessmentType, formative_type: AssessmentType,
    academic_term: AcademicTerm, school_admin: User,
):
    await _add_score(db_session, school, school_class, subject, diagnostic_type, academic_term, student, school_admin)
    await _add_score(
        db_session, school, school_class, subject, formative_type, academic_term, student, school_admin,
        recorded_date=date.today() - timedelta(days=1),
    )

    resp = await client.get(f"/students/{student.id}/diagnostics", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["assessment_name"] == "Algebra Gap Check"


@pytest.mark.asyncio
async def test_excludes_unapproved_diagnostic_score(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school: School, student: Student, school_class: Class, subject: Subject,
    diagnostic_type: AssessmentType, academic_term: AcademicTerm, school_admin: User,
):
    await _add_score(
        db_session, school, school_class, subject, diagnostic_type, academic_term, student, school_admin,
        is_approved=False,
    )

    resp = await client.get(f"/students/{student.id}/diagnostics", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_orders_most_recent_first(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school: School, student: Student, school_class: Class, subject: Subject,
    diagnostic_type: AssessmentType, academic_term: AcademicTerm, school_admin: User,
):
    today = date.today()
    await _add_score(
        db_session, school, school_class, subject, diagnostic_type, academic_term, student, school_admin,
        recorded_date=today - timedelta(days=10), description="Older check.",
    )
    await _add_score(
        db_session, school, school_class, subject, diagnostic_type, academic_term, student, school_admin,
        recorded_date=today, description="Most recent check.",
    )

    resp = await client.get(f"/students/{student.id}/diagnostics", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["notes"] == "Most recent check."
    assert data[1]["notes"] == "Older check."


@pytest.mark.asyncio
async def test_404_for_nonexistent_student(client: AsyncClient, auth: dict):
    resp = await client.get("/students/00000000-0000-0000-0000-000000000000/diagnostics", headers=auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_404_for_caller_outside_view_scope(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school: School, student: Student, redis_permissions: None,
):
    """assessments.view alone doesn't imply cross-class visibility — a
    TEACHER with no ClassTeacher/SubjectTeacher assignment to this student's
    class must 404, matching the same boundary the transcript enforces."""
    teacher_auth = await _login_as_position(client, auth, db_session, school, "TEACHER")
    resp = await client.get(f"/students/{student.id}/diagnostics", headers=teacher_auth)
    assert resp.status_code == 404, resp.text
