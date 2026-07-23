"""
Assessments integration tests — grading scales, types, assessments, scores.
Run inside Docker: docker compose exec api pytest app/tests/test_assessments.py -v
"""
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class
from app.models.assessments import Assessment, AssessmentType, GradingScale
from app.models.students import Student


# ── Grading scales ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_grading_scale(client: AsyncClient, auth: dict):
    resp = await client.post("/assessments/grading-scales", json={
        "name": "GES Standard", "is_default": True,
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "GES Standard"
    assert data["is_default"] is True
    assert data["grades"] == []


@pytest.mark.asyncio
async def test_add_grade_band(client: AsyncClient, auth: dict):
    scale_resp = await client.post("/assessments/grading-scales", json={
        "name": "Scale A",
    }, headers=auth)
    scale_id = scale_resp.json()["id"]

    resp = await client.post(f"/assessments/grading-scales/{scale_id}/grades", json={
        "min_score": "80.00", "max_score": "100.00",
        "letter_grade": "A1", "label": "Excellent",
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["letter_grade"] == "A1"


@pytest.mark.asyncio
async def test_list_grading_scales(client: AsyncClient, auth: dict):
    await client.post("/assessments/grading-scales", json={"name": "Scale B"}, headers=auth)
    resp = await client.get("/assessments/grading-scales", headers=auth)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_grade_band_min_max_validation(client: AsyncClient, auth: dict):
    scale_resp = await client.post("/assessments/grading-scales", json={
        "name": "Bad Scale",
    }, headers=auth)
    scale_id = scale_resp.json()["id"]
    resp = await client.post(f"/assessments/grading-scales/{scale_id}/grades", json={
        "min_score": "90.00", "max_score": "70.00",
        "letter_grade": "X", "label": "Invalid",
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_grade_band(client: AsyncClient, auth: dict):
    scale_resp = await client.post("/assessments/grading-scales", json={"name": "Scale C"}, headers=auth)
    scale_id = scale_resp.json()["id"]
    grade_resp = await client.post(f"/assessments/grading-scales/{scale_id}/grades", json={
        "min_score": "0", "max_score": "49.99", "letter_grade": "F9", "label": "Fail",
    }, headers=auth)
    grade_id = grade_resp.json()["id"]
    resp = await client.delete(f"/assessments/grading-scales/{scale_id}/grades/{grade_id}", headers=auth)
    assert resp.status_code == 204


# ── Assessment types ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_assessment_type(client: AsyncClient, auth: dict):
    resp = await client.post("/assessments/types", json={
        "name": "Class Test", "code": "CT", "weight": "30.00",
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["code"] == "CT"


@pytest.mark.asyncio
async def test_duplicate_assessment_type_rejected(client: AsyncClient, auth: dict):
    await client.post("/assessments/types", json={
        "name": "End of Term", "code": "EOT", "weight": "70.00",
    }, headers=auth)
    resp = await client.post("/assessments/types", json={
        "name": "End of Term 2", "code": "EOT", "weight": "70.00",
    }, headers=auth)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_assessment_types(client: AsyncClient, auth: dict):
    await client.post("/assessments/types", json={
        "name": "Quiz", "code": "QZ", "weight": "10.00",
    }, headers=auth)
    resp = await client.get("/assessments/types", headers=auth)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# ── Assessments ───────────────────────────────────────────────────────────────

@pytest.fixture
async def assessment_type(db_session: AsyncSession, school) -> AssessmentType:
    t = AssessmentType(
        school_id=school.id, name="Class Test", code="CT_FIXTURE", weight=Decimal("30.00")
    )
    db_session.add(t)
    await db_session.flush()
    return t


@pytest.fixture
async def subject(db_session: AsyncSession, school, school_class: Class):
    from app.models.academic import ClassSubject, SubjectCatalogue, SubjectType, Subject, SchoolLevel
    cat = SubjectCatalogue(
        name="Mathematics", code="MATH", subject_type=SubjectType.CORE,
        level=SchoolLevel.SHS,
    )
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code="MATH", name="Mathematics", is_active=True)
    db_session.add(subj)
    await db_session.flush()
    # Assessments require subject_id to be an active ClassSubject on class_id
    # (services/subject_roster.py::class_subject_exists) — wire it up here so
    # every test using `subject` + `school_class` together gets a valid pair.
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subj.id, is_active=True))
    await db_session.flush()
    return subj


@pytest.fixture
async def assessment(
    db_session: AsyncSession, school, school_class: Class,
    subject, assessment_type: AssessmentType, academic_term: AcademicTerm,
) -> Assessment:
    a = Assessment(
        school_id=school.id,
        class_id=school_class.id,
        subject_id=subject.id,
        assessment_type_id=assessment_type.id,
        academic_term_id=academic_term.id,
        name="Mid-Term Test",
        max_score=Decimal("100.00"),
    )
    db_session.add(a)
    await db_session.flush()
    return a


@pytest.mark.asyncio
async def test_create_assessment(
    client: AsyncClient, auth: dict,
    school_class: Class, subject, assessment_type: AssessmentType, academic_term: AcademicTerm,
):
    resp = await client.post("/assessments", json={
        "class_id": str(school_class.id),
        "subject_id": str(subject.id),
        "assessment_type_id": str(assessment_type.id),
        "academic_term_id": str(academic_term.id),
        "name": "Term 1 Test",
        "max_score": "100.00",
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["name"] == "Term 1 Test"
    assert resp.json()["is_published"] is False


@pytest.mark.asyncio
async def test_duplicate_assessment_name_rejected(
    client: AsyncClient, auth: dict,
    school_class: Class, subject, assessment_type: AssessmentType, academic_term: AcademicTerm,
):
    """Same class + subject + term + name must not silently create a second
    assessment — reported live: creating two 'Assignment 1' for the same
    subject was accepted with no warning."""
    payload = {
        "class_id": str(school_class.id),
        "subject_id": str(subject.id),
        "assessment_type_id": str(assessment_type.id),
        "academic_term_id": str(academic_term.id),
        "name": "Assignment 1",
        "max_score": "20.00",
    }
    first = await client.post("/assessments", json=payload, headers=auth)
    assert first.status_code == 201

    second = await client.post("/assessments", json=payload, headers=auth)
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"]


@pytest.mark.asyncio
async def test_list_assessments(
    client: AsyncClient, auth: dict,
    assessment: Assessment, school_class: Class, academic_term: AcademicTerm,
):
    resp = await client.get(
        f"/assessments?class_id={school_class.id}&term_id={academic_term.id}",
        headers=auth,
    )
    assert resp.status_code == 200
    assert any(a["id"] == str(assessment.id) for a in resp.json())


@pytest.mark.asyncio
async def test_publish_assessment(
    client: AsyncClient, auth: dict, assessment: Assessment,
):
    resp = await client.post(f"/assessments/{assessment.id}/publish", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["is_published"] is True


# ── Scores ────────────────────────────────────────────────────────────────────

@pytest.fixture
async def grading_scale(db_session: AsyncSession, school) -> GradingScale:
    from app.models.assessments import Grade
    scale = GradingScale(school_id=school.id, name="GES Scale", is_default=True)
    db_session.add(scale)
    await db_session.flush()
    bands = [
        Grade(grading_scale_id=scale.id, min_score=Decimal("80"), max_score=Decimal("100"), letter_grade="A1", label="Excellent"),
        Grade(grading_scale_id=scale.id, min_score=Decimal("70"), max_score=Decimal("79.99"), letter_grade="B2", label="Very Good"),
        Grade(grading_scale_id=scale.id, min_score=Decimal("60"), max_score=Decimal("69.99"), letter_grade="B3", label="Good"),
        Grade(grading_scale_id=scale.id, min_score=Decimal("0"), max_score=Decimal("59.99"), letter_grade="F9", label="Fail"),
    ]
    db_session.add_all(bands)
    await db_session.flush()
    return scale


@pytest.mark.asyncio
async def test_submit_scores(
    client: AsyncClient, auth: dict, assessment: Assessment, student: Student,
):
    resp = await client.post(f"/assessments/{assessment.id}/scores", json={
        "scores": [{"student_id": str(student.id), "raw_score": "85.00"}],
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 1
    assert data[0]["raw_score"] == "85.00"
    assert data[0]["is_approved"] is False
    assert data[0]["cached_grade_label"] is None


@pytest.mark.asyncio
async def test_score_out_of_range_rejected(
    client: AsyncClient, auth: dict, assessment: Assessment, student: Student,
):
    resp = await client.post(f"/assessments/{assessment.id}/scores", json={
        "scores": [{"student_id": str(student.id), "raw_score": "150.00"}],
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_resubmit_score_updates_and_unapproves(
    client: AsyncClient, auth: dict, assessment: Assessment, student: Student,
):
    await client.post(f"/assessments/{assessment.id}/scores", json={
        "scores": [{"student_id": str(student.id), "raw_score": "70.00"}],
    }, headers=auth)
    resp = await client.post(f"/assessments/{assessment.id}/scores", json={
        "scores": [{"student_id": str(student.id), "raw_score": "75.00"}],
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()[0]["raw_score"] == "75.00"
    assert resp.json()[0]["is_approved"] is False


@pytest.mark.asyncio
async def test_approve_scores_sets_grade_label(
    client: AsyncClient, auth: dict,
    assessment: Assessment, student: Student, grading_scale: GradingScale,
):
    submit = await client.post(f"/assessments/{assessment.id}/scores", json={
        "scores": [{"student_id": str(student.id), "raw_score": "85.00"}],
    }, headers=auth)
    score_id = submit.json()[0]["id"]

    resp = await client.post(f"/assessments/{assessment.id}/scores/approve", json={
        "score_ids": [score_id],
    }, headers=auth)
    assert resp.status_code == 200
    data = resp.json()[0]
    assert data["is_approved"] is True
    assert data["cached_grade_label"] == "A1"


@pytest.fixture
async def quiz_assessment(
    db_session: AsyncSession, school, school_class: Class,
    subject, assessment_type: AssessmentType, academic_term: AcademicTerm,
) -> Assessment:
    """A 20-mark assessment, not out of 100 — regression fixture for the
    grade-normalization bug (raw_score must be normalized to a percentage
    before resolve_grade, since GradingScale bands are 0-100)."""
    a = Assessment(
        school_id=school.id,
        class_id=school_class.id,
        subject_id=subject.id,
        assessment_type_id=assessment_type.id,
        academic_term_id=academic_term.id,
        name="20-Mark Quiz",
        max_score=Decimal("20.00"),
    )
    db_session.add(a)
    await db_session.flush()
    return a


@pytest.mark.asyncio
async def test_approve_scores_normalizes_non_100_max_score(
    client: AsyncClient, auth: dict,
    quiz_assessment: Assessment, student: Student, grading_scale: GradingScale,
):
    """18/20 is 90% and must resolve to A1 (80-100) — not be compared against
    the GradingScale bands as a raw 18, which would wrongly land in F9."""
    submit = await client.post(f"/assessments/{quiz_assessment.id}/scores", json={
        "scores": [{"student_id": str(student.id), "raw_score": "18.00"}],
    }, headers=auth)
    score_id = submit.json()[0]["id"]

    resp = await client.post(f"/assessments/{quiz_assessment.id}/scores/approve", json={
        "score_ids": [score_id],
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.json()[0]["cached_grade_label"] == "A1"


@pytest.mark.asyncio
async def test_list_scores(
    client: AsyncClient, auth: dict, assessment: Assessment, student: Student,
):
    await client.post(f"/assessments/{assessment.id}/scores", json={
        "scores": [{"student_id": str(student.id), "raw_score": "60.00"}],
    }, headers=auth)
    resp = await client.get(f"/assessments/{assessment.id}/scores", headers=auth)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
