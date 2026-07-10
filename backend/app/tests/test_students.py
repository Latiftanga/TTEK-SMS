"""
Student profile integration tests (CRUD, guardians, medical record).
Run inside Docker: docker compose exec api pytest app/tests/test_students.py -v
"""
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicYear, Class
from app.models.school import School
from app.models.students import StudentClassAssignment


def _student(num: str = "ADM001", **kw) -> dict:
    return {"admission_number": num, "first_name": "Ama", "last_name": "Boateng", **kw}


# ── Student CRUD ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_student(client: AsyncClient, auth: dict):
    resp = await client.post("/students", json=_student(), headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["admission_number"] == "ADM001"
    assert data["display_name"] == "Ama Boateng"
    assert data["guardians"] == []
    assert data["medical_record"] is None


@pytest.mark.asyncio
async def test_create_student_with_middle_name(client: AsyncClient, auth: dict):
    resp = await client.post("/students", json=_student(middle_name="Akua"), headers=auth)
    assert resp.status_code == 201
    assert resp.json()["display_name"] == "Ama Akua Boateng"


@pytest.mark.asyncio
async def test_duplicate_admission_number_rejected(client: AsyncClient, auth: dict):
    await client.post("/students", json=_student(), headers=auth)
    resp = await client.post("/students", json=_student(), headers=auth)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_students(client: AsyncClient, auth: dict):
    await client.post("/students", json=_student("ADM001"), headers=auth)
    await client.post("/students", json=_student("ADM002"), headers=auth)
    resp = await client.get("/students", headers=auth)
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert resp.headers["x-total-count"] == "2"


@pytest.mark.asyncio
async def test_list_students_total_count_exceeds_page(client: AsyncClient, auth: dict):
    for i in range(3):
        await client.post("/students", json=_student(f"ADM00{i}"), headers=auth)
    resp = await client.get("/students?limit=2", headers=auth)
    assert len(resp.json()) == 2
    assert resp.headers["x-total-count"] == "3"


@pytest.mark.asyncio
async def test_list_students_search(client: AsyncClient, auth: dict):
    await client.post("/students", json=_student("ADM001", last_name="Mensah"), headers=auth)
    await client.post("/students", json=_student("ADM002", last_name="Asante"), headers=auth)
    resp = await client.get("/students?search=mensah", headers=auth)
    assert len(resp.json()) == 1
    assert resp.json()[0]["last_name"] == "Mensah"
    assert resp.headers["x-total-count"] == "1"


# ── Sort ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_students_sort_by_name(client: AsyncClient, auth: dict):
    await client.post("/students", json=_student("ADM001", last_name="Zulu"), headers=auth)
    await client.post("/students", json=_student("ADM002", last_name="Asante"), headers=auth)
    resp = await client.get("/students?sort_by=name&sort_dir=asc", headers=auth)
    names = [s["last_name"] for s in resp.json()]
    assert names == ["Asante", "Zulu"]

    resp = await client.get("/students?sort_by=name&sort_dir=desc", headers=auth)
    names = [s["last_name"] for s in resp.json()]
    assert names == ["Zulu", "Asante"]


@pytest.mark.asyncio
async def test_list_students_sort_by_admission(client: AsyncClient, auth: dict):
    await client.post("/students", json=_student("ADM009"), headers=auth)
    await client.post("/students", json=_student("ADM001"), headers=auth)
    resp = await client.get("/students?sort_by=admission&sort_dir=asc", headers=auth)
    numbers = [s["admission_number"] for s in resp.json()]
    assert numbers == ["ADM001", "ADM009"]


@pytest.mark.asyncio
async def test_list_students_sort_by_class(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_year: AcademicYear, db_session: AsyncSession, school: School,
):
    # school_class fixture is SHS year_group=2; give it a lower-ranked Basic class to sort before it.
    basic_class = Class(school_id=school.id, level="Basic", year_group=6, is_active=True)
    db_session.add(basic_class)
    await db_session.flush()

    sid_shs = (await client.post("/students", json=_student("ADM001"), headers=auth)).json()["id"]
    sid_basic = (await client.post("/students", json=_student("ADM002"), headers=auth)).json()["id"]
    sid_none = (await client.post("/students", json=_student("ADM003"), headers=auth)).json()["id"]

    await client.post("/students/class-assignments", json={
        "student_id": sid_shs, "class_id": str(school_class.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)
    await client.post("/students/class-assignments", json={
        "student_id": sid_basic, "class_id": str(basic_class.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)

    resp = await client.get("/students?sort_by=class&sort_dir=asc", headers=auth)
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    # Basic (pedagogically before SHS) first, then SHS, then no-class student last (nulls_last).
    assert ids == [sid_basic, sid_shs, sid_none]


# ── Multi-active class assignment (promoted, not graduated) ───────────────────

@pytest.mark.asyncio
async def test_list_students_promoted_student_not_double_counted(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_year: AcademicYear, db_session: AsyncSession, school: School,
):
    """A promoted (non-graduated) student can hold 2+ is_active StudentClassAssignment
    rows across academic years — the list/count must dedup to the most recent one."""
    sid = (await client.post("/students", json=_student("ADM001"), headers=auth)).json()["id"]

    next_year = AcademicYear(
        school_id=school.id, name="2025/2026",
        start_date=date(2025, 9, 1), end_date=date(2026, 7, 31), is_current=False,
    )
    db_session.add(next_year)
    await db_session.flush()
    next_class = Class(school_id=school.id, level="SHS", year_group=3, stream="A", is_active=True)
    db_session.add(next_class)
    await db_session.flush()

    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=sid, class_id=school_class.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=sid, class_id=next_class.id,
        academic_year_id=next_year.id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.get("/students", headers=auth)
    assert resp.status_code == 200
    assert resp.headers["x-total-count"] == "1"
    assert len(resp.json()) == 1
    # Most-recently-created assignment (next_class, SHS year_group=3) wins.
    assert resp.json()[0]["current_class_id"] == str(next_class.id)


@pytest.mark.asyncio
async def test_get_student(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    resp = await client.get(f"/students/{sid}", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["id"] == sid


@pytest.mark.asyncio
async def test_update_student(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    resp = await client.patch(f"/students/{sid}", json={"nationality": "Ghanaian"}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["nationality"] == "Ghanaian"


@pytest.mark.asyncio
async def test_deactivate_student(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    await client.patch(f"/students/{sid}", json={"is_active": False}, headers=auth)
    active_list = (await client.get("/students", headers=auth)).json()
    assert all(s["id"] != sid for s in active_list)
    all_list = (await client.get("/students?active_only=false", headers=auth)).json()
    assert any(s["id"] == sid for s in all_list)


# ── Medical record ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_medical_record(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    resp = await client.put(f"/students/{sid}/medical", json={
        "blood_group": "O+", "allergies": "Peanuts",
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["blood_group"] == "O+"

    # Update (upsert — same endpoint)
    resp2 = await client.put(f"/students/{sid}/medical", json={"blood_group": "A+"}, headers=auth)
    assert resp2.json()["blood_group"] == "A+"
    assert resp2.json()["allergies"] == "Peanuts"   # previous value preserved


# ── Guardian management ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_and_remove_guardian(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    resp = await client.post(f"/students/{sid}/guardians", json={
        "first_name": "Kofi", "last_name": "Boateng",
        "phone": "0244000001", "relation_type": "Father", "is_primary": True,
    }, headers=auth)
    assert resp.status_code == 201
    guardian_id = resp.json()["guardian_id"]
    assert resp.json()["is_primary"] is True

    detail = (await client.get(f"/students/{sid}", headers=auth)).json()
    assert len(detail["guardians"]) == 1

    await client.delete(f"/students/{sid}/guardians/{guardian_id}", headers=auth)
    detail = (await client.get(f"/students/{sid}", headers=auth)).json()
    assert len(detail["guardians"]) == 0


@pytest.mark.asyncio
async def test_primary_guardian_demoted(client: AsyncClient, auth: dict):
    """Adding a second primary guardian demotes the first."""
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    await client.post(f"/students/{sid}/guardians", json={
        "first_name": "Kofi", "last_name": "Boateng",
        "phone": "0244000001", "relation_type": "Father", "is_primary": True,
    }, headers=auth)
    await client.post(f"/students/{sid}/guardians", json={
        "first_name": "Abena", "last_name": "Boateng",
        "phone": "0244000002", "relation_type": "Mother", "is_primary": True,
    }, headers=auth)
    detail = (await client.get(f"/students/{sid}", headers=auth)).json()
    primaries = [g for g in detail["guardians"] if g["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["first_name"] == "Abena"
