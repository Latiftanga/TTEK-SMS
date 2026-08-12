"""
Staff profile integration tests.
Run inside Docker: docker compose exec api pytest app/tests/test_staff.py -v

Fixtures (school, school_admin, auth) come from conftest.py.
"""
import io
import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
import pytest_asyncio

from app.core.auth import hash_password
from app.models.academic import AcademicYear, Class, ClassTeacher
from app.models.auth import AuditLog, LoginType, StaffPermission, StaffPosition, User
from app.models.school import GhanaDistrict, GhanaRegion, School, SchoolType
from app.models.staff import StaffCategory, StaffMember, StaffRank, StaffType
from sqlalchemy import select


def _tiny_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="blue").save(buf, format="PNG")
    return buf.getvalue()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_position_id(db_session: AsyncSession) -> str:
    """Return the id of any seeded staff position."""
    pos = await db_session.scalar(select(StaffPosition).limit(1))
    assert pos is not None, "Run seed_reference_data.py first"
    return str(pos.id)


async def _get_head_position_id(db_session: AsyncSession) -> str:
    """Return the id of the seeded HEAD position (grants school.manage_users)."""
    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == "HEAD"))
    assert pos is not None, "Run seed_reference_data.py first"
    return str(pos.id)


async def _other_school_position_id(db_session: AsyncSession) -> str:
    """Create a second school and a position it owns (school_id set, not a
    shared template) — mirrors a real school's own forked position
    (routers/permissions.py's fork-on-edit). Returns the position id."""
    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    other_school = School(
        name="Other Test School", school_code="OTHER_STAFF", school_type=SchoolType.SHS,
        region_id=region.id, district_id=district.id, is_active=True,
    )
    db_session.add(other_school)
    await db_session.flush()
    pos = StaffPosition(code="CUSTOM_HOD", name="Custom HOD", school_id=other_school.id, is_template=False)
    db_session.add(pos)
    await db_session.flush()
    return str(pos.id)


async def _seed_rank(db_session: AsyncSession) -> tuple[str, str]:
    """Create a template category + rank and return (category_id, rank_id)."""
    cat = await db_session.scalar(
        select(StaffCategory).where(StaffCategory.code == "TEACHING", StaffCategory.school_id.is_(None))
    )
    if not cat:
        cat = StaffCategory(
            school_id=None, name="Teaching Staff", code="TEACHING",
            staff_type=StaffType.TEACHING, is_template=True, is_active=True,
        )
        db_session.add(cat)
        await db_session.flush()

    rank = await db_session.scalar(
        select(StaffRank).where(StaffRank.category_id == cat.id, StaffRank.title == "Superintendent I")
    )
    if not rank:
        rank = StaffRank(
            school_id=None, category_id=cat.id, title="Superintendent I",
            is_template=True, is_active=True,
        )
        db_session.add(rank)
        await db_session.flush()
    return str(cat.id), str(rank.id)


async def _other_school_rank(db_session: AsyncSession) -> tuple[str, str]:
    """Create a second school with its own PRIVATE (non-template) category +
    rank — mirrors _other_school_position_id, for testing the cross-school
    ownership gap fixed in staff_category.py/staff_leave.py. Returns
    (category_id, rank_id)."""
    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    other_school = School(
        name="Other Rank School", school_code="OTHER_RANK", school_type=SchoolType.SHS,
        region_id=region.id, district_id=district.id, is_active=True,
    )
    db_session.add(other_school)
    await db_session.flush()
    cat = StaffCategory(
        school_id=other_school.id, name="Foreign Category", code="FOREIGNCAT",
        staff_type=StaffType.TEACHING, is_template=False, is_active=True,
    )
    db_session.add(cat)
    await db_session.flush()
    rank = StaffRank(
        school_id=other_school.id, category_id=cat.id, title="Foreign Rank",
        is_template=False, is_active=True,
    )
    db_session.add(rank)
    await db_session.flush()
    return str(cat.id), str(rank.id)


def _staff_payload(**overrides) -> dict:
    base = {
        "staff_number": "TST001",
        "first_name": "Kwame",
        "last_name": "Mensah",
    }
    return {**base, **overrides}


