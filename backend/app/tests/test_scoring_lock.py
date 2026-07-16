"""
AcademicTerm.results_locked integration tests — the term-level freeze on
scoring, distinct from Assessment.is_published (per-assessment, tested in
test_assessments.py). Also covers the due_date term-bounds sanity check.

Run inside Docker: docker compose exec api pytest app/tests/test_scoring_lock.py -v
"""
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import AcademicTerm, Class
from app.models.assessments import Assessment, AssessmentAuditLog, AssessmentType, Score, ScoreAuditLog
from app.models.auth import LoginType, StaffPosition, User
from app.models.school import School
from app.models.students import Student


async def _login_as_position(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, position_code: str,
) -> dict:
    """Create a staff member holding `position_code`, give them a login, and return
    their bearer-token auth headers."""
    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == position_code))
    assert pos is not None, "Run seed_reference_data.py first"

    staff_id = (await client.post("/staff", json={
        "staff_number": f"TST-{position_code}", "first_name": "Test", "last_name": position_code.title(),
    }, headers=auth)).json()["id"]
    await client.patch(f"/staff/{staff_id}", json={"position_ids": [str(pos.id)]}, headers=auth)

    email = f"{position_code.lower()}@presec-test.edu.gh"
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
async def assessment_type(db_session: AsyncSession, school) -> AssessmentType:
    t = AssessmentType(school_id=school.id, name="Class Test", code="CT_LOCK", weight=Decimal("30.00"))
    db_session.add(t)
    await db_session.flush()
    return t


@pytest.fixture
async def subject(db_session: AsyncSession, school):
    from app.models.academic import SchoolLevel, Subject, SubjectCatalogue, SubjectType
    cat = SubjectCatalogue(name="English", code="ENG_LOCK", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code="ENG_LOCK", name="English", is_active=True)
    db_session.add(subj)
    await db_session.flush()
    return subj


@pytest.fixture
async def assessment(
    db_session: AsyncSession, school, school_class: Class,
    subject, assessment_type: AssessmentType, academic_term: AcademicTerm,
) -> Assessment:
    a = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        assessment_type_id=assessment_type.id, academic_term_id=academic_term.id,
        name="Locked-Term Test", max_score=Decimal("100.00"),
    )
    db_session.add(a)
    await db_session.flush()
    return a


async def _lock_term(client: AsyncClient, auth: dict, term_id) -> None:
    resp = await client.patch(f"/academic/terms/{term_id}", json={"results_locked": True}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["results_locked"] is True


# ── Term lock toggle ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_term_toggles_results_locked(client: AsyncClient, auth: dict, academic_term: AcademicTerm):
    resp = await client.patch(f"/academic/terms/{academic_term.id}", json={
        "results_locked": True,
    }, headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["results_locked"] is True
    assert data["results_locked_by_id"] is not None
    assert data["results_locked_at"] is not None


# ── Submit scores ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_scores_blocked_when_term_locked_without_reason(
    client: AsyncClient, auth: dict, assessment: Assessment, student: Student, academic_term: AcademicTerm,
):
    await _lock_term(client, auth, academic_term.id)
    resp = await client.post(f"/assessments/{assessment.id}/scores", json={
        "scores": [{"student_id": str(student.id), "raw_score": "85.00"}],
    }, headers=auth)
    assert resp.status_code == 423


@pytest.mark.asyncio
async def test_submit_scores_allowed_when_locked_with_reason(
    client: AsyncClient, auth: dict, assessment: Assessment, student: Student,
    academic_term: AcademicTerm, db_session: AsyncSession,
):
    await _lock_term(client, auth, academic_term.id)
    resp = await client.post(f"/assessments/{assessment.id}/scores", json={
        "scores": [{"student_id": str(student.id), "raw_score": "85.00"}],
        "override_reason": "Late transcript correction approved by HOD.",
    }, headers=auth)
    assert resp.status_code == 201
    score_id = resp.json()[0]["id"]
    log = await db_session.scalar(
        select(ScoreAuditLog).where(ScoreAuditLog.score_id == score_id)
    )
    assert log is not None
    assert log.reason == "Late transcript correction approved by HOD."


@pytest.mark.asyncio
async def test_submit_scores_blocked_for_class_teacher_even_with_reason(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    assessment: Assessment, student: Student, academic_term: AcademicTerm, redis_permissions: None,
):
    """CLASS_TEACHER holds enter_scores but not approve_scores — a locked term
    must reject them even when they supply a reason."""
    await _lock_term(client, auth, academic_term.id)
    teacher_auth = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    resp = await client.post(f"/assessments/{assessment.id}/scores", json={
        "scores": [{"student_id": str(student.id), "raw_score": "85.00"}],
        "override_reason": "I really need to enter this.",
    }, headers=teacher_auth)
    assert resp.status_code == 423


# ── Approve scores ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_approve_scores_blocked_when_locked_without_reason(
    client: AsyncClient, auth: dict, assessment: Assessment, student: Student,
    academic_term: AcademicTerm, db_session: AsyncSession,
):
    score = Score(
        school_id=assessment.school_id, assessment_id=assessment.id, student_id=student.id,
        raw_score=Decimal("70.00"), entered_by_id=(await db_session.scalar(select(User).limit(1))).id,
    )
    db_session.add(score)
    await db_session.flush()
    await _lock_term(client, auth, academic_term.id)

    resp = await client.post(f"/assessments/{assessment.id}/scores/approve", json={
        "score_ids": [str(score.id)],
    }, headers=auth)
    assert resp.status_code == 423


