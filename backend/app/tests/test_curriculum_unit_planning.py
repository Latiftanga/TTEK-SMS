"""
CurriculumUnit wiring into lesson-plan creation ("pick a unit" flow) and its
supporting endpoints (extract-units trigger, list, manual-correction PATCH).

Run inside Docker: docker compose exec api pytest app/tests/test_curriculum_unit_planning.py -v
"""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class, ClassSubject, SchoolLevel, Subject, SubjectCatalogue, SubjectType
from app.models.curriculum_materials import CurriculumMaterial, ExtractionStatus
from app.models.curriculum_units import CurriculumUnit
from app.models.school import School
from app.tests.test_lesson_plans import _login_as_position, _make_subject_teacher, _payload, subject  # noqa: F401


@pytest.fixture
async def class_subject_row(db_session: AsyncSession, school: School, school_class: Class, subject: Subject) -> ClassSubject:
    return await db_session.scalar(
        select(ClassSubject).where(ClassSubject.class_id == school_class.id, ClassSubject.subject_id == subject.id)
    )


@pytest.fixture
async def other_class_subject(db_session: AsyncSession, school: School, school_class: Class) -> ClassSubject:
    """A different subject's ClassSubject — its material's units must never
    resolve for a lesson plan on the `subject` fixture's own class+subject."""
    cat = SubjectCatalogue(name="Physics", code="PHY_CUP", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, code="PHY_CUP", name="Physics", is_active=True)
    db_session.add(subj)
    await db_session.flush()
    cs = ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subj.id, is_active=True)
    db_session.add(cs)
    await db_session.flush()
    return cs


async def _make_unit(
    db_session: AsyncSession, school: School, class_subject: ClassSubject, school_admin, **overrides,
) -> CurriculumUnit:
    mat = CurriculumMaterial(
        id=uuid.uuid4(), school_id=school.id, class_subject_id=class_subject.id,
        document_type="TEACHER_MANUAL", file_path="x.pdf", file_name="x.pdf",
        file_size=1, mime_type="application/pdf", uploaded_by_id=school_admin.id,
        created_at=datetime.now(timezone.utc), extraction_status=ExtractionStatus.DONE,
        unit_extraction_status=ExtractionStatus.DONE,
    )
    db_session.add(mat)
    await db_session.flush()
    unit = CurriculumUnit(
        school_id=school.id, material_id=mat.id, sequence_number=1,
        unit_label="Week 1", strand="Number", sub_strand="Fractions",
        content_standard="Demonstrate understanding of fractions.",
        indicator="Add and subtract fractions with unlike denominators.",
        learning_objectives="Learners will add and subtract fractions.",
        topics="Fractions", source_page_start=1, source_page_end=2,
        **overrides,
    )
    db_session.add(unit)
    await db_session.flush()
    return unit