async def _login_as_teacher_no_edit(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
) -> tuple[dict, str]:
    """Create a real staff login holding TEACHER — which grants no staff.*
    permission at all (reference_data.py) — to prove self-service photo
    upload works without staff.edit, while acting on someone else's photo
    still requires it. Returns (auth headers, own staff_id)."""
    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == "TEACHER"))
    assert pos is not None, "Run seed_reference_data.py first"

    staff_id = (await client.post("/staff", json=_staff_payload(staff_number="TCH-NOEDIT"), headers=auth)).json()["id"]
    await client.patch(f"/staff/{staff_id}", json={"position_ids": [str(pos.id)]}, headers=auth)

    email = "teacher-noedit@presec-test.edu.gh"
    db_session.add(User(
        school_id=school.id, login_type=LoginType.EMAIL, email=email,
        password_hash=hash_password("Whatever123!"), is_active=True, staff_member_id=staff_id,
    ))
    await db_session.flush()
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL", "identifier": email, "password": "Whatever123!",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, staff_id


async def _login_as_position(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, position_code: str,
) -> tuple[dict, str]:
    """Create a real staff login holding `position_code`. Returns (auth headers, staff_id)."""
    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == position_code))
    assert pos is not None, "Run seed_reference_data.py first"

    staff_id = (await client.post("/staff", json=_staff_payload(
        staff_number=f"TST-{position_code}",
    ), headers=auth)).json()["id"]
    await client.patch(f"/staff/{staff_id}", json={"position_ids": [str(pos.id)]}, headers=auth)

    email = f"{position_code.lower()}@presec-test.edu.gh"
    db_session.add(User(
        school_id=school.id, login_type=LoginType.EMAIL, email=email,
        password_hash=hash_password("Whatever123!"), is_active=True, staff_member_id=staff_id,
    ))
    await db_session.flush()
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL", "identifier": email, "password": "Whatever123!",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, staff_id