@pytest.mark.asyncio
async def test_approve_scores_allowed_when_locked_with_reason(
    client: AsyncClient, auth: dict, assessment: Assessment, student: Student,
    academic_term: AcademicTerm, db_session: AsyncSession,
):
    score = Score(
        school_id=assessment.school_id, assessment_id=assessment.id, student_id=student.id,
        raw_score=Decimal("70.00"), entered_by_id=(await db_session.scalar(select(User).limit(1))).id,
    )
    db_session.add(score)
    await db_session.flush()
    await _lock_term(client, auth, academic_term.id)

    resp = await client.post(f"/assessments/{assessment.id}/scores/approve", json={
        "score_ids": [str(score.id)],
        "override_reason": "HOD-approved correction after lock.",
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.json()[0]["is_approved"] is True


# ── Update / delete assessment ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_assessment_blocked_when_locked_without_reason(
    client: AsyncClient, auth: dict, assessment: Assessment, academic_term: AcademicTerm,
    db_session: AsyncSession,
):
    await _lock_term(client, auth, academic_term.id)
    resp = await client.patch(f"/assessments/{assessment.id}", json={
        "name": "Renamed while locked",
    }, headers=auth)
    assert resp.status_code == 423
    log = await db_session.scalar(
        select(AssessmentAuditLog).where(AssessmentAuditLog.assessment_id == assessment.id)
    )
    assert log is None


@pytest.mark.asyncio
async def test_update_assessment_allowed_when_locked_with_reason(
    client: AsyncClient, auth: dict, assessment: Assessment, academic_term: AcademicTerm,
    db_session: AsyncSession,
):
    await _lock_term(client, auth, academic_term.id)
    resp = await client.patch(f"/assessments/{assessment.id}", json={
        "name": "Renamed with HOD approval",
        "override_reason": "Corrected a typo in the assessment name after lock.",
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed with HOD approval"
    log = await db_session.scalar(
        select(AssessmentAuditLog).where(AssessmentAuditLog.assessment_id == assessment.id)
    )
    assert log is not None
    assert log.reason == "Corrected a typo in the assessment name after lock."
    assert log.old_values["name"] == "Locked-Term Test"
    assert log.new_values["name"] == "Renamed with HOD approval"


@pytest.mark.asyncio
async def test_update_assessment_unlocked_writes_audit_log_without_reason(
    client: AsyncClient, auth: dict, assessment: Assessment, db_session: AsyncSession,
):
    resp = await client.patch(f"/assessments/{assessment.id}", json={
        "max_score": "80.00",
    }, headers=auth)
    assert resp.status_code == 200
    log = await db_session.scalar(
        select(AssessmentAuditLog).where(AssessmentAuditLog.assessment_id == assessment.id)
    )
    assert log is not None
    assert log.reason is None
    assert log.old_values["max_score"] == "100.00"
    assert log.new_values["max_score"] == "80.00"


@pytest.mark.asyncio
async def test_delete_assessment_blocked_when_term_locked(
    client: AsyncClient, auth: dict, assessment: Assessment, academic_term: AcademicTerm,
    db_session: AsyncSession,
):
    await _lock_term(client, auth, academic_term.id)
    resp = await client.delete(f"/assessments/{assessment.id}", headers=auth)
    assert resp.status_code == 423
    # No override path exists for delete — confirm it's still there.
    still_there = await db_session.get(Assessment, assessment.id)
    assert still_there is not None


@pytest.mark.asyncio
async def test_delete_assessment_allowed_when_term_unlocked(
    client: AsyncClient, auth: dict, assessment: Assessment,
):
    resp = await client.delete(f"/assessments/{assessment.id}", headers=auth)
    assert resp.status_code == 204


# ── Assessment due_date term bounds ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_assessment_due_date_outside_term_rejected(
    client: AsyncClient, auth: dict, school_class: Class, subject, assessment_type: AssessmentType,
    academic_term: AcademicTerm,
):
    resp = await client.post("/assessments", json={
        "class_id": str(school_class.id),
        "subject_id": str(subject.id),
        "assessment_type_id": str(assessment_type.id),
        "academic_term_id": str(academic_term.id),
        "name": "Way Out Of Term",
        "max_score": "100.00",
        "due_date": "2026-01-15",  # academic_term ends 2024-12-20
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_assessment_due_date_outside_term_rejected(
    client: AsyncClient, auth: dict, assessment: Assessment,
):
    resp = await client.patch(f"/assessments/{assessment.id}", json={
        "due_date": "2026-01-15",
    }, headers=auth)
    assert resp.status_code == 422