@pytest.mark.asyncio
async def test_create_autofills_from_curriculum_unit(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, class_subject_row: ClassSubject,
    academic_term: AcademicTerm, redis_permissions: None, school_admin,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    unit = await _make_unit(db_session, school, class_subject_row, school_admin)

    resp = await client.post("/lesson-plans", json={
        **_payload(academic_term, school_class, subject), "curriculum_unit_id": str(unit.id),
    }, headers=teacher_auth)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["curriculum_unit_id"] == str(unit.id)
    assert data["content_standard"] == "Demonstrate understanding of fractions."
    assert data["indicator"] == "Add and subtract fractions with unlike denominators."
    assert data["learning_objectives"] == "Learners will add and subtract fractions."
    assert data["strand"] == "Number"
    assert data["sub_strand"] == "Fractions"


@pytest.mark.asyncio
async def test_create_explicit_field_wins_over_unit(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, class_subject_row: ClassSubject,
    academic_term: AcademicTerm, redis_permissions: None, school_admin,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    unit = await _make_unit(db_session, school, class_subject_row, school_admin)

    resp = await client.post("/lesson-plans", json={
        **_payload(academic_term, school_class, subject),
        "curriculum_unit_id": str(unit.id), "content_standard": "Teacher-typed standard",
    }, headers=teacher_auth)
    assert resp.status_code == 201, resp.text
    assert resp.json()["content_standard"] == "Teacher-typed standard"


@pytest.mark.asyncio
async def test_create_rejects_unit_from_different_class_subject(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, other_class_subject: ClassSubject,
    academic_term: AcademicTerm, redis_permissions: None, school_admin,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    other_unit = await _make_unit(db_session, school, other_class_subject, school_admin)

    resp = await client.post("/lesson-plans", json={
        **_payload(academic_term, school_class, subject), "curriculum_unit_id": str(other_unit.id),
    }, headers=teacher_auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_autofills_from_curriculum_unit(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, class_subject_row: ClassSubject,
    academic_term: AcademicTerm, redis_permissions: None, school_admin,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    created = (await client.post("/lesson-plans", json=_payload(academic_term, school_class, subject), headers=teacher_auth)).json()
    assert created["content_standard"] is None

    unit = await _make_unit(db_session, school, class_subject_row, school_admin)
    patched = await client.patch(
        f"/lesson-plans/{created['id']}", json={"curriculum_unit_id": str(unit.id)}, headers=teacher_auth,
    )
    assert patched.status_code == 200, patched.text
    data = patched.json()
    assert data["content_standard"] == "Demonstrate understanding of fractions."
    assert data["strand"] == "Number"


@pytest.mark.asyncio
async def test_list_curriculum_units_for_planning_scoped(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, class_subject_row: ClassSubject,
    other_class_subject: ClassSubject, academic_term: AcademicTerm, redis_permissions: None, school_admin,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    unit = await _make_unit(db_session, school, class_subject_row, school_admin)
    await _make_unit(db_session, school, other_class_subject, school_admin)  # a different subject's unit

    resp = await client.get("/lesson-plans/curriculum-units", params={
        "class_id": str(school_class.id), "subject_id": str(subject.id), "academic_term_id": str(academic_term.id),
    }, headers=teacher_auth)
    assert resp.status_code == 200, resp.text
    assert [u["id"] for u in resp.json()] == [str(unit.id)]


@pytest.mark.asyncio
async def test_list_curriculum_units_404_for_non_owning_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None,
):
    teacher_auth, _ = await _login_as_position(client, auth, db_session, school, "TEACHER")
    resp = await client.get("/lesson-plans/curriculum-units", params={
        "class_id": str(school_class.id), "subject_id": str(subject.id), "academic_term_id": str(academic_term.id),
    }, headers=teacher_auth)
    assert resp.status_code == 404


# ── extract-units trigger / list / correction endpoints ────────────────────

@pytest.mark.asyncio
async def test_extract_units_trigger_and_list_and_patch(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, class_subject_row: ClassSubject, school_admin,
):
    mat = CurriculumMaterial(
        id=uuid.uuid4(), school_id=school.id, class_subject_id=class_subject_row.id,
        document_type="TEACHER_MANUAL", file_path="x.pdf", file_name="x.pdf",
        file_size=1, mime_type="application/pdf", uploaded_by_id=school_admin.id,
        created_at=datetime.now(timezone.utc), extraction_status=ExtractionStatus.DONE,
    )
    db_session.add(mat)
    await db_session.flush()

    triggered = await client.post(f"/curriculum-materials/{mat.id}/extract-units", headers=auth)
    assert triggered.status_code == 200, triggered.text
    assert triggered.json()["unit_extraction_status"] == "PENDING"

    unit = CurriculumUnit(
        school_id=school.id, material_id=mat.id, sequence_number=1, unit_label="Week 1",
        content_standard="A standard.", source_page_start=1, source_page_end=1,
    )
    db_session.add(unit)
    await db_session.flush()

    listed = await client.get(f"/curriculum-materials/{mat.id}/units", headers=auth)
    assert listed.status_code == 200
    assert [u["id"] for u in listed.json()] == [str(unit.id)]

    patched = await client.patch(f"/curriculum-units/{unit.id}", json={"content_standard": "Corrected standard."}, headers=auth)
    assert patched.status_code == 200, patched.text
    assert patched.json()["content_standard"] == "Corrected standard."


@pytest.mark.asyncio
async def test_extract_units_404_for_cross_school_material(client: AsyncClient, auth: dict):
    resp = await client.post(f"/curriculum-materials/{uuid.uuid4()}/extract-units", headers=auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_unit_404_for_cross_school(client: AsyncClient, auth: dict):
    resp = await client.patch(f"/curriculum-units/{uuid.uuid4()}", json={"topics": "x"}, headers=auth)
    assert resp.status_code == 404
