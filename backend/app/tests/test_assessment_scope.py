"""
Teacher-role scoping for assessments/scoring — a CLASS_TEACHER holds
assessments.enter_scores/view but should only reach assessments for
(class, subject) combos they are the SubjectTeacher of, matching the user's
own framing ("he/she should see only the subjects or classes he/she is
assign to teach"). assessments.approve_scores holders (HOD/EXAM_OFFICER/
HEAD/DEPUTY_HEAD) are never scoped — they need cross-class oversight.

Run inside Docker: docker compose exec api pytest app/tests/test_assessment_scope.py -v
"""
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import (
    AcademicTerm, Class, ClassSubject, SchoolLevel, Subject, SubjectCatalogue,
    SubjectTeacher, SubjectType,
)
from app.models.assessments import Assessment, AssessmentType
from app.models.auth import LoginType, StaffPosition, User
from app.models.school import School
from app.models.students import Student


async def _login_as_position(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, position_code: str,
) -> tuple[dict, str]:
    """Create a staff member holding `position_code`, give them a login, and
    return (their bearer-token auth headers, their staff_member id) — mirrors
    test_attendance.py/test_scoring_lock.py's helper."""
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
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, staff_id


@pytest.fixture
async def subject(db_session: AsyncSession, school: School, school_class: Class) -> Subject:
    cat = SubjectCatalogue(name="English", code="ENG_SCOPE", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code="ENG_SCOPE", name="English", is_active=True)
    db_session.add(subj)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subj.id, is_active=True))
    await db_session.flush()
    return subj


@pytest.fixture
async def assessment_type(db_session: AsyncSession, school: School) -> AssessmentType:
    t = AssessmentType(school_id=school.id, name="Class Test", code="CT_SCOPE", weight=Decimal("30.00"))
    db_session.add(t)
    await db_session.flush()
    return t


@pytest.fixture
async def assessment(
    db_session: AsyncSession, school: School, school_class: Class,
    subject: Subject, assessment_type: AssessmentType, academic_term: AcademicTerm,
) -> Assessment:
    a = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        assessment_type_id=assessment_type.id, academic_term_id=academic_term.id,
        name="Scoped Test", max_score=Decimal("100.00"),
    )
    db_session.add(a)
    await db_session.flush()
    return a


async def _make_subject_teacher(
    db_session: AsyncSession, school: School, staff_id: str,
    school_class: Class, subject: Subject, academic_term: AcademicTerm,
) -> None:
    db_session.add(SubjectTeacher(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        staff_member_id=staff_id, academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()


# ── submit_scores ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_scores_404_for_non_assigned_subject_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    assessment: Assessment, student: Student, redis_permissions: None,
):
    teacher_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    resp = await client.post(f"/assessments/{assessment.id}/scores", json={
        "scores": [{"student_id": str(student.id), "raw_score": "80.00"}],
    }, headers=teacher_auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_submit_scores_allowed_for_assigned_subject_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, assessment: Assessment, student: Student,
    academic_term: AcademicTerm, redis_permissions: None,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)

    resp = await client.post(f"/assessments/{assessment.id}/scores", json={
        "scores": [{"student_id": str(student.id), "raw_score": "80.00"}],
    }, headers=teacher_auth)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_submit_scores_unrestricted_for_approver(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    assessment: Assessment, student: Student, redis_permissions: None,
):
    """EXAM_OFFICER holds assessments.approve_scores — never scoped, even
    with zero SubjectTeacher assignments of their own."""
    exam_officer_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "EXAM_OFFICER")
    resp = await client.post(f"/assessments/{assessment.id}/scores", json={
        "scores": [{"student_id": str(student.id), "raw_score": "80.00"}],
    }, headers=exam_officer_auth)
    assert resp.status_code == 201


# ── list_assessments / get_assessment ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_assessments_excludes_class_with_zero_taught_pairs(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, assessment: Assessment, academic_term: AcademicTerm, redis_permissions: None,
):
    teacher_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    resp = await client.get(
        f"/assessments?class_id={school_class.id}&term_id={academic_term.id}", headers=teacher_auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_assessments_filters_to_taught_subject_only(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, assessment: Assessment,
    assessment_type: AssessmentType, academic_term: AcademicTerm, redis_permissions: None,
):
    """A second subject's assessment in the same class must not appear —
    only the taught (class, subject) pair is included, not the whole class."""
    cat2 = SubjectCatalogue(name="Maths", code="MATH_SCOPE", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat2)
    await db_session.flush()
    other_subject = Subject(school_id=school.id, catalogue_id=cat2.id, code="MATH_SCOPE", name="Maths", is_active=True)
    db_session.add(other_subject)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=other_subject.id, is_active=True))
    await db_session.flush()
    other_assessment = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=other_subject.id,
        assessment_type_id=assessment_type.id, academic_term_id=academic_term.id,
        name="Other Subject Test", max_score=Decimal("100.00"),
    )
    db_session.add(other_assessment)
    await db_session.flush()

    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)

    resp = await client.get(
        f"/assessments?class_id={school_class.id}&term_id={academic_term.id}", headers=teacher_auth,
    )
    assert resp.status_code == 200
    ids = {a["id"] for a in resp.json()}
    assert ids == {str(assessment.id)}


