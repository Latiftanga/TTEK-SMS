"""
Staff profile integration tests.
Run inside Docker: docker compose exec api pytest app/tests/test_staff.py -v

Fixtures (school, school_admin, auth) come from conftest.py.
"""
import io
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import pytest_asyncio

from app.core.auth import hash_password
from app.models.academic import AcademicYear, Class, ClassTeacher
from app.models.auth import LoginType, StaffPosition, User
from app.models.school import School
from app.models.staff import StaffCategory, StaffRank, StaffType
from sqlalchemy import select


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


def _staff_payload(**overrides) -> dict:
    base = {
        "staff_number": "TST001",
        "first_name": "Kwame",
        "last_name": "Mensah",
    }
    return {**base, **overrides}


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
