"""
Dashboard tests — teacher and housemaster views.

A staff member can be ClassTeacher for more than one class in the same year
(nothing in the schema prevents it — only one class teacher per class, not
one class per class teacher), so my_classes is a list, not a single class.
Same shape of bug for HouseMaster: assign_house_master() never checks
whether the incoming staff member already runs a different house, so
my_houses is a list too.

Run inside Docker: docker compose exec api pytest app/tests/test_dashboard.py -v
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import AcademicTerm, AcademicYear, Class, ClassTeacher
from app.models.auth import LoginType, StaffPosition, User
from app.models.housing import House, HouseGender, HouseMaster
from app.models.school import School
from app.models.staff import StaffMember


async def _teacher_login(
    client: AsyncClient, db_session: AsyncSession, school: School, staff: StaffMember,
) -> dict:
    """A staff member with no StaffPosition/permissions at all falls through
    get_dashboard()'s permission checks straight to teacher_view()."""
    email = f"{staff.staff_number.lower()}@presec-test.edu.gh"
    db_session.add(User(
        school_id=school.id, login_type=LoginType.EMAIL, email=email,
        password_hash=hash_password("Whatever123!"), is_active=True, staff_member_id=staff.id,
    ))
    await db_session.flush()
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL", "identifier": email, "password": "Whatever123!",
        "school_code": school.school_code,
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _login_as_housemaster(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
) -> tuple[dict, StaffMember]:
    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == "HOUSEMASTER"))
    assert pos is not None, "Run seed_reference_data.py first"

    staff_id = (await client.post("/staff", json={
        "staff_number": "TST-HOUSEMASTER", "first_name": "Test", "last_name": "Housemaster",
    }, headers=auth)).json()["id"]
    await client.patch(f"/staff/{staff_id}", json={"position_ids": [str(pos.id)]}, headers=auth)

    email = "housemaster@presec-test.edu.gh"
    db_session.add(User(
        school_id=school.id, login_type=LoginType.EMAIL, email=email,
        password_hash=hash_password("Whatever123!"), is_active=True, staff_member_id=staff_id,
    ))
    await db_session.flush()

    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL", "identifier": email, "password": "Whatever123!",
        "school_code": school.school_code,
    })
    assert resp.status_code == 200, resp.text
    staff = await db_session.get(StaffMember, staff_id)
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, staff


@pytest.mark.asyncio
async def test_teacher_dashboard_no_class(
    client: AsyncClient, db_session: AsyncSession, school: School,
    staff_member: StaffMember, academic_term: AcademicTerm, redis_permissions: None,
):
    auth = await _teacher_login(client, db_session, school, staff_member)
    resp = await client.get("/dashboard", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["view"] == "teacher"
    assert data["my_classes"] == []


@pytest.mark.asyncio
async def test_teacher_dashboard_multiple_classes(
    client: AsyncClient, db_session: AsyncSession, school: School, staff_member: StaffMember,
    academic_year: AcademicYear, academic_term: AcademicTerm, school_class: Class,
    redis_permissions: None,
):
    second_class = Class(school_id=school.id, level="SHS", year_group=1, stream="B", is_active=True)
    db_session.add(second_class)
    await db_session.flush()

    for cls in (school_class, second_class):
        db_session.add(ClassTeacher(
            school_id=school.id, class_id=cls.id, staff_member_id=staff_member.id,
            academic_year_id=academic_year.id, is_active=True,
        ))
    await db_session.flush()

    auth = await _teacher_login(client, db_session, school, staff_member)
    resp = await client.get("/dashboard", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["view"] == "teacher"
    assert len(data["my_classes"]) == 2
    assert {c["id"] for c in data["my_classes"]} == {str(school_class.id), str(second_class.id)}


@pytest.mark.asyncio
async def test_housemaster_dashboard_no_house(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions: None,
):
    hm_auth, _ = await _login_as_housemaster(client, auth, db_session, school)
    resp = await client.get("/dashboard", headers=hm_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["view"] == "housemaster"
    assert data["my_houses"] == []


@pytest.mark.asyncio
async def test_housemaster_dashboard_multiple_houses(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, redis_permissions: None,
):
    house_a = House(school_id=school.id, name="Ashanti House", code="ASH", gender=HouseGender.MIXED)
    house_b = House(school_id=school.id, name="Volta House", code="VOL", gender=HouseGender.MIXED)
    db_session.add_all([house_a, house_b])
    await db_session.flush()

    hm_auth, staff = await _login_as_housemaster(client, auth, db_session, school)

    for house in (house_a, house_b):
        db_session.add(HouseMaster(
            school_id=school.id, house_id=house.id, staff_member_id=staff.id,
            academic_year_id=academic_year.id, is_active=True,
        ))
    await db_session.flush()

    resp = await client.get("/dashboard", headers=hm_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["view"] == "housemaster"
    assert len(data["my_houses"]) == 2
    assert {h["id"] for h in data["my_houses"]} == {str(house_a.id), str(house_b.id)}


# ── Multi-role: is_class_teacher + other_roles ───────────────────────────────
# A staff member can genuinely hold several responsibilities at once (the
# reported case: Class Teacher who's then also appointed Housemaster) — the
# view cascade above only ever returns ONE full view by seniority, so these
# two fields are what let the rest of the app (nav) and the dashboard itself
# (the "you also..." strip) stay correct regardless of which view won.

@pytest.mark.asyncio
async def test_housemaster_who_is_also_class_teacher_keeps_teacher_badge(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, academic_term: AcademicTerm, school_class: Class, redis_permissions: None,
):
    """housing.manage outranks the plain teacher fallback in the cascade, so
    'housemaster' stays the primary view — but is_class_teacher must still
    be true (nav correctness) and other_roles must surface the Class
    Teacher responsibility the primary housemaster view doesn't cover."""
    house = House(school_id=school.id, name="Eastern House", code="EAS", gender=HouseGender.MIXED)
    db_session.add(house)
    await db_session.flush()

    hm_auth, staff = await _login_as_housemaster(client, auth, db_session, school)

    db_session.add(HouseMaster(
        school_id=school.id, house_id=house.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.get("/dashboard", headers=hm_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["view"] == "housemaster"
    assert data["is_class_teacher"] is True
    teacher_badges = [r for r in data["other_roles"] if r["role"] == "teacher"]
    assert len(teacher_badges) == 1
    assert "1 class" in teacher_badges[0]["detail"]


@pytest.mark.asyncio
async def test_plain_teacher_dashboard_has_no_other_roles(
    client: AsyncClient, db_session: AsyncSession, school: School,
    staff_member: StaffMember, academic_year: AcademicYear, academic_term: AcademicTerm,
    school_class: Class, redis_permissions: None,
):
    """The common case (one responsibility, no housing/finance/approval
    role) must not show a pointless empty 'you also...' strip."""
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_member.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    auth = await _teacher_login(client, db_session, school, staff_member)
    resp = await client.get("/dashboard", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["view"] == "teacher"
    assert data["is_class_teacher"] is True
    assert data["other_roles"] == []
