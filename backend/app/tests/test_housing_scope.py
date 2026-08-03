"""
Per-house scoping for Housing — core/housing_scope.py unit tests plus
integration coverage across the housing router (mirrors test_student_scope.py/
test_behaviour_scope.py's split: direct resolver tests here, plus real
HTTP-level regression tests for the endpoints that now enforce scope).

Run inside Docker: docker compose exec api pytest app/tests/test_housing_scope.py -v
"""
from datetime import date

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.core.housing_scope import assert_house_in_scope, assert_unrestricted, resolve_house_scope
from app.models.academic import AcademicYear
from app.models.auth import LoginType, StaffPosition, User
from app.models.housing import House, HouseGender, HouseMaster
from app.models.school import School
from app.models.staff import StaffMember


async def _make_house(db_session: AsyncSession, school: School, code: str) -> House:
    house = House(school_id=school.id, name=f"Hall {code}", code=code, gender=HouseGender.MIXED, is_active=True)
    db_session.add(house)
    await db_session.flush()
    return house


async def _make_housemaster_staff(
    db_session: AsyncSession, school: School, suffix: str,
) -> tuple[StaffMember, User]:
    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == "HOUSEMASTER"))
    assert pos is not None, "Run seed_reference_data.py first"

    staff = StaffMember(school_id=school.id, staff_number=f"HMSCOPE-{suffix}", first_name="House", last_name=suffix)
    db_session.add(staff)
    await db_session.flush()

    from app.models.staff import staff_member_positions
    await db_session.execute(
        staff_member_positions.insert().values(staff_member_id=staff.id, position_id=pos.id)
    )
    user = User(
        school_id=school.id, login_type=LoginType.EMAIL, email=f"hmscope-{suffix.lower()}@presec-test.edu.gh",
        password_hash=hash_password("Whatever123!"), is_active=True, staff_member_id=staff.id,
    )
    db_session.add(user)
    await db_session.flush()
    return staff, user


async def _login(client: AsyncClient, email: str) -> dict:
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL", "identifier": email, "password": "Whatever123!",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Unit tests: resolve_house_scope / assert_house_in_scope / assert_unrestricted ──

@pytest.mark.asyncio
async def test_superadmin_is_unrestricted(db_session: AsyncSession, school: School, school_admin: User):
    scope = await resolve_house_scope(school_admin.id, school.id, None, db_session)
    assert scope is None


@pytest.mark.asyncio
async def test_staff_with_no_housemaster_row_is_unrestricted(
    db_session: AsyncSession, school: School, academic_year: AcademicYear,
):
    _staff, user = await _make_housemaster_staff(db_session, school, "NONE")
    scope = await resolve_house_scope(user.id, school.id, academic_year.id, db_session)
    assert scope is None


@pytest.mark.asyncio
async def test_no_academic_year_is_unrestricted(
    db_session: AsyncSession, school: School,
):
    _staff, user = await _make_housemaster_staff(db_session, school, "NOYEAR")
    scope = await resolve_house_scope(user.id, school.id, None, db_session)
    assert scope is None


