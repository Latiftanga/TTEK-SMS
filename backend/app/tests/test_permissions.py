"""
Permission editor (PUT /permissions/positions/{id}) fork-on-edit tests.

Most seeded positions (HEAD, TEACHER, HOD, ...) are shared platform
templates (school_id=NULL). Editing one used to mutate it in place —
silently changing what that position means for every school on the
platform, the same "shared row mutated by one tenant" bug already fixed
for Programmes. Editing a template now forks a school-owned copy instead,
migrating this school's own staff off the template onto the fork.

Run inside Docker: docker compose exec api pytest app/tests/test_permissions.py -v
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import AcademicYear, Class, ClassTeacher
from app.models.auth import LoginType, PositionPermission, StaffPosition, User
from app.models.school import GhanaDistrict, GhanaRegion, School, SchoolType
from app.models.staff import StaffMember, staff_member_positions


async def _other_school_auth(client: AsyncClient, db_session: AsyncSession) -> tuple[dict, School]:
    """Create a second school + superadmin and return their auth headers."""
    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    other_school = School(
        name="Other Test School", school_code="OTHER_PERM", school_type=SchoolType.SHS,
        region_id=region.id, district_id=district.id, is_active=True,
    )
    db_session.add(other_school)
    await db_session.flush()
    user = User(
        login_type=LoginType.EMAIL, email="other-admin-perm@test.gh",
        password_hash=hash_password("pw"), is_active=True,
        is_superadmin=True, school_id=other_school.id,
    )
    db_session.add(user)
    await db_session.flush()
    resp = await client.post("/auth/superadmin-login", json={
        "identifier": "other-admin-perm@test.gh", "password": "pw",
    })
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, other_school


def _entries(perms: dict[str, bool]) -> list[dict]:
    return [
        {"module": m, "action": a, "is_allowed": v}
        for (m, a), v in (
            (tuple(k.split(".", 1)), v) for k, v in perms.items()
        )
    ]


@pytest.mark.asyncio
async def test_editing_shared_template_forks_school_copy(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    template = await db_session.scalar(select(StaffPosition).where(
        StaffPosition.code == "TEACHER", StaffPosition.school_id.is_(None),
    ))
    assert template is not None, "Run seed_reference_data.py first"

    resp = await client.put(f"/permissions/positions/{template.id}", json={
        "permissions": _entries({"students.view": True, "students.edit": False}),
    }, headers=auth)
    assert resp.status_code == 200
    forked_id = resp.json()["id"]
    assert forked_id != str(template.id)
    assert resp.json()["school_id"] == str(school.id)

    # The shared template itself must be untouched.
    await db_session.refresh(template, attribute_names=["permissions"])
    template_perms = {(p.module, p.action): p.is_allowed for p in template.permissions}
    assert template_perms.get(("students", "edit")) is True


@pytest.mark.asyncio
async def test_editing_already_forked_position_reuses_it(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    template = await db_session.scalar(select(StaffPosition).where(
        StaffPosition.code == "TEACHER", StaffPosition.school_id.is_(None),
    ))
    first = await client.put(f"/permissions/positions/{template.id}", json={
        "permissions": _entries({"students.view": True}),
    }, headers=auth)
    forked_id = first.json()["id"]

    # Second edit, referencing the ORIGINAL template id again (e.g. a stale
    # client) — must reuse the existing fork, not create a second one.
    second = await client.put(f"/permissions/positions/{template.id}", json={
        "permissions": _entries({"students.view": True, "reports.view": True}),
    }, headers=auth)
    assert second.json()["id"] == forked_id

    all_forks = list(await db_session.scalars(
        select(StaffPosition).where(StaffPosition.code == "TEACHER", StaffPosition.school_id == school.id)
    ))
    assert len(all_forks) == 1


@pytest.mark.asyncio
async def test_existing_staff_migrated_to_fork_and_see_new_permissions(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions: None,
):
    template = await db_session.scalar(select(StaffPosition).where(
        StaffPosition.code == "TEACHER", StaffPosition.school_id.is_(None),
    ))

    staff_id = (await client.post("/staff", json={
        "staff_number": "PERM_T1", "first_name": "Perm", "last_name": "Teacher",
    }, headers=auth)).json()["id"]
    await client.patch(f"/staff/{staff_id}", json={"position_ids": [str(template.id)]}, headers=auth)

    db_session.add(User(
        school_id=school.id, login_type=LoginType.EMAIL, email="permteacher@presec-test.edu.gh",
        password_hash=hash_password("Whatever123!"), is_active=True, staff_member_id=staff_id,
    ))
    await db_session.flush()
    teacher_auth = {"Authorization": f"Bearer {(await client.post('/auth/login', json={
        'login_type': 'EMAIL', 'identifier': 'permteacher@presec-test.edu.gh', 'password': 'Whatever123!',
        'school_code': school.school_code,
    })).json()['access_token']}"}

    # Before the fork, the teacher can see students.
    resp = await client.get("/students", headers=teacher_auth)
    assert resp.status_code == 200

    # Admin revokes students.view entirely for this school's Teacher position.
    await client.put(f"/permissions/positions/{template.id}", json={
        "permissions": _entries({"students.edit": True}),  # students.view omitted = revoked
    }, headers=auth)

    row = await db_session.execute(
        select(staff_member_positions.c.position_id).where(
            staff_member_positions.c.staff_member_id == staff_id,
        )
    )
    migrated_position_id = row.scalar_one()
    assert str(migrated_position_id) != str(template.id)

    resp = await client.get("/students", headers=teacher_auth)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cross_school_forks_are_independent(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    """The literal 'school-a offers only X, school-b offers everything' shape
    already used for Programme adoption (12ag) — applied here to positions."""
    template = await db_session.scalar(select(StaffPosition).where(
        StaffPosition.code == "TEACHER", StaffPosition.school_id.is_(None),
    ))
    other_auth, other_school = await _other_school_auth(client, db_session)

    await client.put(f"/permissions/positions/{template.id}", json={
        "permissions": _entries({"students.view": True}),
    }, headers=auth)
    await client.put(f"/permissions/positions/{template.id}", json={
        "permissions": _entries({"students.view": True, "students.edit": True, "students.create": True}),
    }, headers=other_auth)

    my_fork = await db_session.scalar(select(StaffPosition).where(
        StaffPosition.code == "TEACHER", StaffPosition.school_id == school.id,
    ))
    await db_session.refresh(my_fork, attribute_names=["permissions"])
    my_perms = {(p.module, p.action) for p in my_fork.permissions if p.is_allowed}
    assert ("students", "edit") not in my_perms

    other_fork = await db_session.scalar(select(StaffPosition).where(
        StaffPosition.code == "TEACHER", StaffPosition.school_id == other_school.id,
    ))
    await db_session.refresh(other_fork, attribute_names=["permissions"])
    other_perms = {(p.module, p.action) for p in other_fork.permissions if p.is_allowed}
    assert ("students", "edit") in other_perms

    # And the shared template is still exactly as seeded, untouched by either.
    await db_session.refresh(template, attribute_names=["permissions"])
    template_perms = {(p.module, p.action): p.is_allowed for p in template.permissions}
    assert template_perms.get(("students", "edit")) is True


@pytest.mark.asyncio
async def test_class_teacher_fork_does_not_leak_to_other_school(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, redis_permissions: None,
):
    """Auto-derived positions (CLASS_TEACHER) must resolve the same
    school-specific-wins rule as manually-assigned ones — otherwise a fork
    would only ever add to the template instead of replacing it, and a
    different school's fork of the same code would leak in."""
    ct_template = await db_session.scalar(select(StaffPosition).where(
        StaffPosition.code == "CLASS_TEACHER", StaffPosition.school_id.is_(None),
    ))
    other_auth, other_school = await _other_school_auth(client, db_session)

    # This school forks CLASS_TEACHER down to a narrow set (no fees.view).
    await client.put(f"/permissions/positions/{ct_template.id}", json={
        "permissions": _entries({"students.view": True}),
    }, headers=auth)

    staff = StaffMember(
        school_id=school.id, staff_number="PERM_CT1", first_name="Perm", last_name="ClassTeacher", is_active=True,
    )
    db_session.add(staff)
    await db_session.flush()
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    db_session.add(User(
        school_id=school.id, login_type=LoginType.EMAIL, email="permct@presec-test.edu.gh",
        password_hash=hash_password("Whatever123!"), is_active=True, staff_member_id=staff.id,
    ))
    await db_session.flush()
    ct_auth = {"Authorization": f"Bearer {(await client.post('/auth/login', json={
        'login_type': 'EMAIL', 'identifier': 'permct@presec-test.edu.gh', 'password': 'Whatever123!',
        'school_code': school.school_code,
    })).json()['access_token']}"}

    # fees.view was on the original CLASS_TEACHER template but not re-granted
    # in this school's fork — the derived staff member should NOT have it
    # (would fail if the union incorrectly included the untouched template).
    resp = await client.get("/fees/types", headers=ct_auth)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_resolve_permissions_ignores_directly_assigned_cross_school_position(
    db_session: AsyncSession, school: School, redis_permissions,
):
    """Defense in depth for resolve_permissions()'s Layer 2 lookup: even if a
    staff_member_positions row somehow links a staff member to a *different*
    school's own position (the write path now blocks this at assignment time
    — services/staff.py::_assert_positions_owned — this covers any stray or
    historical row bypassing that), the resolved permission map must not
    include that other school's grants. Inserted directly via the DB rather
    than through POST/PATCH /staff, which now reject this outright — this
    test is about the resolution layer, not the write guard."""
    from app.core.permissions import resolve_permissions

    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    other_school = School(
        name="Other Resolve School", school_code="OTHER_RESOLVE", school_type=SchoolType.SHS,
        region_id=region.id, district_id=district.id, is_active=True,
    )
    db_session.add(other_school)
    await db_session.flush()

    other_pos = StaffPosition(
        code="CUSTOM_ADMIN", name="Custom Admin", school_id=other_school.id, is_template=False,
    )
    db_session.add(other_pos)
    await db_session.flush()
    db_session.add(PositionPermission(
        position_id=other_pos.id, module="staff", action="delete", is_allowed=True,
    ))

    staff = StaffMember(
        school_id=school.id, staff_number="PERM_XSCHOOL", first_name="Perm", last_name="Cross", is_active=True,
    )
    db_session.add(staff)
    await db_session.flush()
    await db_session.execute(
        staff_member_positions.insert().values(staff_member_id=staff.id, position_id=other_pos.id)
    )
    await db_session.flush()

    perms = await resolve_permissions(staff.id, db_session)
    assert perms.get("staff.delete") is not True
