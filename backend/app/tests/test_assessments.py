"""
Assessments integration tests — grading scales, types, assessments, scores.
Run inside Docker: docker compose exec api pytest app/tests/test_assessments.py -v
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
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
async def test_list_grading_scales_includes_shared_default(client: AsyncClient, auth: dict):
    """A school with no grading scale of its own must still see the shared
    system default (school_id=NULL, seeded by scripts/seed_reference_data.py)
    — otherwise the Grading Scales page looks empty even though scoring
    already falls back to it."""
    resp = await client.get("/assessments/grading-scales", headers=auth)
    assert resp.status_code == 200
    shared = next((s for s in resp.json() if s["school_id"] is None), None)
    assert shared is not None, "Run scripts/seed_reference_data.py first"
    assert shared["name"] == "GES Standard Grading Scale"
    assert len(shared["grades"]) == 9


@pytest.mark.asyncio
async def test_resolve_grade_falls_back_to_shared_default(db_session: AsyncSession, school):
    """A school with no grading scale of its own still gets a letter grade,
    from the seeded shared scale."""
    from app.services.grading import resolve_grade
    result = await resolve_grade(Decimal("85"), school.id, db_session)
    assert result == "A1"
    result_low = await resolve_grade(Decimal("30"), school.id, db_session)
    assert result_low == "F9"


@pytest.mark.asyncio
async def test_resolve_grade_prefers_school_own_scale_over_shared(
    db_session: AsyncSession, school, grading_scale: GradingScale,
):
    """Once a school creates its own default scale, it wins over the shared
    system default — the fallback only fires when the school has none."""
    from app.services.grading import resolve_grade
    # The `grading_scale` fixture's own top band is A1 = 80-100, same letter
    # as the shared scale's — use a percentage only the school's *own* bands
    # (60-69.99 = "B3") would label differently from the shared scale's
    # equivalent range (70-74.99 = "B3", 65-69.99 = "C4") to prove which
    # scale actually resolved.
    result = await resolve_grade(Decimal("65"), school.id, db_session)
    assert result == "B3"  # grading_scale fixture's band, not the shared scale's "C4"


@pytest.mark.asyncio
async def test_get_default_scale_with_bands_prefers_school_own_scale(
    db_session: AsyncSession, school, grading_scale: GradingScale,
):
    """Same fallback resolve_grade() uses, exposed directly for the report
    card / transcript grade-legend section — a school's own default scale
    wins once it exists."""
    from app.services.grading import get_default_scale_with_bands

    scale = await get_default_scale_with_bands(school.id, db_session)
    assert scale is not None
    assert scale.id == grading_scale.id
    assert [g.letter_grade for g in scale.grades] == ["A1", "B2", "B3", "F9"]  # highest score first


@pytest.mark.asyncio
async def test_get_default_scale_with_bands_falls_back_to_shared(db_session: AsyncSession, school):
    """A school with no scale of its own gets the shared system default."""
    from app.services.grading import get_default_scale_with_bands

    scale = await get_default_scale_with_bands(school.id, db_session)
    assert scale is not None
    assert scale.school_id is None
    assert scale.name == "GES Standard Grading Scale"


def test_grade_legend_rows_empty_for_no_scale():
    from app.services.grading import grade_legend_rows
    assert grade_legend_rows(None) == []


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
        description="Mid-Term Test",
        recorded_date=date.today(),
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
        "description": "Term 1 Test",
        "max_score": "100.00",
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["description"] == "Term 1 Test"
    assert resp.json()["recorded_date"] == date.today().isoformat()
    assert resp.json()["is_published"] is False


@pytest.mark.asyncio
async def test_duplicate_category_same_day_rejected(
    client: AsyncClient, auth: dict,
    school_class: Class, subject, assessment_type: AssessmentType, academic_term: AcademicTerm,
):
    """Same class + subject + term + category + recorded_date (always today
    at creation) must not silently create a second assessment — an
    assessment's identity is the category and the day it was recorded, not a
    teacher-typed name."""
    payload = {
        "class_id": str(school_class.id),
        "subject_id": str(subject.id),
        "assessment_type_id": str(assessment_type.id),
        "academic_term_id": str(academic_term.id),
        "max_score": "20.00",
    }
    first = await client.post("/assessments", json=payload, headers=auth)
    assert first.status_code == 201

    second = await client.post("/assessments", json=payload, headers=auth)
    assert second.status_code == 409
    assert "already been recorded today" in second.json()["detail"]


@pytest.mark.asyncio
async def test_same_category_different_day_allowed(
    db_session: AsyncSession, client: AsyncClient, auth: dict,
    school_class: Class, subject, assessment_type: AssessmentType, academic_term: AcademicTerm,
):
    """The UNIQUE constraint is scoped to (class, subject, term, category,
    recorded_date) — a second instance of the same category on a different
    day is a legitimate, distinct assessment, not a conflict."""
    yesterday = Assessment(
        school_id=school_class.school_id,
        class_id=school_class.id,
        subject_id=subject.id,
        assessment_type_id=assessment_type.id,
        academic_term_id=academic_term.id,
        recorded_date=date.today() - timedelta(days=1),
        max_score=Decimal("20.00"),
    )
    db_session.add(yesterday)
    await db_session.flush()

    resp = await client.post("/assessments", json={
        "class_id": str(school_class.id),
        "subject_id": str(subject.id),
        "assessment_type_id": str(assessment_type.id),
        "academic_term_id": str(academic_term.id),
        "max_score": "20.00",
    }, headers=auth)
    assert resp.status_code == 201


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


@pytest.mark.asyncio
async def test_publishing_second_assessment_does_not_resend_report_ready_email(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school, school_class: Class, subject, assessment_type: AssessmentType,
    academic_term: AcademicTerm, assessment: Assessment, student: Student,
):
    """services/portal.py::is_report_published() unlocks the whole report the
    moment ANY assessment for the class+term is published, and stays unlocked
    regardless of how many more are published after. Before this fix,
    publish_assessment() re-sent the identical "report is ready" email (and
    SMS) to every guardian on every subsequent publish — a class with dozens
    of assessments across a term would spam guardians (and rack up real SMS
    cost) with nothing new to report. Publishing a second assessment for the
    same class+term must not add a second EmailLog row."""
    import unittest.mock as mock
    import httpx
    from app.models.school import EmailConfig, EmailLog, EmailProvider
    from app.models.students import Guardian, StudentClassAssignment, StudentGuardian

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
    second = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        assessment_type_id=assessment_type.id, academic_term_id=academic_term.id,
        description="End-of-Term Exam", recorded_date=date.today() - timedelta(days=1),
        max_score=Decimal("100.00"),
    )
    db_session.add(second)
    await db_session.flush()

    class _MockTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(202, json={})

    original_init = httpx.AsyncClient.__init__
    with mock.patch("httpx.AsyncClient.__init__", lambda self, **kw: original_init(
        self, transport=_MockTransport(), **{k: v for k, v in kw.items() if k != "transport"}
    )):
        resp1 = await client.post(f"/assessments/{assessment.id}/publish", headers=auth)
        resp2 = await client.post(f"/assessments/{second.id}/publish", headers=auth)

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    logs = (await db_session.scalars(
        select(EmailLog).where(
            EmailLog.school_id == school.id, EmailLog.entity_type == "REPORT_CARD",
        )
    )).all()
    assert len(logs) == 1, "Second publish for the same class+term must not resend the email"
    assert logs[0].recipient == "ama.owusu@example.com"


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
        description="20-Mark Quiz",
        recorded_date=date.today(),
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
async def test_switching_default_scale_clears_cached_grades(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school,
    assessment: Assessment, student: Student, grading_scale: GradingScale,
):
    """A previously-approved score's cached_grade_label was resolved from
    whichever scale was `is_default` at approval time — add_grade/delete_grade
    already invalidate it when a scale's own bands change, but switching
    WHICH scale is default is just as grade-affecting and was silently not
    invalidating anything, so a report card generated after the switch would
    still show the letter grade resolved from the OLD default scale."""
    from app.models.assessments import Grade

    submit = await client.post(f"/assessments/{assessment.id}/scores", json={
        "scores": [{"student_id": str(student.id), "raw_score": "85.00"}],
    }, headers=auth)
    score_id = submit.json()[0]["id"]
    approve = await client.post(f"/assessments/{assessment.id}/scores/approve", json={
        "score_ids": [score_id],
    }, headers=auth)
    assert approve.json()[0]["cached_grade_label"] == "A1"

    # A second scale, deliberately with no band covering 85% at all.
    honors = GradingScale(school_id=school.id, name="Honors Scale", is_default=False)
    db_session.add(honors)
    await db_session.flush()
    db_session.add(Grade(
        grading_scale_id=honors.id, min_score=Decimal("95"), max_score=Decimal("100"),
        letter_grade="H", label="Honors",
    ))
    await db_session.flush()

    resp = await client.patch(f"/assessments/grading-scales/{honors.id}", json={
        "is_default": True,
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["is_default"] is True

    from app.models.assessments import Score
    score = await db_session.get(Score, score_id)
    await db_session.refresh(score)
    assert score.cached_grade_label is None, (
        "Switching the default scale must clear stale cached grade labels, "
        "not leave report cards silently showing grades from the old scale"
    )


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