@pytest.mark.asyncio
async def test_active_housemaster_scoped_to_own_house_only(
    db_session: AsyncSession, school: School, academic_year: AcademicYear,
):
    staff, user = await _make_housemaster_staff(db_session, school, "OWN")
    house_a = await _make_house(db_session, school, "SCA")
    house_b = await _make_house(db_session, school, "SCB")
    db_session.add(HouseMaster(
        school_id=school.id, house_id=house_a.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    scope = await resolve_house_scope(user.id, school.id, academic_year.id, db_session)
    assert scope == {house_a.id}
    assert house_b.id not in scope


@pytest.mark.asyncio
async def test_inactive_housemaster_row_ignored(
    db_session: AsyncSession, school: School, academic_year: AcademicYear,
):
    staff, user = await _make_housemaster_staff(db_session, school, "INACTIVE")
    house = await _make_house(db_session, school, "SCI")
    db_session.add(HouseMaster(
        school_id=school.id, house_id=house.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=False,
    ))
    await db_session.flush()

    scope = await resolve_house_scope(user.id, school.id, academic_year.id, db_session)
    assert scope is None


@pytest.mark.asyncio
async def test_housemaster_row_for_different_year_ignored(
    db_session: AsyncSession, school: School, academic_year: AcademicYear,
):
    staff, user = await _make_housemaster_staff(db_session, school, "OTHERYEAR")
    house = await _make_house(db_session, school, "SCY")
    other_year = AcademicYear(
        school_id=school.id, name="2099/2100",
        start_date=date(2099, 9, 1), end_date=date(2100, 7, 31), is_current=False,
    )
    db_session.add(other_year)
    await db_session.flush()
    db_session.add(HouseMaster(
        school_id=school.id, house_id=house.id, staff_member_id=staff.id,
        academic_year_id=other_year.id, is_active=True,
    ))
    await db_session.flush()

    scope = await resolve_house_scope(user.id, school.id, academic_year.id, db_session)
    assert scope is None


@pytest.mark.asyncio
async def test_assert_house_in_scope_404s_for_other_house(
    db_session: AsyncSession, school: School, academic_year: AcademicYear,
):
    staff, user = await _make_housemaster_staff(db_session, school, "ASSERT404")
    house_a = await _make_house(db_session, school, "AS1")
    house_b = await _make_house(db_session, school, "AS2")
    db_session.add(HouseMaster(
        school_id=school.id, house_id=house_a.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    await assert_house_in_scope(house_a.id, user.id, school.id, academic_year.id, db_session)  # no raise
    with pytest.raises(HTTPException) as exc:
        await assert_house_in_scope(house_b.id, user.id, school.id, academic_year.id, db_session)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_assert_unrestricted_403s_for_scoped_housemaster(
    db_session: AsyncSession, school: School, academic_year: AcademicYear,
):
    staff, user = await _make_housemaster_staff(db_session, school, "UNRESTRICTED")
    house = await _make_house(db_session, school, "UR1")
    db_session.add(HouseMaster(
        school_id=school.id, house_id=house.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    with pytest.raises(HTTPException) as exc:
        await assert_unrestricted(user.id, school.id, academic_year.id, db_session, "nope")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_assert_unrestricted_allows_admin(
    db_session: AsyncSession, school: School, school_admin: User, academic_year: AcademicYear,
):
    await assert_unrestricted(school_admin.id, school.id, academic_year.id, db_session, "nope")  # no raise


# ── Integration: real endpoints, real HTTP layer ──────────────────────────────

async def _make_house_api(client: AsyncClient, auth: dict, code: str, gender: str = "MALE") -> dict:
    r = await client.post("/housing/houses", json={
        "name": f"Hall {code}", "code": code, "gender": gender,
    }, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


async def _make_student_api(client: AsyncClient, auth: dict, adm: str, gender: str = "MALE") -> dict:
    r = await client.post("/students", json={
        "admission_number": adm, "first_name": "Scope", "last_name": "Student", "gender": gender,
    }, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
async def test_list_houses_scoped_to_own_house(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, academic_year: AcademicYear, redis_permissions: None,
):
    house_a = await _make_house_api(client, auth, "INTA1")
    house_b = await _make_house_api(client, auth, "INTA2")
    staff, user = await _make_housemaster_staff(db_session, school, "LIST")
    db_session.add(HouseMaster(
        school_id=school.id, house_id=house_a["id"], staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()
    hm_auth = await _login(client, "hmscope-list@presec-test.edu.gh")

    r_mine = await client.get("/housing/houses/mine", headers=hm_auth)
    assert r_mine.status_code == 200
    ids = {h["id"] for h in r_mine.json()}
    assert ids == {house_a["id"]}

    r_all = await client.get("/housing/houses", headers=hm_auth)
    assert r_all.status_code == 200
    assert {h["id"] for h in r_all.json()} == {house_a["id"]}
    assert house_b["id"] not in {h["id"] for h in r_all.json()}


@pytest.mark.asyncio
async def test_get_and_update_house_404_for_other_house(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, academic_year: AcademicYear, redis_permissions: None,
):
    house_a = await _make_house_api(client, auth, "INTB1")
    house_b = await _make_house_api(client, auth, "INTB2")
    staff, _user = await _make_housemaster_staff(db_session, school, "GETUPD")
    db_session.add(HouseMaster(
        school_id=school.id, house_id=house_a["id"], staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()
    hm_auth = await _login(client, "hmscope-getupd@presec-test.edu.gh")

    ok = await client.get(f"/housing/houses/{house_a['id']}", headers=hm_auth)
    assert ok.status_code == 200
    blocked = await client.get(f"/housing/houses/{house_b['id']}", headers=hm_auth)
    assert blocked.status_code == 404

    patch_ok = await client.patch(f"/housing/houses/{house_a['id']}", json={"capacity": 40}, headers=hm_auth)
    assert patch_ok.status_code == 200
    patch_blocked = await client.patch(f"/housing/houses/{house_b['id']}", json={"capacity": 40}, headers=hm_auth)
    assert patch_blocked.status_code == 404


@pytest.mark.asyncio
async def test_create_house_403_for_scoped_housemaster(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, academic_year: AcademicYear, redis_permissions: None,
):
    house = await _make_house_api(client, auth, "INTC1")
    staff, _user = await _make_housemaster_staff(db_session, school, "CREATE")
    db_session.add(HouseMaster(
        school_id=school.id, house_id=house["id"], staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()
    hm_auth = await _login(client, "hmscope-create@presec-test.edu.gh")

    r = await client.post("/housing/houses", json={
        "name": "Rogue Hall", "code": "ROGUE1", "gender": "MALE",
    }, headers=hm_auth)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_assign_house_master_403_for_scoped_housemaster(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, academic_year: AcademicYear, redis_permissions: None,
):
    house_a = await _make_house_api(client, auth, "INTD1")
    house_b = await _make_house_api(client, auth, "INTD2")
    staff, _user = await _make_housemaster_staff(db_session, school, "ASSIGNHM")
    db_session.add(HouseMaster(
        school_id=school.id, house_id=house_a["id"], staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()
    hm_auth = await _login(client, "hmscope-assignhm@presec-test.edu.gh")

    r = await client.post(f"/housing/houses/{house_b['id']}/master", json={
        "staff_member_id": str(staff.id), "academic_year_id": str(academic_year.id),
    }, headers=hm_auth)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_rooms_and_house_students_scoped(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, academic_year: AcademicYear, redis_permissions: None,
):
    house_a = await _make_house_api(client, auth, "INTE1")
    house_b = await _make_house_api(client, auth, "INTE2")
    staff, _user = await _make_housemaster_staff(db_session, school, "ROOMS")
    db_session.add(HouseMaster(
        school_id=school.id, house_id=house_a["id"], staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()
    hm_auth = await _login(client, "hmscope-rooms@presec-test.edu.gh")

    ok_room = await client.post(f"/housing/houses/{house_a['id']}/rooms", json={"room_number": "1A"}, headers=hm_auth)
    assert ok_room.status_code == 201
    blocked_room = await client.post(f"/housing/houses/{house_b['id']}/rooms", json={"room_number": "1A"}, headers=hm_auth)
    assert blocked_room.status_code == 404

    ok_list = await client.get(f"/housing/houses/{house_a['id']}/students", headers=hm_auth)
    assert ok_list.status_code == 200
    blocked_list = await client.get(f"/housing/houses/{house_b['id']}/students", headers=hm_auth)
    assert blocked_list.status_code == 404


@pytest.mark.asyncio
async def test_assign_and_vacate_student_scoped(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, academic_year: AcademicYear, redis_permissions: None,
):
    house_a = await _make_house_api(client, auth, "INTF1")
    house_b = await _make_house_api(client, auth, "INTF2")
    staff, _user = await _make_housemaster_staff(db_session, school, "ASSIGNSTU")
    db_session.add(HouseMaster(
        school_id=school.id, house_id=house_a["id"], staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()
    hm_auth = await _login(client, "hmscope-assignstu@presec-test.edu.gh")

    s1 = await _make_student_api(client, auth, "SCOPESTU1")
    s2 = await _make_student_api(client, auth, "SCOPESTU2")

    ok = await client.post("/housing/assignments", json={
        "student_id": s1["id"], "house_id": house_a["id"],
        "academic_year_id": str(academic_year.id), "assigned_at": "2024-09-01",
    }, headers=hm_auth)
    assert ok.status_code == 201

    blocked = await client.post("/housing/assignments", json={
        "student_id": s2["id"], "house_id": house_b["id"],
        "academic_year_id": str(academic_year.id), "assigned_at": "2024-09-01",
    }, headers=hm_auth)
    assert blocked.status_code == 404

    # Vacate: own-house assignment succeeds, a different house's assignment 404s.
    other_house_assignment = await client.post("/housing/assignments", json={
        "student_id": s2["id"], "house_id": house_b["id"],
        "academic_year_id": str(academic_year.id), "assigned_at": "2024-09-01",
    }, headers=auth)
    assert other_house_assignment.status_code == 201

    own_vacate = await client.patch(
        f"/housing/assignments/{ok.json()['id']}/vacate", json={"vacated_at": "2024-12-01"}, headers=hm_auth,
    )
    assert own_vacate.status_code == 200
    blocked_vacate = await client.patch(
        f"/housing/assignments/{other_house_assignment.json()['id']}/vacate",
        json={"vacated_at": "2024-12-01"}, headers=hm_auth,
    )
    assert blocked_vacate.status_code == 404
