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
from app.models.assessments import (
    AggregationStrategy, Assessment, AssessmentType, GradingScale,
)
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


@pytest.mark.asyncio
async def test_deactivate_and_reactivate_grading_scale(client: AsyncClient, auth: dict):
    """Deactivating must not make the scale vanish from GET /grading-scales —
    the same 'one-way trip' bug already fixed for Subject/AssessmentType."""
    create = await client.post("/assessments/grading-scales", json={"name": "Retiring Scale"}, headers=auth)
    scale_id = create.json()["id"]

    off = await client.patch(f"/assessments/grading-scales/{scale_id}", json={"is_active": False}, headers=auth)
    assert off.status_code == 200
    assert off.json()["is_active"] is False

    listed = await client.get("/assessments/grading-scales", headers=auth)
    scale = next(s for s in listed.json() if s["id"] == scale_id)
    assert scale["is_active"] is False

    on = await client.patch(f"/assessments/grading-scales/{scale_id}", json={"is_active": True}, headers=auth)
    assert on.status_code == 200
    assert on.json()["is_active"] is True


@pytest.mark.asyncio
async def test_deactivating_the_effective_default_scale_clears_cached_grades(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school,
    assessment: Assessment, student: Student, grading_scale: GradingScale,
):
    """Deactivating a school's own default scale silently falls back to the
    shared platform default (get_default_scale_with_bands' own priority) —
    exactly as grade-affecting as explicitly switching default, since every
    previously-approved score was graded against the scale that's now gone."""
    submit = await client.post(f"/assessments/{assessment.id}/scores", json={
        "scores": [{"student_id": str(student.id), "raw_score": "85.00"}],
    }, headers=auth)
    score_id = submit.json()[0]["id"]
    approve = await client.post(f"/assessments/{assessment.id}/scores/approve", json={
        "score_ids": [score_id],
    }, headers=auth)
    assert approve.json()[0]["cached_grade_label"] == "A1"

    resp = await client.patch(f"/assessments/grading-scales/{grading_scale.id}", json={
        "is_active": False,
    }, headers=auth)
    assert resp.status_code == 200

    from app.models.assessments import Score
    score = await db_session.get(Score, score_id)
    await db_session.refresh(score)
    assert score.cached_grade_label is None


@pytest.mark.asyncio
async def test_delete_unused_grading_scale(client: AsyncClient, auth: dict):
    create = await client.post("/assessments/grading-scales", json={"name": "Throwaway Scale"}, headers=auth)
    scale_id = create.json()["id"]

    resp = await client.delete(f"/assessments/grading-scales/{scale_id}", headers=auth)
    assert resp.status_code == 204

    listed = await client.get("/assessments/grading-scales", headers=auth)
    assert all(s["id"] != scale_id for s in listed.json())


@pytest.mark.asyncio
async def test_delete_default_grading_scale_rejected(
    client: AsyncClient, auth: dict, grading_scale: GradingScale,
):
    resp = await client.delete(f"/assessments/grading-scales/{grading_scale.id}", headers=auth)
    assert resp.status_code == 409

    listed = await client.get("/assessments/grading-scales", headers=auth)
    assert any(s["id"] == str(grading_scale.id) for s in listed.json())


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


# ── Assessment type — aggregation engine fields ─────────────────────────────────

