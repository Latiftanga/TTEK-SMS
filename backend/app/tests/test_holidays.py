"""
Superadmin CRUD for GhanaPublicHoliday — system-wide reference data.
Run inside Docker: docker compose exec api pytest app/tests/test_holidays.py -v
"""
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.attendance import GhanaPublicHoliday
from app.models.auth import LoginType, StaffPosition, User
from app.models.school import School


async def _login_as_head(client: AsyncClient, auth: dict, db_session: AsyncSession, school: School) -> dict:
    """A real (non-superadmin) staff login holding HEAD — proves the holiday
    endpoints reject a normal school admin, not just an anonymous caller.
    The default `auth` fixture is itself a superadmin (conftest.py::school_admin)."""
    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == "HEAD"))
    assert pos is not None, "Run seed_reference_data.py first"

    staff_id = (await client.post("/staff", json={
        "staff_number": "TST-HOL-HEAD", "first_name": "Test", "last_name": "Head",
    }, headers=auth)).json()["id"]
    await client.patch(f"/staff/{staff_id}", json={"position_ids": [str(pos.id)]}, headers=auth)

    db_session.add(User(
        school_id=school.id, login_type=LoginType.EMAIL, email="head@holiday-test.edu.gh",
        password_hash=hash_password("Whatever123!"), is_active=True, staff_member_id=staff_id,
    ))
    await db_session.flush()
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL", "identifier": "head@holiday-test.edu.gh", "password": "Whatever123!",
        "school_code": school.school_code,
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_list_holidays(client: AsyncClient, auth: dict):
    resp = await client.get("/superadmin/holidays", headers=auth)
    assert resp.status_code == 200
    assert len(resp.json()) > 0  # seeded reference data


@pytest.mark.asyncio
async def test_create_update_delete_holiday(client: AsyncClient, auth: dict, db_session: AsyncSession):
    resp = await client.post("/superadmin/holidays", json={
        "name": "Test Founders Day", "date": "2026-01-15", "is_recurring": True,
    }, headers=auth)
    assert resp.status_code == 201
    holiday_id = resp.json()["id"]
    assert resp.json()["is_recurring"] is True

    resp = await client.patch(f"/superadmin/holidays/{holiday_id}", json={
        "is_recurring": False, "description": "Now a one-off",
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["is_recurring"] is False
    assert resp.json()["description"] == "Now a one-off"

    resp = await client.delete(f"/superadmin/holidays/{holiday_id}", headers=auth)
    assert resp.status_code == 204
    assert await db_session.get(GhanaPublicHoliday, holiday_id) is None


@pytest.mark.asyncio
async def test_update_nonexistent_holiday_404(client: AsyncClient, auth: dict):
    resp = await client.patch(
        "/superadmin/holidays/00000000-0000-0000-0000-000000000000",
        json={"name": "Nope"}, headers=auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_holiday_endpoints_reject_non_superadmin(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    head_auth = await _login_as_head(client, auth, db_session, school)

    assert (await client.get("/superadmin/holidays", headers=head_auth)).status_code == 403
    assert (await client.post("/superadmin/holidays", json={
        "name": "X", "date": "2026-01-01",
    }, headers=head_auth)).status_code == 403

    existing = await db_session.scalar(select(GhanaPublicHoliday))
    assert (await client.patch(
        f"/superadmin/holidays/{existing.id}", json={"name": "X"}, headers=head_auth,
    )).status_code == 403
    assert (await client.delete(
        f"/superadmin/holidays/{existing.id}", headers=head_auth,
    )).status_code == 403
