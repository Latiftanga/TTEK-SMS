"""
Housing integration tests — houses, rooms, housemasters, student assignments.
Run inside Docker: docker compose exec api pytest app/tests/test_housing.py -v
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicYear
from app.models.school import School
from app.models.staff import StaffMember


async def _make_house(client: AsyncClient, auth: dict, code: str = "HAA", gender: str = "MALE") -> dict:
    r = await client.post("/housing/houses", json={
        "name": f"Hall {code}", "code": code, "gender": gender,
    }, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


async def _make_student(client: AsyncClient, auth: dict, adm: str = "STU001", gender: str = "MALE") -> dict:
    r = await client.post("/students", json={
        "admission_number": adm, "first_name": "Test", "last_name": "Student", "gender": gender,
    }, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


# ── Boarding guard ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_housing_blocked_for_non_boarding_school(
    client: AsyncClient, auth: dict,
    db_session: AsyncSession, school: School,
):
    school.has_boarding = False
    await db_session.flush()
    r = await client.post("/housing/houses", json={
        "name": "Ghost Hall", "code": "NOHB", "gender": "MALE",
    }, headers=auth)
    assert r.status_code == 403
    assert "boarding" in r.json()["detail"].lower()


# ── Houses ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_house(client: AsyncClient, auth: dict):
    r = await client.post("/housing/houses", json={
        "name": "Aggrey Hall", "code": "AH", "gender": "MALE",
        "capacity": 100, "color": "#001f5b",
    }, headers=auth)
    assert r.status_code == 201
    d = r.json()
    assert d["code"] == "AH"
    assert d["gender"] == "MALE"
    assert d["capacity"] == 100
    assert d["is_active"] is True
    assert d["rooms"] == []


@pytest.mark.asyncio
async def test_list_houses(client: AsyncClient, auth: dict):
    await _make_house(client, auth, code="LH1")
    await _make_house(client, auth, code="LH2", gender="FEMALE")
    r = await client.get("/housing/houses", headers=auth)
    assert r.status_code == 200
    codes = {h["code"] for h in r.json()}
    assert "LH1" in codes and "LH2" in codes


@pytest.mark.asyncio
async def test_get_house(client: AsyncClient, auth: dict):
    h = await _make_house(client, auth, code="GH1")
    r = await client.get(f"/housing/houses/{h['id']}", headers=auth)
    assert r.status_code == 200
    assert r.json()["id"] == h["id"]


@pytest.mark.asyncio
async def test_update_house(client: AsyncClient, auth: dict):
    h = await _make_house(client, auth, code="UH1")
    r = await client.patch(f"/housing/houses/{h['id']}", json={"capacity": 120}, headers=auth)
    assert r.status_code == 200
    assert r.json()["capacity"] == 120


@pytest.mark.asyncio
async def test_deactivate_house(client: AsyncClient, auth: dict):
    h = await _make_house(client, auth, code="DH1")
    r = await client.patch(f"/housing/houses/{h['id']}", json={"is_active": False}, headers=auth)
    assert r.status_code == 200
    assert r.json()["is_active"] is False


@pytest.mark.asyncio
async def test_duplicate_house_code_rejected(client: AsyncClient, auth: dict):
    await _make_house(client, auth, code="DUPX")
    r = await client.post("/housing/houses", json={
        "name": "Another Hall", "code": "DUPX", "gender": "FEMALE",
    }, headers=auth)
    assert r.status_code == 409


# ── Rooms ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_room(client: AsyncClient, auth: dict):
    h = await _make_house(client, auth, code="RH1")
    r = await client.post(f"/housing/houses/{h['id']}/rooms", json={
        "room_number": "1A", "capacity": 4,
    }, headers=auth)
    assert r.status_code == 201
    d = r.json()
    assert d["room_number"] == "1A"
    assert d["room_type"] == "DORMITORY"
    assert d["house_id"] == h["id"]


@pytest.mark.asyncio
async def test_list_rooms(client: AsyncClient, auth: dict):
    h = await _make_house(client, auth, code="RH2")
    await client.post(f"/housing/houses/{h['id']}/rooms", json={"room_number": "1A"}, headers=auth)
    await client.post(f"/housing/houses/{h['id']}/rooms", json={"room_number": "1B"}, headers=auth)
    r = await client.get(f"/housing/houses/{h['id']}/rooms", headers=auth)
    assert r.status_code == 200
    assert len(r.json()) == 2


@pytest.mark.asyncio
async def test_house_detail_includes_rooms(client: AsyncClient, auth: dict):
    h = await _make_house(client, auth, code="RH3")
    await client.post(f"/housing/houses/{h['id']}/rooms", json={"room_number": "2A"}, headers=auth)
    r = await client.get(f"/housing/houses/{h['id']}", headers=auth)
    assert r.status_code == 200
    assert len(r.json()["rooms"]) == 1


@pytest.mark.asyncio
async def test_update_room(client: AsyncClient, auth: dict):
    h = await _make_house(client, auth, code="RH4")
    room_r = await client.post(
        f"/housing/houses/{h['id']}/rooms", json={"room_number": "3A", "capacity": 4}, headers=auth
    )
    room = room_r.json()
    r = await client.patch(
        f"/housing/houses/{h['id']}/rooms/{room['id']}", json={"capacity": 6}, headers=auth
    )
    assert r.status_code == 200
    assert r.json()["capacity"] == 6


# ── HouseMaster ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_assign_house_master(
    client: AsyncClient, auth: dict,
    staff_member: StaffMember, academic_year: AcademicYear,
):
    h = await _make_house(client, auth, code="HMH1")
    r = await client.post(f"/housing/houses/{h['id']}/master", json={
        "staff_member_id": str(staff_member.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)
    assert r.status_code == 201
    d = r.json()
    assert d["staff_member_id"] == str(staff_member.id)
    assert d["is_active"] is True


@pytest.mark.asyncio
async def test_reassign_housemaster_deactivates_previous(
    client: AsyncClient, auth: dict,
    staff_member: StaffMember, academic_year: AcademicYear,
):
    h = await _make_house(client, auth, code="HMH2")
    await client.post(f"/housing/houses/{h['id']}/master", json={
        "staff_member_id": str(staff_member.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)
    await client.post(f"/housing/houses/{h['id']}/master", json={
        "staff_member_id": str(staff_member.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)
    r = await client.get(
        f"/housing/houses/{h['id']}/master?year_id={academic_year.id}", headers=auth
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is True


@pytest.mark.asyncio
async def test_remove_house_master(
    client: AsyncClient, auth: dict,
    staff_member: StaffMember, academic_year: AcademicYear,
):
    h = await _make_house(client, auth, code="HMH3")
    await client.post(f"/housing/houses/{h['id']}/master", json={
        "staff_member_id": str(staff_member.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)

    r = await client.delete(
        f"/housing/houses/{h['id']}/master?year_id={academic_year.id}", headers=auth,
    )
    assert r.status_code == 204

    listed = await client.get(
        f"/housing/houses/{h['id']}/master?year_id={academic_year.id}", headers=auth,
    )
    assert listed.json() is None


@pytest.mark.asyncio
async def test_remove_house_master_404_when_nothing_to_remove(
    client: AsyncClient, auth: dict, academic_year: AcademicYear,
):
    h = await _make_house(client, auth, code="HMH4")

    r = await client.delete(
        f"/housing/houses/{h['id']}/master?year_id={academic_year.id}", headers=auth,
    )
    assert r.status_code == 404


# ── Student assignments ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_assign_student_to_house(
    client: AsyncClient, auth: dict, academic_year: AcademicYear,
):
    h = await _make_house(client, auth, code="SAH1")
    s = await _make_student(client, auth, adm="HSTU001")
    r = await client.post("/housing/assignments", json={
        "student_id": s["id"], "house_id": h["id"],
        "academic_year_id": str(academic_year.id), "assigned_at": "2024-09-01",
    }, headers=auth)
    assert r.status_code == 201
    d = r.json()
    assert d["student_id"] == s["id"]
    assert d["vacated_at"] is None


@pytest.mark.asyncio
async def test_assign_student_wrong_gender_rejected(
    client: AsyncClient, auth: dict, academic_year: AcademicYear,
):
    h = await _make_house(client, auth, code="SAH5", gender="MALE")
    s = await _make_student(client, auth, adm="HSTU005", gender="FEMALE")
    r = await client.post("/housing/assignments", json={
        "student_id": s["id"], "house_id": h["id"],
        "academic_year_id": str(academic_year.id), "assigned_at": "2024-09-01",
    }, headers=auth)
    assert r.status_code == 422
    assert "female" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_assign_student_missing_gender_rejected(
    client: AsyncClient, auth: dict, academic_year: AcademicYear,
):
    h = await _make_house(client, auth, code="SAH6", gender="MALE")
    r = await client.post("/students", json={
        "admission_number": "HSTU006", "first_name": "Test", "last_name": "Student",
    }, headers=auth)
    s = r.json()
    resp = await client.post("/housing/assignments", json={
        "student_id": s["id"], "house_id": h["id"],
        "academic_year_id": str(academic_year.id), "assigned_at": "2024-09-01",
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_assign_student_to_mixed_house_any_gender(
    client: AsyncClient, auth: dict, academic_year: AcademicYear,
):
    h = await _make_house(client, auth, code="SAH7", gender="MIXED")
    s = await _make_student(client, auth, adm="HSTU007", gender="FEMALE")
    r = await client.post("/housing/assignments", json={
        "student_id": s["id"], "house_id": h["id"],
        "academic_year_id": str(academic_year.id), "assigned_at": "2024-09-01",
    }, headers=auth)
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_assign_student_sets_is_boarding(
    client: AsyncClient, auth: dict, academic_year: AcademicYear,
):
    """A student housed in a dorm must be flagged is_boarding — otherwise
    boarding_only fee structures (services/fees.py) silently skip them."""
    h = await _make_house(client, auth, code="SAH8")
    s = await _make_student(client, auth, adm="HSTU008")
    assert s["is_boarding"] is False
    await client.post("/housing/assignments", json={
        "student_id": s["id"], "house_id": h["id"],
        "academic_year_id": str(academic_year.id), "assigned_at": "2024-09-01",
    }, headers=auth)
    r = await client.get(f"/students/{s['id']}", headers=auth)
    assert r.json()["is_boarding"] is True


@pytest.mark.asyncio
async def test_duplicate_assignment_rejected(
    client: AsyncClient, auth: dict, academic_year: AcademicYear,
):
    h = await _make_house(client, auth, code="SAH2")
    s = await _make_student(client, auth, adm="HSTU002")
    payload = {
        "student_id": s["id"], "house_id": h["id"],
        "academic_year_id": str(academic_year.id), "assigned_at": "2024-09-01",
    }
    await client.post("/housing/assignments", json=payload, headers=auth)
    r = await client.post("/housing/assignments", json=payload, headers=auth)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_vacate_assignment(
    client: AsyncClient, auth: dict, academic_year: AcademicYear,
):
    h = await _make_house(client, auth, code="SAH3")
    s = await _make_student(client, auth, adm="HSTU003")
    a_r = await client.post("/housing/assignments", json={
        "student_id": s["id"], "house_id": h["id"],
        "academic_year_id": str(academic_year.id), "assigned_at": "2024-09-01",
    }, headers=auth)
    a = a_r.json()
    r = await client.patch(
        f"/housing/assignments/{a['id']}/vacate", json={"vacated_at": "2024-12-20"}, headers=auth
    )
    assert r.status_code == 200
    assert r.json()["vacated_at"] == "2024-12-20"


@pytest.mark.asyncio
async def test_get_student_current_assignment(
    client: AsyncClient, auth: dict, academic_year: AcademicYear,
):
    h = await _make_house(client, auth, code="SAH4")
    s = await _make_student(client, auth, adm="HSTU004")
    await client.post("/housing/assignments", json={
        "student_id": s["id"], "house_id": h["id"],
        "academic_year_id": str(academic_year.id), "assigned_at": "2024-09-01",
    }, headers=auth)
    r = await client.get(
        f"/housing/students/{s['id']}/assignment?year_id={academic_year.id}", headers=auth
    )
    assert r.status_code == 200
    assert r.json()["student_id"] == s["id"]
