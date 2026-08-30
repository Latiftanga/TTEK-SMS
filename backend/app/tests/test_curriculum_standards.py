"""
Curriculum standard CRUD — minimal admin-facing create/list/search/retire,
gated on the existing academic.* permission tier. Starts empty; a school's
own private rows (school_id set) coexist with any shared GES-wide rows
(school_id NULL) exactly like SubjectCatalogue.

Run inside Docker: docker compose exec api pytest app/tests/test_curriculum_standards.py -v
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import SchoolLevel, SubjectCatalogue, SubjectType
from app.models.school import School


@pytest.fixture
async def catalogue(db_session: AsyncSession) -> SubjectCatalogue:
    cat = SubjectCatalogue(name="Mathematics", code="MATH_CS", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    return cat


def _payload(catalogue: SubjectCatalogue) -> dict:
    return {
        "subject_catalogue_id": str(catalogue.id), "level": "SHS", "year_group": 2,
        "strand": "Number", "sub_strand": "Fractions", "indicator_code": "B7.1.1.1",
        "objective_text": "Add and subtract fractions with unlike denominators.",
    }


@pytest.mark.asyncio
async def test_create_and_list_curriculum_standard(client: AsyncClient, auth: dict, catalogue: SubjectCatalogue):
    resp = await client.post("/curriculum-standards", json=_payload(catalogue), headers=auth)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["indicator_code"] == "B7.1.1.1"
    assert data["school_id"] is not None  # created as this school's own private row

    listed = await client.get(
        "/curriculum-standards", params={"subject_catalogue_id": str(catalogue.id)}, headers=auth,
    )
    assert listed.status_code == 200
    assert [r["id"] for r in listed.json()] == [data["id"]]


@pytest.mark.asyncio
async def test_list_filters_by_level_and_year_group(client: AsyncClient, auth: dict, catalogue: SubjectCatalogue):
    await client.post("/curriculum-standards", json=_payload(catalogue), headers=auth)
    other = _payload(catalogue)
    other["year_group"] = 3
    other["indicator_code"] = "B7.1.1.2"
    await client.post("/curriculum-standards", json=other, headers=auth)

    resp = await client.get(
        "/curriculum-standards",
        params={"subject_catalogue_id": str(catalogue.id), "year_group": 2}, headers=auth,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["year_group"] == 2


@pytest.mark.asyncio
async def test_deactivate_hides_from_default_list(client: AsyncClient, auth: dict, catalogue: SubjectCatalogue):
    created = (await client.post("/curriculum-standards", json=_payload(catalogue), headers=auth)).json()

    patched = await client.patch(f"/curriculum-standards/{created['id']}", json={"is_active": False}, headers=auth)
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False

    listed = await client.get(
        "/curriculum-standards", params={"subject_catalogue_id": str(catalogue.id)}, headers=auth,
    )
    assert listed.json() == []

    listed_incl = await client.get(
        "/curriculum-standards",
        params={"subject_catalogue_id": str(catalogue.id), "include_inactive": True}, headers=auth,
    )
    assert [r["id"] for r in listed_incl.json()] == [created["id"]]


@pytest.mark.asyncio
async def test_curriculum_standard_autofills_lesson_plan(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    catalogue: SubjectCatalogue, school_class, academic_term, redis_permissions: None,
):
    from app.models.academic import ClassSubject, SubjectTeacher, Subject
    from app.tests.test_lesson_plans import _login_as_position

    subj = Subject(school_id=school.id, catalogue_id=catalogue.id, code="MATH_CS", name="Mathematics", is_active=True)
    db_session.add(subj)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subj.id, is_active=True))
    await db_session.flush()

    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    db_session.add(SubjectTeacher(
        school_id=school.id, class_id=school_class.id, subject_id=subj.id,
        staff_member_id=staff_id, academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()

    cs = (await client.post("/curriculum-standards", json=_payload(catalogue), headers=auth)).json()

    resp = await client.post("/lesson-plans", json={
        "class_id": str(school_class.id), "subject_id": str(subj.id),
        "academic_term_id": str(academic_term.id), "week_start_date": "2024-09-09",
        "topic": "Fractions", "curriculum_standard_id": cs["id"],
    }, headers=teacher_auth)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["indicator"] == "B7.1.1.1"
    assert data["content_standard"] == "Number — Fractions"
    assert data["learning_objectives"] == cs["objective_text"]
    assert data["curriculum_standard_id"] == cs["id"]