# ── Staff CRUD ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_staff_member(client: AsyncClient, auth: dict):
    resp = await client.post("/staff", json=_staff_payload(), headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["staff_number"] == "TST001"
    assert data["display_name"] == "Kwame Mensah"
    assert data["qualifications"] == []
    assert data["emergency_contacts"] == []


@pytest.mark.asyncio
async def test_create_staff_with_middle_name(client: AsyncClient, auth: dict):
    resp = await client.post("/staff", json=_staff_payload(
        middle_name="Adu", gender="MALE"
    ), headers=auth)
    assert resp.status_code == 201
    assert resp.json()["display_name"] == "Kwame Adu Mensah"


@pytest.mark.asyncio
async def test_staff_number_unique_per_school(client: AsyncClient, auth: dict):
    await client.post("/staff", json=_staff_payload(), headers=auth)
    resp = await client.post("/staff", json=_staff_payload(), headers=auth)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_staff(client: AsyncClient, auth: dict):
    await client.post("/staff", json=_staff_payload(staff_number="TST001"), headers=auth)
    await client.post("/staff", json=_staff_payload(staff_number="TST002", last_name="Asante"), headers=auth)

    resp = await client.get("/staff", headers=auth)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_staff_detail(client: AsyncClient, auth: dict):
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    resp = await client.get(f"/staff/{staff_id}", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == staff_id
    assert "qualifications" in data
    assert "emergency_contacts" in data


@pytest.mark.asyncio
async def test_update_staff(client: AsyncClient, auth: dict, db_session: AsyncSession):
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    pos_id = await _get_position_id(db_session)
    resp = await client.patch(f"/staff/{staff_id}", json={"position_ids": [pos_id]}, headers=auth)
    assert resp.status_code == 200
    assert pos_id in resp.json()["position_ids"]


@pytest.mark.asyncio
async def test_create_staff_rejects_cross_school_position(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
):
    """A position belonging to a *different* school must never be assignable
    — resolve_permissions() unions purely by position_id with no school
    check of its own, so this would otherwise directly grant that other
    school's exact permission set."""
    other_pos_id = await _other_school_position_id(db_session)
    resp = await client.post("/staff", json={
        **_staff_payload(staff_number="TSTXSCHOOL"), "position_ids": [other_pos_id],
    }, headers=auth)
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_update_staff_rejects_cross_school_position(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
):
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    other_pos_id = await _other_school_position_id(db_session)
    resp = await client.patch(f"/staff/{staff_id}", json={"position_ids": [other_pos_id]}, headers=auth)
    assert resp.status_code == 404, resp.text

    # Confirm nothing was actually linked.
    detail = (await client.get(f"/staff/{staff_id}", headers=auth)).json()
    assert other_pos_id not in detail["position_ids"]


@pytest.mark.asyncio
async def test_deactivate_staff(client: AsyncClient, auth: dict):
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    await client.patch(f"/staff/{staff_id}", json={"is_active": False}, headers=auth)

    # Should not appear in active-only list
    active_list = (await client.get("/staff", headers=auth)).json()
    assert all(m["id"] != staff_id for m in active_list)

    # Should appear when including inactive
    all_list = (await client.get("/staff?active_only=false", headers=auth)).json()
    assert any(m["id"] == staff_id for m in all_list)


@pytest.mark.asyncio
async def test_deactivate_staff_disables_linked_user_login(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    user = User(
        school_id=school.id, login_type=LoginType.EMAIL, email="deactivate-target@example.com",
        password_hash=hash_password("Whatever123!"), is_active=True, staff_member_id=staff_id,
    )
    db_session.add(user)
    await db_session.flush()

    resp = await client.patch(f"/staff/{staff_id}", json={"is_active": False}, headers=auth)
    assert resp.status_code == 200
    await db_session.refresh(user)
    assert user.is_active is False

    # Reactivating restores login access.
    resp = await client.patch(f"/staff/{staff_id}", json={"is_active": True}, headers=auth)
    assert resp.status_code == 200
    await db_session.refresh(user)
    assert user.is_active is True


@pytest.mark.asyncio
async def test_deactivate_staff_cascades_to_class_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school_class: Class, academic_year: AcademicYear,
):
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    assign_resp = await client.post(f"/academic/classes/{school_class.id}/class-teacher", json={
        "staff_member_id": staff_id, "academic_year_id": str(academic_year.id),
    }, headers=auth)
    assert assign_resp.status_code == 201

    resp = await client.patch(f"/staff/{staff_id}", json={"is_active": False}, headers=auth)
    assert resp.status_code == 200

    ct = await db_session.scalar(
        select(ClassTeacher).where(ClassTeacher.staff_member_id == staff_id)
    )
    assert ct.is_active is False


@pytest.mark.asyncio
async def test_deactivate_last_admin_rejected(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
):
    head_pos_id = await _get_head_position_id(db_session)
    staff_id = (await client.post("/staff", json=_staff_payload(staff_number="TSTHEAD"), headers=auth)).json()["id"]
    await client.patch(f"/staff/{staff_id}", json={"position_ids": [head_pos_id]}, headers=auth)

    resp = await client.patch(f"/staff/{staff_id}", json={"is_active": False}, headers=auth)
    assert resp.status_code == 422


# ── Emergency contacts ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_and_delete_emergency_contact(client: AsyncClient, auth: dict):
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]

    resp = await client.post(f"/staff/{staff_id}/emergency-contacts", json={
        "name": "Akosua Mensah", "contact_type": "Spouse", "phone": "0241234567",
    }, headers=auth)
    assert resp.status_code == 201
    contact_id = resp.json()["id"]

    detail = (await client.get(f"/staff/{staff_id}", headers=auth)).json()
    assert len(detail["emergency_contacts"]) == 1

    await client.delete(f"/staff/{staff_id}/emergency-contacts/{contact_id}", headers=auth)
    detail = (await client.get(f"/staff/{staff_id}", headers=auth)).json()
    assert len(detail["emergency_contacts"]) == 0


# ── Qualifications ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_and_delete_qualification(client: AsyncClient, auth: dict):
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]

    resp = await client.post(f"/staff/{staff_id}/qualifications", json={
        "institution": "University of Ghana",
        "qualification_type": "Bachelor of Education",
        "field_of_study": "Mathematics",
        "year_obtained": 2015,
    }, headers=auth)
    assert resp.status_code == 201
    qual_id = resp.json()["id"]

    detail = (await client.get(f"/staff/{staff_id}", headers=auth)).json()
    assert len(detail["qualifications"]) == 1
    assert detail["qualifications"][0]["institution"] == "University of Ghana"

    await client.delete(f"/staff/{staff_id}/qualifications/{qual_id}", headers=auth)
    detail = (await client.get(f"/staff/{staff_id}", headers=auth)).json()
    assert len(detail["qualifications"]) == 0


