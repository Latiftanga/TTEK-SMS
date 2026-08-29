"""
Bell-schedule period (SchoolPeriod) CRUD tests — reactivates a table that
previously had zero code anywhere touching it.

Run inside Docker: docker compose exec api pytest app/tests/test_school_periods.py -v
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import School
from app.tests.test_attendance import _other_school_auth


@pytest.mark.asyncio
async def test_create_and_list_period(client: AsyncClient, auth: dict):
    resp = await client.post("/attendance/periods", json={
        "name": "Period 1", "day_of_week": "MON", "period_number": 1,
        "start_time": "08:00:00", "end_time": "08:45:00",
    }, headers=auth)
    assert resp.status_code == 201, resp.text
    period = resp.json()
    assert period["name"] == "Period 1"

    resp = await client.get("/attendance/periods", headers=auth)
    assert resp.status_code == 200
    assert any(p["id"] == period["id"] for p in resp.json())


@pytest.mark.asyncio
async def test_create_period_invalid_time_range_rejected(client: AsyncClient, auth: dict):
    resp = await client.post("/attendance/periods", json={
        "name": "Bad Period", "day_of_week": "MON", "period_number": 1,
        "start_time": "09:00:00", "end_time": "08:00:00",
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_period_number_same_day_rejected(client: AsyncClient, auth: dict):
    body = {
        "name": "Period 1", "day_of_week": "TUE", "period_number": 1,
        "start_time": "08:00:00", "end_time": "08:45:00",
    }
    resp = await client.post("/attendance/periods", json=body, headers=auth)
    assert resp.status_code == 201

    resp = await client.post("/attendance/periods", json={**body, "name": "Different name"}, headers=auth)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_and_delete_period(client: AsyncClient, auth: dict):
    resp = await client.post("/attendance/periods", json={
        "name": "Period 2", "day_of_week": "WED", "period_number": 2,
        "start_time": "08:45:00", "end_time": "09:30:00",
    }, headers=auth)
    period_id = resp.json()["id"]

    resp = await client.patch(f"/attendance/periods/{period_id}", json={"name": "Renamed"}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"

    resp = await client.delete(f"/attendance/periods/{period_id}", headers=auth)
    assert resp.status_code == 204

    resp = await client.get("/attendance/periods", headers=auth)
    assert all(p["id"] != period_id for p in resp.json())


@pytest.mark.asyncio
async def test_copy_periods_to_other_days(client: AsyncClient, auth: dict):
    for n, (start, end) in enumerate([("08:00:00", "08:45:00"), ("08:45:00", "09:30:00")], start=1):
        resp = await client.post("/attendance/periods", json={
            "name": f"Period {n}", "day_of_week": "MON", "period_number": n,
            "start_time": start, "end_time": end,
        }, headers=auth)
        assert resp.status_code == 201

    resp = await client.post("/attendance/periods/copy", json={
        "source_day": "MON", "target_days": ["TUE", "WED"],
    }, headers=auth)
    assert resp.status_code == 201
    created = resp.json()
    assert len(created) == 4  # 2 periods x 2 target days

    resp = await client.get("/attendance/periods", headers=auth)
    days = [p["day_of_week"] for p in resp.json()]
    assert days.count("MON") == 2
    assert days.count("TUE") == 2
    assert days.count("WED") == 2

    # Re-running the copy is a safe no-op — every (day, period_number)
    # combination already exists on the targets.
    resp = await client.post("/attendance/periods/copy", json={
        "source_day": "MON", "target_days": ["TUE", "WED"],
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json() == []


@pytest.mark.asyncio
async def test_copy_with_no_source_periods_rejected(client: AsyncClient, auth: dict):
    resp = await client.post("/attendance/periods/copy", json={
        "source_day": "SUN", "target_days": ["SAT"],
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_periods_are_school_scoped(client: AsyncClient, auth: dict, db_session: AsyncSession, school: School):
    resp = await client.post("/attendance/periods", json={
        "name": "Period 1", "day_of_week": "THU", "period_number": 1,
        "start_time": "08:00:00", "end_time": "08:45:00",
    }, headers=auth)
    period_id = resp.json()["id"]

    other_auth = await _other_school_auth(client, db_session)
    resp = await client.get("/attendance/periods", headers=other_auth)
    assert all(p["id"] != period_id for p in resp.json())

    resp = await client.patch(f"/attendance/periods/{period_id}", json={"name": "Hijacked"}, headers=other_auth)
    assert resp.status_code == 404


# ── SchoolSchedule/SchoolPeriod consolidation — periods can't be added to a
# day explicitly marked closed. Mirrors generate_calendar()'s own Mon-Fri
# default: a day with zero SchoolSchedule rows configured at all is still
# treated as open (every test above relies on this default already).

@pytest.mark.asyncio
async def test_create_period_rejected_on_closed_day(client: AsyncClient, auth: dict):
    await client.post("/attendance/schedule", json={"day_of_week": "SAT", "is_school_day": False}, headers=auth)

    resp = await client.post("/attendance/periods", json={
        "name": "Period 1", "day_of_week": "SAT", "period_number": 1,
        "start_time": "08:00:00", "end_time": "08:45:00",
    }, headers=auth)
    assert resp.status_code == 422
    assert "SAT" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_period_allowed_after_opening_day(client: AsyncClient, auth: dict):
    await client.post("/attendance/schedule", json={"day_of_week": "SUN", "is_school_day": False}, headers=auth)
    resp = await client.post("/attendance/periods", json={
        "name": "Period 1", "day_of_week": "SUN", "period_number": 1,
        "start_time": "08:00:00", "end_time": "08:45:00",
    }, headers=auth)
    assert resp.status_code == 422

    await client.post("/attendance/schedule", json={"day_of_week": "SUN", "is_school_day": True}, headers=auth)
    resp = await client.post("/attendance/periods", json={
        "name": "Period 1", "day_of_week": "SUN", "period_number": 1,
        "start_time": "08:00:00", "end_time": "08:45:00",
    }, headers=auth)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_period_allowed_by_default_with_no_schedule_configured(client: AsyncClient, auth: dict):
    """No /attendance/schedule rows exist at all for this school in this
    test — Mon-Fri defaults to open, matching generate_calendar()."""
    resp = await client.post("/attendance/periods", json={
        "name": "Period 1", "day_of_week": "FRI", "period_number": 1,
        "start_time": "08:00:00", "end_time": "08:45:00",
    }, headers=auth)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_copy_periods_skips_closed_target_day(client: AsyncClient, auth: dict):
    await client.post("/attendance/schedule", json={"day_of_week": "MON", "is_school_day": True}, headers=auth)
    await client.post("/attendance/schedule", json={"day_of_week": "SAT", "is_school_day": False}, headers=auth)

    resp = await client.post("/attendance/periods", json={
        "name": "Period 1", "day_of_week": "MON", "period_number": 1,
        "start_time": "08:00:00", "end_time": "08:45:00",
    }, headers=auth)
    assert resp.status_code == 201

    # TUE has no explicit row (defaults open via Mon-Fri, since MON now has
    # an explicit True row the "no rows at all" fallback no longer applies —
    # but TUE itself still has no row, so it's genuinely closed under the
    # exact semantics: "any explicit True row" only opens the days with one).
    resp = await client.post("/attendance/periods/copy", json={
        "source_day": "MON", "target_days": ["SAT", "TUE"],
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json() == []  # both targets skipped: SAT closed, TUE has no explicit open row

    resp = await client.get("/attendance/periods", headers=auth)
    days = [p["day_of_week"] for p in resp.json()]
    assert "SAT" not in days
    assert "TUE" not in days


# ── name/start_time/end_time uniqueness — same school+day, distinct fields ──

@pytest.mark.asyncio
async def test_duplicate_name_same_day_rejected(client: AsyncClient, auth: dict):
    await client.post("/attendance/periods", json={
        "name": "Assembly", "day_of_week": "MON", "period_number": 1,
        "start_time": "08:00:00", "end_time": "08:45:00",
    }, headers=auth)

    resp = await client.post("/attendance/periods", json={
        "name": "Assembly", "day_of_week": "MON", "period_number": 2,
        "start_time": "08:45:00", "end_time": "09:30:00",
    }, headers=auth)
    assert resp.status_code == 409
    assert "Assembly" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_duplicate_start_time_same_day_rejected(client: AsyncClient, auth: dict):
    await client.post("/attendance/periods", json={
        "name": "Period 1", "day_of_week": "MON", "period_number": 1,
        "start_time": "08:00:00", "end_time": "08:45:00",
    }, headers=auth)

    resp = await client.post("/attendance/periods", json={
        "name": "Period 2", "day_of_week": "MON", "period_number": 2,
        "start_time": "08:00:00", "end_time": "09:30:00",
    }, headers=auth)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_duplicate_end_time_same_day_rejected(client: AsyncClient, auth: dict):
    await client.post("/attendance/periods", json={
        "name": "Period 1", "day_of_week": "MON", "period_number": 1,
        "start_time": "08:00:00", "end_time": "08:45:00",
    }, headers=auth)

    resp = await client.post("/attendance/periods", json={
        "name": "Period 2", "day_of_week": "MON", "period_number": 2,
        "start_time": "07:00:00", "end_time": "08:45:00",
    }, headers=auth)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_same_name_and_times_allowed_on_different_day(client: AsyncClient, auth: dict):
    """Uniqueness is scoped per day, not school-wide — an identical Monday
    and Tuesday bell schedule is completely normal."""
    for day in ("MON", "TUE"):
        resp = await client.post("/attendance/periods", json={
            "name": "Period 1", "day_of_week": day, "period_number": 1,
            "start_time": "08:00:00", "end_time": "08:45:00",
        }, headers=auth)
        assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_update_period_rejects_collision_with_sibling(client: AsyncClient, auth: dict):
    await client.post("/attendance/periods", json={
        "name": "Period 1", "day_of_week": "MON", "period_number": 1,
        "start_time": "08:00:00", "end_time": "08:45:00",
    }, headers=auth)
    resp = await client.post("/attendance/periods", json={
        "name": "Period 2", "day_of_week": "MON", "period_number": 2,
        "start_time": "08:45:00", "end_time": "09:30:00",
    }, headers=auth)
    period2_id = resp.json()["id"]

    # Renaming Period 2 to collide with Period 1's name is rejected...
    resp = await client.patch(f"/attendance/periods/{period2_id}", json={"name": "Period 1"}, headers=auth)
    assert resp.status_code == 409

    # ...but saving it with its own unchanged values is fine (self-exclusion).
    resp = await client.patch(f"/attendance/periods/{period2_id}", json={"name": "Period 2"}, headers=auth)
    assert resp.status_code == 200