@pytest.mark.asyncio
async def test_get_assessment_404_for_non_assigned_subject_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    assessment: Assessment, redis_permissions: None,
):
    teacher_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    resp = await client.get(f"/assessments/{assessment.id}", headers=teacher_auth)
    assert resp.status_code == 404


# ── my-subjects ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_my_subjects_scoped_to_own_subject_teacher_assignment(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")

    empty = await client.get(f"/assessments/my-subjects?term_id={academic_term.id}", headers=teacher_auth)
    assert empty.status_code == 200
    assert empty.json() == []

    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)

    resp = await client.get(f"/assessments/my-subjects?term_id={academic_term.id}", headers=teacher_auth)
    assert resp.status_code == 200
    pairs = {(p["class_id"], p["subject_id"]) for p in resp.json()}
    assert pairs == {(str(school_class.id), str(subject.id))}


@pytest.mark.asyncio
async def test_my_subjects_unrestricted_for_admin_returns_full_catalogue(
    client: AsyncClient, auth: dict, school_class: Class, subject: Subject, academic_term: AcademicTerm,
):
    """The school_admin fixture is a superadmin — always unrestricted, sees
    every active ClassSubject pairing in the school."""
    resp = await client.get(f"/assessments/my-subjects?term_id={academic_term.id}", headers=auth)
    assert resp.status_code == 200
    pairs = {(p["class_id"], p["subject_id"]) for p in resp.json()}
    assert (str(school_class.id), str(subject.id)) in pairs


# ── Current-term lock for score entry ─────────────────────────────────────────
# A subject teacher may only enter scores for the term admins have set as
# current — going back to a previous semester doesn't make sense for them.

@pytest.mark.asyncio
async def test_submit_scores_422_for_non_current_term(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, assessment_type: AssessmentType,
    academic_term: AcademicTerm, student: Student, redis_permissions: None,
):
    non_current_term = AcademicTerm(
        school_id=school.id, academic_year_id=academic_term.academic_year_id,
        term_number=2, name="Term 2",
        start_date=date(2025, 1, 1), end_date=date(2025, 4, 1), is_current=False,
    )
    db_session.add(non_current_term)
    await db_session.flush()
    past_assessment = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        assessment_type_id=assessment_type.id, academic_term_id=non_current_term.id,
        name="Past Term Test", max_score=Decimal("100.00"),
    )
    db_session.add(past_assessment)
    await db_session.flush()

    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    # SubjectTeacher is year-scoped (not term-scoped) so this assignment
    # covers both terms of the year — the rejection must come purely from
    # the term not being current, not from the (class, subject) scope check.
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)

    resp = await client.post(f"/assessments/{past_assessment.id}/scores", json={
        "scores": [{"student_id": str(student.id), "raw_score": "80.00"}],
    }, headers=teacher_auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_scores_unrestricted_for_approve_scores_holder(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, assessment_type: AssessmentType,
    academic_term: AcademicTerm, student: Student, redis_permissions: None,
):
    """EXAM_OFFICER holds assessments.approve_scores — can enter scores for
    any term, current or not."""
    non_current_term = AcademicTerm(
        school_id=school.id, academic_year_id=academic_term.academic_year_id,
        term_number=2, name="Term 2",
        start_date=date(2025, 1, 1), end_date=date(2025, 4, 1), is_current=False,
    )
    db_session.add(non_current_term)
    await db_session.flush()
    past_assessment = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        assessment_type_id=assessment_type.id, academic_term_id=non_current_term.id,
        name="Past Term Test 2", max_score=Decimal("100.00"),
    )
    db_session.add(past_assessment)
    await db_session.flush()

    exam_officer_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "EXAM_OFFICER")
    resp = await client.post(f"/assessments/{past_assessment.id}/scores", json={
        "scores": [{"student_id": str(student.id), "raw_score": "80.00"}],
    }, headers=exam_officer_auth)
    assert resp.status_code == 201