# ── Promotions ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_promotion(
    client: AsyncClient, auth: dict, db_session: AsyncSession
):
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    _, rank_id = await _seed_rank(db_session)

    resp = await client.post(f"/staff/{staff_id}/promotions", json={
        "to_rank_id": rank_id,
        "effective_date": "2024-01-15",
        "reason": "Annual review",
    }, headers=auth)
    assert resp.status_code == 201
    promo = resp.json()
    assert promo["to_rank_title"] == "Superintendent I"
    assert promo["from_rank_id"] is None
    assert promo["reason"] == "Annual review"


@pytest.mark.asyncio
async def test_promotion_invalid_rank(client: AsyncClient, auth: dict):
    """Promotion with non-existent to_rank_id must 404."""
    import uuid
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    resp = await client.post(f"/staff/{staff_id}/promotions", json={
        "to_rank_id": str(uuid.uuid4()),
        "effective_date": "2024-01-15",
    }, headers=auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_record_promotion_rejects_cross_school_to_rank(
    client: AsyncClient, auth: dict, db_session: AsyncSession
):
    """to_rank_id referencing a different school's private rank must 404 —
    without this, a promotion could silently reference another school's
    private StaffRank."""
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    _, foreign_rank_id = await _other_school_rank(db_session)

    resp = await client.post(f"/staff/{staff_id}/promotions", json={
        "to_rank_id": foreign_rank_id,
        "effective_date": "2024-01-15",
    }, headers=auth)
    assert resp.status_code == 404

    list_resp = await client.get(f"/staff/{staff_id}/promotions", headers=auth)
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_record_promotion_rejects_cross_school_from_rank(
    client: AsyncClient, auth: dict, db_session: AsyncSession
):
    """from_rank_id referencing a different school's private rank must 404,
    even when to_rank_id is a valid shared template."""
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    _, own_rank_id = await _seed_rank(db_session)
    _, foreign_rank_id = await _other_school_rank(db_session)

    resp = await client.post(f"/staff/{staff_id}/promotions", json={
        "from_rank_id": foreign_rank_id,
        "to_rank_id": own_rank_id,
        "effective_date": "2024-01-15",
    }, headers=auth)
    assert resp.status_code == 404

    list_resp = await client.get(f"/staff/{staff_id}/promotions", headers=auth)
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_update_promotion_rejects_cross_school_rank(
    client: AsyncClient, auth: dict, db_session: AsyncSession
):
    """PATCH on an existing promotion with a cross-school to_rank_id must
    404 and leave the promotion's own rank unchanged."""
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    _, own_rank_id = await _seed_rank(db_session)
    _, foreign_rank_id = await _other_school_rank(db_session)

    create_resp = await client.post(f"/staff/{staff_id}/promotions", json={
        "to_rank_id": own_rank_id,
        "effective_date": "2024-01-15",
    }, headers=auth)
    promotion_id = create_resp.json()["id"]

    resp = await client.patch(f"/staff/{staff_id}/promotions/{promotion_id}", json={
        "to_rank_id": foreign_rank_id,
    }, headers=auth)
    assert resp.status_code == 404

    list_resp = await client.get(f"/staff/{staff_id}/promotions", headers=auth)
    assert list_resp.json()[0]["to_rank_id"] == own_rank_id


@pytest.mark.asyncio
async def test_list_promotions(client: AsyncClient, auth: dict, db_session: AsyncSession):
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    _, rank_id = await _seed_rank(db_session)
    await client.post(f"/staff/{staff_id}/promotions", json={
        "to_rank_id": rank_id,
        "effective_date": "2024-01-15",
    }, headers=auth)

    resp = await client.get(f"/staff/{staff_id}/promotions", headers=auth)
    assert resp.status_code == 200
    promos = resp.json()
    assert len(promos) == 1
    assert promos[0]["to_rank_title"] == "Superintendent I"


# ── Categories & Ranks ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_rank_rejects_cross_school_category(
    client: AsyncClient, auth: dict, db_session: AsyncSession
):
    """POST /staff/ranks with category_id from a different school's private
    category must 404, not silently create a rank under it."""
    foreign_category_id, _ = await _other_school_rank(db_session)

    resp = await client.post("/staff/ranks", json={
        "category_id": foreign_category_id,
        "title": "Leaked Rank",
    }, headers=auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_ranks_rejects_cross_school_category(
    client: AsyncClient, auth: dict, db_session: AsyncSession
):
    """GET /staff/ranks?category_id=<other school's private category> must
    404 rather than silently returning that other school's ranks."""
    foreign_category_id, _ = await _other_school_rank(db_session)

    resp = await client.get(
        "/staff/ranks", params={"category_id": foreign_category_id}, headers=auth
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_rank_allowed_for_own_category(
    client: AsyncClient, auth: dict, db_session: AsyncSession
):
    category_id, _ = await _seed_rank(db_session)
    resp = await client.post("/staff/ranks", json={
        "category_id": category_id,
        "title": "Brand New Title",
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["title"] == "Brand New Title"


# ── Leave ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_and_approve_leave(client: AsyncClient, auth: dict):
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]

    leave_resp = await client.post(f"/staff/{staff_id}/leave", json={
        "leave_type": "Annual",
        "start_date": "2025-08-04",
        "end_date": "2025-08-08",
        "days_count": 5,
        "reason": "Family vacation",
    }, headers=auth)
    assert leave_resp.status_code == 201
    leave_id = leave_resp.json()["id"]
    assert leave_resp.json()["status"] == "PENDING"

    # Approve it
    resp = await client.patch(f"/staff/leave/{leave_id}/review",
        json={"status": "APPROVED", "notes": "Approved by headmaster"},
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_double_review_rejected(client: AsyncClient, auth: dict):
    """Reviewing an already-reviewed leave must return 409."""
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    leave_id = (await client.post(f"/staff/{staff_id}/leave", json={
        "leave_type": "Sick", "start_date": "2025-08-04",
        "end_date": "2025-08-05", "days_count": 2,
    }, headers=auth)).json()["id"]

    await client.patch(f"/staff/leave/{leave_id}/review", json={"status": "REJECTED"}, headers=auth)
    resp = await client.patch(f"/staff/leave/{leave_id}/review", json={"status": "APPROVED"}, headers=auth)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_pending_leave_enriched_with_staff_name(client: AsyncClient, auth: dict):
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    await client.post(f"/staff/{staff_id}/leave", json={
        "leave_type": "Annual", "start_date": "2025-08-04",
        "end_date": "2025-08-08", "days_count": 5,
    }, headers=auth)

    resp = await client.get("/staff/leave/pending", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["staff_member_id"] == staff_id
    assert data[0]["staff_name"] == "Kwame Mensah"
    assert data[0]["staff_number"] == "TST001"


# ── List pagination ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_staff_total_count_and_search(client: AsyncClient, auth: dict):
    await client.post("/staff", json=_staff_payload(staff_number="TST101", last_name="Mensah"), headers=auth)
    await client.post("/staff", json=_staff_payload(staff_number="TST102", last_name="Asante"), headers=auth)
    await client.post("/staff", json=_staff_payload(staff_number="TST103", last_name="Asante"), headers=auth)

    resp = await client.get("/staff?limit=1", headers=auth)
    assert len(resp.json()) == 1
    assert resp.headers["x-total-count"] == "3"

    resp = await client.get("/staff?search=asante", headers=auth)
    assert resp.headers["x-total-count"] == "2"
    assert all(m["last_name"] == "Asante" for m in resp.json())


@pytest.mark.asyncio
async def test_list_staff_search_matches_position_name(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
):
    """Search must match a staff member's position name, not just name/staff
    number — the search box is advertised as 'Search name, ID, or position…'."""
    bursar_pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == "BURSAR"))
    assert bursar_pos is not None, "Run seed_reference_data.py first"

    staff_id = (await client.post(
        "/staff", json=_staff_payload(staff_number="TST201", last_name="Owusu"), headers=auth,
    )).json()["id"]
    await client.patch(f"/staff/{staff_id}", json={"position_ids": [str(bursar_pos.id)]}, headers=auth)
    await client.post("/staff", json=_staff_payload(staff_number="TST202", last_name="Boateng"), headers=auth)

    resp = await client.get("/staff?search=bursar", headers=auth)
    assert resp.status_code == 200
    assert resp.headers["x-total-count"] == "1"
    assert resp.json()[0]["id"] == staff_id


@pytest.mark.asyncio
async def test_list_staff_category_filter(client: AsyncClient, auth: dict, db_session: AsyncSession):
    cat_id, _ = await _seed_rank(db_session)
    await client.post("/staff", json=_staff_payload(staff_number="TST201", category_id=cat_id), headers=auth)
    await client.post("/staff", json=_staff_payload(staff_number="TST202"), headers=auth)

    resp = await client.get(f"/staff?category_id={cat_id}", headers=auth)
    assert resp.headers["x-total-count"] == "1"
    assert resp.json()[0]["staff_number"] == "TST201"


# ── Personal permission overrides ────────────────────────────────────────────

async def _other_school_staff(db_session: AsyncSession) -> StaffMember:
    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    other_school = School(
        name="Other Test School", school_code="OTHERSCH",
        school_type=SchoolType.SHS,
        region_id=region.id, district_id=district.id, is_active=True,
    )
    db_session.add(other_school)
    await db_session.flush()
    staff = StaffMember(
        school_id=other_school.id, staff_number="OTH001",
        first_name="Foreign", last_name="Staff", is_active=True,
    )
    db_session.add(staff)
    await db_session.flush()
    return staff


@pytest.mark.asyncio
async def test_staff_permissions_reject_cross_school_read(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
):
    other_staff = await _other_school_staff(db_session)
    resp = await client.get(f"/staff/{other_staff.id}/permissions", headers=auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_staff_permissions_reject_cross_school_write(
    client: AsyncClient, auth: dict, db_session: AsyncSession, redis_permissions,
):
    """A caller with school.manage_users at one school must not be able to
    grant a permission override to a staff member at a different school —
    resolve_permissions() applies overrides by staff_member_id alone, so an
    unguarded write here would silently change a real staff member's live
    permissions at another school."""
    other_staff = await _other_school_staff(db_session)
    resp = await client.post(f"/staff/{other_staff.id}/permissions", json={
        "module": "fees", "action": "manage", "is_allowed": True,
    }, headers=auth)
    assert resp.status_code == 404

    from app.core.permissions import resolve_permissions
    perms = await resolve_permissions(other_staff.id, db_session)
    assert perms.get("fees.manage", False) is False


@pytest.mark.asyncio
async def test_staff_permissions_reject_cross_school_clear(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
):
    other_staff = await _other_school_staff(db_session)
    resp = await client.delete(f"/staff/{other_staff.id}/permissions/fees/manage", headers=auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_set_permission_rejects_unknown_module_action(
    client: AsyncClient, auth: dict, redis_permissions,
):
    """An unrecognised module/action pair must 422, not silently persist —
    resolve_permissions() would never match it against any real permission,
    so a caller would otherwise get no sign their override never took effect."""
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    resp = await client.post(f"/staff/{staff_id}/permissions", json={
        "module": "fees", "action": "not_a_real_action", "is_allowed": True,
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_permission_catalogue_includes_record_behaviour_and_documents(
    client: AsyncClient, auth: dict,
):
    """assessments.record_behaviour and the documents module must appear in
    the returned catalogue and be settable — both were silently absent from
    the old hand-maintained ALL_PERMISSIONS copy despite being seeded onto
    real staff positions."""
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    resp = await client.get(f"/staff/{staff_id}/permissions", headers=auth)
    assert resp.status_code == 200
    keys = {(p["module"], p["action"]) for p in resp.json()}
    assert ("assessments", "record_behaviour") in keys
    assert ("documents", "view") in keys
    assert ("documents", "manage") in keys


@pytest.mark.asyncio
async def test_set_permission_allows_record_behaviour(
    client: AsyncClient, auth: dict, redis_permissions,
):
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    resp = await client.post(f"/staff/{staff_id}/permissions", json={
        "module": "assessments", "action": "record_behaviour", "is_allowed": True,
    }, headers=auth)
    assert resp.status_code == 200
    row = next(p for p in resp.json() if p["module"] == "assessments" and p["action"] == "record_behaviour")
    assert row["effective"] is True
    assert row["source"] == "override"


@pytest.mark.asyncio
async def test_resolve_permissions_ignores_mismatched_school_override(
    db_session: AsyncSession, school: School, redis_permissions,
):
    """Defense in depth: even if a StaffPermission row somehow exists with a
    school_id that doesn't match the staff member's own school, resolve_permissions()
    must not apply it."""
    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    other_school = School(
        name="Mismatch Test School", school_code="MISMATCH",
        school_type=SchoolType.SHS,
        region_id=region.id, district_id=district.id, is_active=True,
    )
    db_session.add(other_school)
    await db_session.flush()
    staff = StaffMember(
        school_id=school.id, staff_number="MIS001",
        first_name="Mismatch", last_name="Test", is_active=True,
    )
    db_session.add(staff)
    await db_session.flush()
    db_session.add(StaffPermission(
        school_id=other_school.id,  # wrong school on purpose
        staff_member_id=staff.id, module="fees", action="manage", is_allowed=True,
    ))
    await db_session.flush()

    from app.core.permissions import resolve_permissions
    perms = await resolve_permissions(staff.id, db_session)
    assert perms.get("fees.manage", False) is False


# ── Staff photo ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_and_delete_staff_photo(client: AsyncClient, auth: dict):
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    assert (await client.get(f"/staff/{staff_id}", headers=auth)).json()["photo_url"] is None

    resp = await client.post(
        f"/staff/{staff_id}/photo",
        files={"file": ("photo.png", _tiny_png(), "image/png")},
        headers=auth,
    )
    assert resp.status_code == 200
    photo_url = resp.json()["photo_url"]
    assert photo_url is not None
    assert photo_url.endswith(".webp")

    detail = (await client.get(f"/staff/{staff_id}", headers=auth)).json()
    assert detail["photo_url"] == photo_url

    del_resp = await client.delete(f"/staff/{staff_id}/photo", headers=auth)
    assert del_resp.status_code == 204

    detail = (await client.get(f"/staff/{staff_id}", headers=auth)).json()
    assert detail["photo_url"] is None


@pytest.mark.asyncio
async def test_upload_staff_photo_rejects_non_image(client: AsyncClient, auth: dict):
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    resp = await client.post(
        f"/staff/{staff_id}/photo",
        files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
        headers=auth,
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_upload_staff_photo_self_service_without_staff_edit(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions,
):
    """A staff member holding no staff.* permission at all (plain TEACHER)
    can still manage their OWN photo — assert_self_or_permission's self
    branch — but not someone else's."""
    teacher_auth, own_staff_id = await _login_as_teacher_no_edit(client, auth, db_session, school)
    other_staff_id = (await client.post("/staff", json=_staff_payload(staff_number="OTHER-PHOTO"), headers=auth)).json()["id"]

    own_resp = await client.post(
        f"/staff/{own_staff_id}/photo",
        files={"file": ("photo.png", _tiny_png(), "image/png")},
        headers=teacher_auth,
    )
    assert own_resp.status_code == 200
    assert own_resp.json()["photo_url"] is not None

    other_resp = await client.post(
        f"/staff/{other_staff_id}/photo",
        files={"file": ("photo.png", _tiny_png(), "image/png")},
        headers=teacher_auth,
    )
    assert other_resp.status_code == 403


# ── Position/password-reset escalation guard ───────────────────────────────────
# staff.edit (held by DEPUTY_HEAD, not just HEAD) previously let a caller
# change ANY staff member's position_ids — including their own, straight
# onto HEAD — and reset ANY staff member's password with zero seniority
# check. Both now require school.manage_users, matching the existing
# POST /staff/{id}/invite precedent.

@pytest.mark.asyncio
async def test_reset_password_rejected_without_manage_users(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions,
):
    """A DEPUTY_HEAD (holds staff.edit, not school.manage_users) must not be
    able to reset the HEAD's password — that's a direct account takeover."""
    head_auth, head_staff_id = await _login_as_position(client, auth, db_session, school, "HEAD")
    deputy_auth, _deputy_id = await _login_as_position(client, auth, db_session, school, "DEPUTY_HEAD")

    resp = await client.post(f"/staff/{head_staff_id}/reset-password", headers=deputy_auth)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reset_password_allowed_for_manage_users_holder(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions,
):
    _head_auth, head_staff_id = await _login_as_position(client, auth, db_session, school, "HEAD")

    resp = await client.post(f"/staff/{head_staff_id}/reset-password", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["temporary_password"]

    log = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.entity_id == head_staff_id, AuditLog.action == "STAFF_PASSWORD_RESET",
        )
    )
    assert log is not None
    # Never log the actual temp password.
    assert "password" not in str(log.new_values).lower() or "reset_by_user_id" in log.new_values


@pytest.mark.asyncio
async def test_update_position_ids_rejected_without_manage_users(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions,
):
    """The self-escalation path: a DEPUTY_HEAD must not be able to PATCH
    their own (or anyone's) position_ids onto something stronger."""
    head_pos_id = await _get_head_position_id(db_session)
    deputy_auth, deputy_staff_id = await _login_as_position(client, auth, db_session, school, "DEPUTY_HEAD")

    resp = await client.patch(
        f"/staff/{deputy_staff_id}", json={"position_ids": [head_pos_id]}, headers=deputy_auth,
    )
    assert resp.status_code == 403

    # Confirm nothing actually changed.
    check = await client.get(f"/staff/{deputy_staff_id}", headers=auth)
    assert head_pos_id not in check.json()["position_ids"]


@pytest.mark.asyncio
async def test_update_position_ids_rejected_against_other_staff_without_manage_users(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions,
):
    deputy_auth, _deputy_id = await _login_as_position(client, auth, db_session, school, "DEPUTY_HEAD")
    other_staff_id = (await client.post("/staff", json=_staff_payload(staff_number="TST-OTHER"), headers=auth)).json()["id"]
    some_pos_id = await _get_position_id(db_session)

    resp = await client.patch(
        f"/staff/{other_staff_id}", json={"position_ids": [some_pos_id]}, headers=deputy_auth,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_profile_fields_still_allowed_without_manage_users(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions,
):
    """Ordinary profile edits (no position_ids) must be unaffected — only
    the position-assignment sub-action needs the stronger permission."""
    deputy_auth, _deputy_id = await _login_as_position(client, auth, db_session, school, "DEPUTY_HEAD")
    other_staff_id = (await client.post("/staff", json=_staff_payload(staff_number="TST-EDITABLE"), headers=auth)).json()["id"]

    resp = await client.patch(
        f"/staff/{other_staff_id}", json={"phone": "0244000000"}, headers=deputy_auth,
    )
    assert resp.status_code == 200
    assert resp.json()["phone"] == "0244000000"


@pytest.mark.asyncio
async def test_update_position_ids_allowed_for_manage_users_holder_writes_audit_log(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
):
    staff_id = (await client.post("/staff", json=_staff_payload(), headers=auth)).json()["id"]
    pos_id = await _get_position_id(db_session)

    resp = await client.patch(f"/staff/{staff_id}", json={"position_ids": [pos_id]}, headers=auth)
    assert resp.status_code == 200
    assert pos_id in resp.json()["position_ids"]

    log = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.entity_id == staff_id, AuditLog.action == "STAFF_POSITION_CHANGE",
        )
    )
    assert log is not None
    assert log.new_values["position_ids"] == [pos_id]