@pytest.mark.asyncio
async def test_create_assessment_type_defaults_are_behavior_preserving(client: AsyncClient, auth: dict):
    """Not specifying the 3 new fields must resolve to the exact same
    defaults the migration backfilled every pre-existing row to — the whole
    point of the migration's chosen default (see alembic/versions/
    f8a9b0c1d2e3_*.py's own docstring)."""
    resp = await client.post("/assessments/types", json={
        "name": "Legacy Style", "code": "LEGACY", "weight": "30.00",
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["category"] == "FORMATIVE"
    assert data["allow_multiple_entries"] is True
    assert data["aggregation_strategy"] == "SUM_NORMALIZE"


@pytest.mark.asyncio
async def test_create_assessment_type_with_new_fields(client: AsyncClient, auth: dict):
    resp = await client.post("/assessments/types", json={
        "name": "Placement Test", "code": "PLACE", "weight": "1.00",
        "category": "DIAGNOSTIC",
        "allow_multiple_entries": True, "aggregation_strategy": "AVERAGE",
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["category"] == "DIAGNOSTIC"
    assert resp.json()["aggregation_strategy"] == "AVERAGE"


@pytest.mark.asyncio
async def test_create_assessment_type_rejects_none_strategy_with_multiple_entries_allowed(
    client: AsyncClient, auth: dict,
):
    resp = await client.post("/assessments/types", json={
        "name": "Bad Combo", "code": "BADCOMBO1", "weight": "10.00",
        "allow_multiple_entries": True, "aggregation_strategy": "NONE",
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_assessment_type_rejects_non_none_strategy_when_multiple_disallowed(
    client: AsyncClient, auth: dict,
):
    resp = await client.post("/assessments/types", json={
        "name": "Bad Combo 2", "code": "BADCOMBO2", "weight": "10.00",
        "allow_multiple_entries": False, "aggregation_strategy": "AVERAGE",
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_assessment_type_partial_update_checked_against_resulting_row(
    client: AsyncClient, auth: dict,
):
    """A single-field PATCH (only aggregation_strategy) can't be checked by
    the schema alone — the service layer must check it against the row's
    *other*, unchanged field."""
    create = await client.post("/assessments/types", json={
        "name": "Single Exam", "code": "SINGLEEX", "weight": "70.00",
        "allow_multiple_entries": False, "aggregation_strategy": "NONE",
    }, headers=auth)
    type_id = create.json()["id"]

    # allow_multiple_entries is still False on the row — AVERAGE is invalid.
    resp = await client.patch(f"/assessments/types/{type_id}", json={
        "aggregation_strategy": "AVERAGE",
    }, headers=auth)
    assert resp.status_code == 422

    # Flip allow_multiple_entries first — now AVERAGE is valid.
    ok = await client.patch(f"/assessments/types/{type_id}", json={
        "allow_multiple_entries": True, "aggregation_strategy": "AVERAGE",
    }, headers=auth)
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_update_assessment_type_rejects_narrowing_when_multi_entry_data_exists(
    db_session: AsyncSession, client: AsyncClient, auth: dict,
    school_class: Class, subject, academic_term: AcademicTerm,
):
    """create_assessment() only guards against a *new* second entry once a
    type is allow_multiple_entries=False — nothing previously stopped
    narrowing an existing multi-entry type down to single-entry after real
    data already violated that (resolve_type_score() would then raise at
    report-card time). Reproduces the exact real-world scenario: a type
    created with multiple entries allowed, two assessments already recorded
    for the same class+subject+term, then narrowed via PATCH."""
    create = await client.post("/assessments/types", json={
        "name": "Individual Redux", "code": "INDREDUX", "weight": "20.00",
        "allow_multiple_entries": True, "aggregation_strategy": "AVERAGE",
    }, headers=auth)
    type_id = create.json()["id"]

    for i in range(2):
        db_session.add(Assessment(
            school_id=school_class.school_id, class_id=school_class.id, subject_id=subject.id,
            assessment_type_id=type_id, academic_term_id=academic_term.id,
            recorded_date=date.today() - timedelta(days=i), max_score=Decimal("20.00"),
        ))
    await db_session.commit()

    resp = await client.patch(f"/assessments/types/{type_id}", json={
        "allow_multiple_entries": False, "aggregation_strategy": "NONE",
    }, headers=auth)
    assert resp.status_code == 409
    assert "more than one assessment" in resp.json()["detail"]

    # Confirm the row was left untouched by the rejected update.
    still_multi = await client.get("/assessments/types", headers=auth)
    t = next(t for t in still_multi.json() if t["id"] == type_id)
    assert t["allow_multiple_entries"] is True


@pytest.mark.asyncio
async def test_deactivate_and_reactivate_assessment_type(client: AsyncClient, auth: dict):
    """Deactivating must not make the type vanish from GET /types — the same
    'one-way trip' bug already fixed for Subject (list_subjects())."""
    create = await client.post("/assessments/types", json={
        "name": "Retiring Type", "code": "RETIRE", "weight": "5.00",
    }, headers=auth)
    type_id = create.json()["id"]

    off = await client.patch(f"/assessments/types/{type_id}", json={"is_active": False}, headers=auth)
    assert off.status_code == 200
    assert off.json()["is_active"] is False

    listed = await client.get("/assessments/types", headers=auth)
    t = next(t for t in listed.json() if t["id"] == type_id)
    assert t["is_active"] is False

    on = await client.patch(f"/assessments/types/{type_id}", json={"is_active": True}, headers=auth)
    assert on.status_code == 200
    assert on.json()["is_active"] is True


@pytest.mark.asyncio
async def test_delete_unused_assessment_type(client: AsyncClient, auth: dict):
    create = await client.post("/assessments/types", json={
        "name": "Throwaway Type", "code": "THROWAWAY", "weight": "5.00",
    }, headers=auth)
    type_id = create.json()["id"]

    resp = await client.delete(f"/assessments/types/{type_id}", headers=auth)
    assert resp.status_code == 204

    listed = await client.get("/assessments/types", headers=auth)
    assert all(t["id"] != type_id for t in listed.json())


@pytest.mark.asyncio
async def test_delete_in_use_assessment_type_rejected(
    db_session: AsyncSession, client: AsyncClient, auth: dict,
    school_class: Class, subject, academic_term: AcademicTerm,
):
    """A hard DELETE against a type with real assessments must not raise a
    raw Postgres IntegrityError (Assessment.assessment_type_id has no
    ondelete clause) — it should 409 cleanly, naming the count, and leave
    the type untouched."""
    create = await client.post("/assessments/types", json={
        "name": "In Use Type", "code": "INUSE", "weight": "5.00",
    }, headers=auth)
    type_id = create.json()["id"]

    db_session.add(Assessment(
        school_id=school_class.school_id, class_id=school_class.id, subject_id=subject.id,
        assessment_type_id=type_id, academic_term_id=academic_term.id,
        recorded_date=date.today(), max_score=Decimal("20.00"),
    ))
    await db_session.commit()

    resp = await client.delete(f"/assessments/types/{type_id}", headers=auth)
    assert resp.status_code == 409
    assert "1 assessment" in resp.json()["detail"]

    listed = await client.get("/assessments/types", headers=auth)
    assert any(t["id"] == type_id for t in listed.json())


@pytest.mark.asyncio
async def test_type_presets_endpoint_returns_waec_ges_shs(client: AsyncClient, auth: dict):
    resp = await client.get("/assessments/type-presets", headers=auth)
    assert resp.status_code == 200
    presets = resp.json()
    assert "waec_ges_shs" in presets
    entries = presets["waec_ges_shs"]
    assert len(entries) == 2
    codes = {e["code"] for e in entries}
    assert codes == {"CAT", "EXAM"}
    exam = next(e for e in entries if e["code"] == "EXAM")
    assert exam["allow_multiple_entries"] is False
    assert exam["aggregation_strategy"] == "NONE"


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
async def test_create_assessment_rejects_deactivated_type(
    db_session: AsyncSession, client: AsyncClient, auth: dict,
    school_class: Class, subject, assessment_type: AssessmentType, academic_term: AcademicTerm,
):
    """Deactivating a type only hides it from the frontend's creation picker
    client-side — the backend must independently reject it too, closing the
    gap a raw API call could otherwise use to bypass that filtering."""
    assessment_type.is_active = False
    await db_session.commit()

    resp = await client.post("/assessments", json={
        "class_id": str(school_class.id),
        "subject_id": str(subject.id),
        "assessment_type_id": str(assessment_type.id),
        "academic_term_id": str(academic_term.id),
        "max_score": "100.00",
    }, headers=auth)
    assert resp.status_code == 422
    assert "deactivated" in resp.json()["detail"]


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
async def test_create_assessment_allow_multiple_entries_false_rejects_second_assessment(
    db_session: AsyncSession, client: AsyncClient, auth: dict,
    school_class: Class, subject, academic_term: AcademicTerm,
):
    """A type with allow_multiple_entries=False must never accumulate a
    second Assessment row for the same class+subject+term — this is what
    keeps resolve_type_score()'s NONE-strategy invariant ("exactly one
    entry") true by construction, not just by convention."""
    single_type = AssessmentType(
        school_id=school_class.school_id, name="Final Exam", code="FINALEXAM",
        weight=Decimal("70.00"), allow_multiple_entries=False, aggregation_strategy=AggregationStrategy.NONE,
    )
    db_session.add(single_type)
    await db_session.flush()

    payload = {
        "class_id": str(school_class.id),
        "subject_id": str(subject.id),
        "assessment_type_id": str(single_type.id),
        "academic_term_id": str(academic_term.id),
        "max_score": "100.00",
    }
    first = await client.post("/assessments", json=payload, headers=auth)
    assert first.status_code == 201

    # A different recorded_date would normally be allowed (see
    # test_same_category_different_day_allowed) — allow_multiple_entries=False
    # must block it anyway, at the school+class+subject+term+type level.
    yesterday = Assessment(
        school_id=school_class.school_id, class_id=school_class.id, subject_id=subject.id,
        assessment_type_id=single_type.id, academic_term_id=academic_term.id,
        recorded_date=date.today() - timedelta(days=1), max_score=Decimal("100.00"),
    )
    db_session.add(yesterday)
    await db_session.flush()

    second = await client.post("/assessments", json={**payload, "max_score": "50.00"}, headers=auth)
    assert second.status_code == 409
    assert "allow_multiple_entries" in second.json()["detail"]


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
async def test_publish_rejects_assessment_with_unapproved_score(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    assessment: Assessment, student: Student, school_admin,
):
    """Single publish must reject loudly (422), not silently publish unreviewed
    marks — the same underlying risk bulk_publish_assessments() guards against
    by skipping, just surfaced as a hard error for a single deliberate click."""
    from app.models.assessments import Score

    db_session.add(Score(
        school_id=assessment.school_id, assessment_id=assessment.id, student_id=student.id,
        raw_score=Decimal("70.00"), is_approved=False, entered_by_id=school_admin.id,
    ))
    await db_session.flush()

    resp = await client.post(f"/assessments/{assessment.id}/publish", headers=auth)
    assert resp.status_code == 422
    assert "unapproved" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_publish_rejects_already_published_assessment(
    client: AsyncClient, auth: dict, assessment: Assessment,
):
    first = await client.post(f"/assessments/{assessment.id}/publish", headers=auth)
    assert first.status_code == 200

    second = await client.post(f"/assessments/{assessment.id}/publish", headers=auth)
    assert second.status_code == 422


# ── Unpublish ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unpublish_reverses_publish_and_logs_reason(
    client: AsyncClient, auth: dict, db_session: AsyncSession, assessment: Assessment,
):
    from app.models.assessments import AssessmentAuditLog

    publish = await client.post(f"/assessments/{assessment.id}/publish", headers=auth)
    assert publish.status_code == 200

    resp = await client.post(f"/assessments/{assessment.id}/unpublish", json={
        "reason": "Wrong scores entered — recalling to fix before parents see it.",
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["is_published"] is False

    log = await db_session.scalar(
        select(AssessmentAuditLog).where(AssessmentAuditLog.assessment_id == assessment.id)
    )
    assert log is not None
    assert log.reason == "Wrong scores entered — recalling to fix before parents see it."
    assert log.old_values == {"is_published": "True"}
    assert log.new_values == {"is_published": "False"}


@pytest.mark.asyncio
async def test_unpublish_requires_a_reason(
    client: AsyncClient, auth: dict, assessment: Assessment,
):
    await client.post(f"/assessments/{assessment.id}/publish", headers=auth)
    resp = await client.post(f"/assessments/{assessment.id}/unpublish", json={"reason": "   "}, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_unpublish_rejects_a_draft_assessment(
    client: AsyncClient, auth: dict, assessment: Assessment,
):
    resp = await client.post(f"/assessments/{assessment.id}/unpublish", json={
        "reason": "Testing",
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_unpublish_hides_report_when_it_was_the_only_publish(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school, school_class: Class, academic_term: AcademicTerm, student: Student, school_admin,
):
    """is_report_published() is a live query, not a cached flag — unpublishing
    the only published assessment for a class+term must re-hide the report
    from the parent portal with no extra bookkeeping."""
    from app.models.students import StudentClassAssignment
    from app.services.portal import is_report_published

    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=school_class.id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()

    from app.models.academic import ClassSubject, SchoolLevel, SubjectCatalogue, SubjectType
    from app.models.academic import Subject as SubjectModel

    cat = SubjectCatalogue(name="Unpublish Test Subject", code="UNPUB_SUBJ", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = SubjectModel(school_id=school.id, catalogue_id=cat.id, code="UNPUB_SUBJ", name="Unpublish Test Subject", is_active=True)
    db_session.add(subj)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subj.id, is_active=True))
    atype = AssessmentType(school_id=school.id, name="Unpublish Type", code="UNPUB_TYPE", weight=Decimal("100.00"))
    db_session.add(atype)
    await db_session.flush()
    a = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=subj.id,
        assessment_type_id=atype.id, academic_term_id=academic_term.id,
        description="Unpublish test", recorded_date=date.today(), max_score=Decimal("100.00"),
    )
    db_session.add(a)
    await db_session.flush()
    a_id = a.id

    assert (await is_report_published(student.id, academic_term.id, school.id, db_session)) is False

    publish = await client.post(f"/assessments/{a_id}/publish", headers=auth)
    assert publish.status_code == 200
    assert (await is_report_published(student.id, academic_term.id, school.id, db_session)) is True

    unpub = await client.post(f"/assessments/{a_id}/unpublish", json={"reason": "Testing"}, headers=auth)
    assert unpub.status_code == 200
    assert (await is_report_published(student.id, academic_term.id, school.id, db_session)) is False


@pytest.mark.asyncio
async def test_republish_after_unpublish_enqueues_notification_again(
    client: AsyncClient, auth: dict, assessment: Assessment,
):
    """If unpublishing genuinely re-hid the report (nothing else for this
    class+term was still published), publishing again is a real re-unlock —
    it must enqueue a fresh notification, not be treated as a duplicate."""
    import unittest.mock as mock

    mock_arq = mock.AsyncMock()

    async def _fake_get_arq():
        return mock_arq

    with mock.patch("app.services.assessment_publish.get_arq", _fake_get_arq):
        first = await client.post(f"/assessments/{assessment.id}/publish", headers=auth)
        assert first.status_code == 200
        unpub = await client.post(f"/assessments/{assessment.id}/unpublish", json={"reason": "Testing"}, headers=auth)
        assert unpub.status_code == 200
        second = await client.post(f"/assessments/{assessment.id}/publish", headers=auth)
        assert second.status_code == 200

    assert mock_arq.enqueue_job.call_count == 2, "genuinely re-unlocking the class+term must notify again"


@pytest.mark.asyncio
async def test_publishing_second_assessment_enqueues_notify_job_only_once(
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
    same class+term must not enqueue a second notify_class_report_published
    job (the actual send/log assertions live in test_report_notify_job.py —
    this test is scoped to publish_assessment()'s own enqueue-once logic)."""
    import unittest.mock as mock

    second = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        assessment_type_id=assessment_type.id, academic_term_id=academic_term.id,
        description="End-of-Term Exam", recorded_date=date.today() - timedelta(days=1),
        max_score=Decimal("100.00"),
    )
    db_session.add(second)
    await db_session.flush()

    mock_arq = mock.AsyncMock()

    async def _fake_get_arq():
        return mock_arq

    with mock.patch("app.services.assessment_publish.get_arq", _fake_get_arq):
        resp1 = await client.post(f"/assessments/{assessment.id}/publish", headers=auth)
        resp2 = await client.post(f"/assessments/{second.id}/publish", headers=auth)

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    assert mock_arq.enqueue_job.call_count == 1, (
        "Second publish for the same class+term must not enqueue a second notification job"
    )
    call = mock_arq.enqueue_job.call_args
    assert call.args[0] == "notify_class_report_published"
    assert call.kwargs["class_id"] == str(school_class.id)
    assert call.kwargs["academic_term_id"] == str(academic_term.id)
    assert call.kwargs["entity_id"] == str(assessment.id)


# ── Bulk publish ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_publish_skips_unapproved_and_already_published(
    db_session: AsyncSession, school, school_class: Class, subject, assessment_type: AssessmentType,
    academic_term: AcademicTerm, student: Student, school_admin,
):
    from app.models.assessments import Score
    from app.services.assessment_publish import bulk_publish_assessments

    approved = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        assessment_type_id=assessment_type.id, academic_term_id=academic_term.id,
        description="Approved", recorded_date=date.today(), max_score=Decimal("100.00"),
    )
    unapproved = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        assessment_type_id=assessment_type.id, academic_term_id=academic_term.id,
        description="Unapproved", recorded_date=date.today() - timedelta(days=1), max_score=Decimal("100.00"),
    )
    already_pub = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        assessment_type_id=assessment_type.id, academic_term_id=academic_term.id,
        description="Already Published", recorded_date=date.today() - timedelta(days=2),
        max_score=Decimal("100.00"), is_published=True,
    )
    db_session.add_all([approved, unapproved, already_pub])
    await db_session.flush()
    db_session.add(Score(
        school_id=school.id, assessment_id=approved.id, student_id=student.id,
        raw_score=Decimal("80.00"), is_approved=True, entered_by_id=school_admin.id,
    ))
    db_session.add(Score(
        school_id=school.id, assessment_id=unapproved.id, student_id=student.id,
        raw_score=Decimal("70.00"), is_approved=False, entered_by_id=school_admin.id,
    ))
    await db_session.flush()

    result = await bulk_publish_assessments(school_class.id, academic_term.id, school.id, db_session)

    assert result.published == 1
    assert result.skipped_unapproved == 1
    assert result.already_published == 1
    await db_session.refresh(approved)
    await db_session.refresh(unapproved)
    assert approved.is_published is True
    assert unapproved.is_published is False, "an assessment with any unapproved score must not be published"


@pytest.mark.asyncio
async def test_bulk_publish_enqueues_notification_only_once_for_the_batch(
    db_session: AsyncSession, school, school_class: Class, subject, assessment_type: AssessmentType,
    academic_term: AcademicTerm,
):
    import unittest.mock as mock
    from app.services.assessment_publish import bulk_publish_assessments

    a1 = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        assessment_type_id=assessment_type.id, academic_term_id=academic_term.id,
        description="A1", recorded_date=date.today(), max_score=Decimal("100.00"),
    )
    a2 = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        assessment_type_id=assessment_type.id, academic_term_id=academic_term.id,
        description="A2", recorded_date=date.today() - timedelta(days=1), max_score=Decimal("100.00"),
    )
    db_session.add_all([a1, a2])
    await db_session.flush()

    mock_arq = mock.AsyncMock()

    async def _fake_get_arq():
        return mock_arq

    with mock.patch("app.services.assessment_publish.get_arq", _fake_get_arq):
        result = await bulk_publish_assessments(school_class.id, academic_term.id, school.id, db_session)

    assert result.published == 2
    assert mock_arq.enqueue_job.call_count == 1, "one batch that newly unlocks the class+term must enqueue exactly one job"


@pytest.mark.asyncio
async def test_bulk_publish_rejects_cross_school_class(db_session: AsyncSession, school, academic_term: AcademicTerm):
    import uuid
    from fastapi import HTTPException
    from app.services.assessment_publish import bulk_publish_assessments

    with pytest.raises(HTTPException) as exc_info:
        await bulk_publish_assessments(uuid.uuid4(), academic_term.id, school.id, db_session)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_bulk_publish_endpoint_returns_summary(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school, school_class: Class, subject, assessment_type: AssessmentType,
    academic_term: AcademicTerm,
):
    a = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        assessment_type_id=assessment_type.id, academic_term_id=academic_term.id,
        description="Endpoint test", recorded_date=date.today(), max_score=Decimal("100.00"),
    )
    db_session.add(a)
    await db_session.flush()

    resp = await client.post("/assessments/bulk-publish", json={
        "class_id": str(school_class.id), "academic_term_id": str(academic_term.id),
    }, headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["published"] == 1
    assert data["skipped_unapproved"] == 0
    assert data["already_published"] == 0


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
async def test_submit_scores_rejects_duplicate_student_in_one_payload(
    client: AsyncClient, auth: dict, assessment: Assessment, student: Student,
):
    """Score has a UNIQUE(assessment_id, student_id) constraint — a duplicate
    student in the same submission must be rejected cleanly (422) rather than
    reaching the DB as two inserts for the same pair and raising a raw
    IntegrityError (500) on the second one."""
    resp = await client.post(f"/assessments/{assessment.id}/scores", json={
        "scores": [
            {"student_id": str(student.id), "raw_score": "70.00"},
            {"student_id": str(student.id), "raw_score": "80.00"},
        ],
    }, headers=auth)
    assert resp.status_code == 422
    assert student.first_name in resp.json()["detail"]


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
async def test_editing_a_non_default_scale_does_not_clear_other_scores_grades(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school,
    assessment: Assessment, student: Student, grading_scale: GradingScale,
):
    """resolve_grade() only ever reads from the school's *effective* default
    scale (get_default_scale_with_bands) — add_grade/delete_grade previously
    wiped every approved score's cached_grade_label school-wide regardless of
    which scale was actually edited, so tinkering with a brand new, unused
    draft scale silently blanked every report card's letter grades even
    though that scale had never resolved a single score."""
    submit = await client.post(f"/assessments/{assessment.id}/scores", json={
        "scores": [{"student_id": str(student.id), "raw_score": "85.00"}],
    }, headers=auth)
    score_id = submit.json()[0]["id"]
    approve = await client.post(f"/assessments/{assessment.id}/scores/approve", json={
        "score_ids": [score_id],
    }, headers=auth)
    assert approve.json()[0]["cached_grade_label"] == "A1"

    # A second, deliberately non-default scale — never used to resolve anything.
    draft = await client.post("/assessments/grading-scales", json={
        "name": "Draft Scale",
    }, headers=auth)
    draft_id = draft.json()["id"]
    assert draft.json()["is_default"] is False

    add = await client.post(f"/assessments/grading-scales/{draft_id}/grades", json={
        "min_score": "0.00", "max_score": "100.00", "letter_grade": "X", "label": "Test",
    }, headers=auth)
    assert add.status_code == 201

    from app.models.assessments import Score
    score = await db_session.get(Score, score_id)
    await db_session.refresh(score)
    assert score.cached_grade_label == "A1", (
        "Editing a scale that isn't the effective default must not touch "
        "grades resolved from a completely different scale"
    )

    # Deleting a band from that same non-default scale must be equally inert.
    delete = await client.delete(
        f"/assessments/grading-scales/{draft_id}/grades/{add.json()['id']}", headers=auth,
    )
    assert delete.status_code == 204
    await db_session.refresh(score)
    assert score.cached_grade_label == "A1"


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
