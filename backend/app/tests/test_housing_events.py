"""
Housing events integration tests — roll calls and exeats.
Run inside Docker: docker compose exec api pytest app/tests/test_housing_events.py -v
"""
import uuid
import pytest
from httpx import AsyncClient

from app.models.attendance import SchoolCalendar


async def _make_house(client: AsyncClient, auth: dict, code: str = "EVH") -> dict:
    r = await client.post("/housing/houses", json={
        "name": f"Hall {code}", "code": code, "gender": "MALE",
    }, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


async def _make_student(client: AsyncClient, auth: dict, adm: str = "EVT001") -> dict:
    r = await client.post("/students", json={
        "admission_number": adm, "first_name": "Event", "last_name": "Student",
    }, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


# ── Roll calls ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_roll_call(
    client: AsyncClient, auth: dict, school_calendar: SchoolCalendar,
):
    h = await _make_house(client, auth, code="RCH1")
    r = await client.post("/housing/roll-calls", json={
        "house_id": h["id"],
        "school_calendar_id": str(school_calendar.id),
        "total_expected": 50,
        "total_present": 48,
        "notes": "2 students on exeat",
    }, headers=auth)
    assert r.status_code == 201
    d = r.json()
    assert d["total_expected"] == 50
    assert d["total_present"] == 48
    assert d["notes"] == "2 students on exeat"
    assert d["house_id"] == h["id"]


@pytest.mark.asyncio
async def test_list_roll_calls(
    client: AsyncClient, auth: dict, school_calendar: SchoolCalendar,
):
    h = await _make_house(client, auth, code="RCH2")
    await client.post("/housing/roll-calls", json={
        "house_id": h["id"],
        "school_calendar_id": str(school_calendar.id),
        "total_expected": 50, "total_present": 50,
    }, headers=auth)
    r = await client.get(f"/housing/roll-calls?house_id={h['id']}", headers=auth)
    assert r.status_code == 200
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_rollcall_unknown_calendar_rejected(client: AsyncClient, auth: dict):
    h = await _make_house(client, auth, code="RCH3")
    r = await client.post("/housing/roll-calls", json={
        "house_id": h["id"],
        "school_calendar_id": str(uuid.uuid4()),
        "total_expected": 50, "total_present": 48,
    }, headers=auth)
    assert r.status_code == 404


# ── Exeats ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_exeat(client: AsyncClient, auth: dict):
    s = await _make_student(client, auth, adm="EX001")
    r = await client.post("/housing/exeats", json={
        "student_id": s["id"],
        "reason": "Family visit",
        "destination": "Kumasi",
        "departure_date": "2024-11-01",
        "return_date": "2024-11-03",
    }, headers=auth)
    assert r.status_code == 201
    d = r.json()
    assert d["status"] == "PENDING"
    assert d["destination"] == "Kumasi"
    assert d["approved_by_id"] is None


@pytest.mark.asyncio
async def test_list_pending_exeats(client: AsyncClient, auth: dict):
    s = await _make_student(client, auth, adm="EX002")
    await client.post("/housing/exeats", json={
        "student_id": s["id"], "reason": "Sick",
        "destination": "Accra",
        "departure_date": "2024-11-01", "return_date": "2024-11-02",
    }, headers=auth)
    r = await client.get("/housing/exeats/pending", headers=auth)
    assert r.status_code == 200
    assert len(r.json()) >= 1
    assert all(e["status"] == "PENDING" for e in r.json())


@pytest.mark.asyncio
async def test_approve_exeat(client: AsyncClient, auth: dict):
    s = await _make_student(client, auth, adm="EX003")
    e_r = await client.post("/housing/exeats", json={
        "student_id": s["id"], "reason": "Visit", "destination": "Tema",
        "departure_date": "2024-11-01", "return_date": "2024-11-04",
    }, headers=auth)
    e = e_r.json()
    r = await client.patch(f"/housing/exeats/{e['id']}/approve", json={"status": "APPROVED"}, headers=auth)
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "APPROVED"
    assert d["approved_by_id"] is not None


@pytest.mark.asyncio
async def test_reject_exeat(client: AsyncClient, auth: dict):
    s = await _make_student(client, auth, adm="EX004")
    e_r = await client.post("/housing/exeats", json={
        "student_id": s["id"], "reason": "Trip", "destination": "Cape Coast",
        "departure_date": "2024-11-01", "return_date": "2024-11-02",
    }, headers=auth)
    e = e_r.json()
    r = await client.patch(f"/housing/exeats/{e['id']}/approve", json={"status": "REJECTED"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["status"] == "REJECTED"


@pytest.mark.asyncio
async def test_double_review_rejected(client: AsyncClient, auth: dict):
    s = await _make_student(client, auth, adm="EX005")
    e_r = await client.post("/housing/exeats", json={
        "student_id": s["id"], "reason": "Visit", "destination": "Accra",
        "departure_date": "2024-11-01", "return_date": "2024-11-03",
    }, headers=auth)
    e = e_r.json()
    await client.patch(f"/housing/exeats/{e['id']}/approve", json={"status": "APPROVED"}, headers=auth)
    r = await client.patch(f"/housing/exeats/{e['id']}/approve", json={"status": "REJECTED"}, headers=auth)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_record_return(client: AsyncClient, auth: dict):
    s = await _make_student(client, auth, adm="EX006")
    e_r = await client.post("/housing/exeats", json={
        "student_id": s["id"], "reason": "Visit", "destination": "Tema",
        "departure_date": "2024-11-01", "return_date": "2024-11-04",
    }, headers=auth)
    e = e_r.json()
    await client.patch(f"/housing/exeats/{e['id']}/approve", json={"status": "APPROVED"}, headers=auth)
    r = await client.patch(
        f"/housing/exeats/{e['id']}/return", json={"actual_return_date": "2024-11-04"}, headers=auth
    )
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "RETURNED"
    assert d["actual_return_date"] == "2024-11-04"


@pytest.mark.asyncio
async def test_return_on_unapproved_rejected(client: AsyncClient, auth: dict):
    s = await _make_student(client, auth, adm="EX007")
    e_r = await client.post("/housing/exeats", json={
        "student_id": s["id"], "reason": "Visit", "destination": "Accra",
        "departure_date": "2024-11-01", "return_date": "2024-11-03",
    }, headers=auth)
    e = e_r.json()
    r = await client.patch(
        f"/housing/exeats/{e['id']}/return", json={"actual_return_date": "2024-11-03"}, headers=auth
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_list_student_exeats(client: AsyncClient, auth: dict):
    s = await _make_student(client, auth, adm="EX008")
    await client.post("/housing/exeats", json={
        "student_id": s["id"], "reason": "Visit", "destination": "Takoradi",
        "departure_date": "2024-11-01", "return_date": "2024-11-02",
    }, headers=auth)
    r = await client.get(f"/housing/students/{s['id']}/exeats", headers=auth)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["student_id"] == s["id"]


@pytest.mark.asyncio
async def test_exeat_return_before_departure_rejected(client: AsyncClient, auth: dict):
    s = await _make_student(client, auth, adm="EX009")
    r = await client.post("/housing/exeats", json={
        "student_id": s["id"], "reason": "Visit", "destination": "Accra",
        "departure_date": "2024-11-05",
        "return_date": "2024-11-01",
    }, headers=auth)
    assert r.status_code == 422
