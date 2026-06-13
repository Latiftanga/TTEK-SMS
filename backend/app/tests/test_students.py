"""
Student profile integration tests (CRUD, guardians, medical record).
Run inside Docker: docker compose exec api pytest app/tests/test_students.py -v
"""
import pytest
from httpx import AsyncClient


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


@pytest.mark.asyncio
async def test_list_students_search(client: AsyncClient, auth: dict):
    await client.post("/students", json=_student("ADM001", last_name="Mensah"), headers=auth)
    await client.post("/students", json=_student("ADM002", last_name="Asante"), headers=auth)
    resp = await client.get("/students?search=mensah", headers=auth)
    assert len(resp.json()) == 1
    assert resp.json()[0]["last_name"] == "Mensah"


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
