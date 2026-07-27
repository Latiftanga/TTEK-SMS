"""
Attendance integration tests — schedule, calendar generation, marking, summary.
Run inside Docker: docker compose exec api pytest app/tests/test_attendance.py -v
"""
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import AcademicTerm, Class
from app.models.attendance import DayType, SchoolCalendar
from app.models.auth import LoginType, StaffPosition, User
from app.models.school import GhanaDistrict, GhanaRegion, School, SchoolType
from app.models.students import Student


async def _login_as_position(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, position_code: str,
) -> dict:
    """Create a staff member holding `position_code`, give them a login, and return
    their bearer-token auth headers — mirrors test_scoring_lock.py's helper."""
    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == position_code))
    assert pos is not None, "Run seed_reference_data.py first"

    staff_id = (await client.post("/staff", json={
        "staff_number": f"TST-{position_code}", "first_name": "Test", "last_name": position_code.title(),
    }, headers=auth)).json()["id"]
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
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _other_school_auth(client: AsyncClient, db_session: AsyncSession) -> dict:
    """Create a second school + superadmin and return their auth headers."""
    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    school = School(
        name="Other Test School", school_code="OTHER001", school_type=SchoolType.SHS,
        region_id=region.id, district_id=district.id, is_active=True,
    )
    db_session.add(school)
    await db_session.flush()
    user = User(
        login_type=LoginType.EMAIL, email="other-admin@test.gh",
        password_hash=hash_password("pw"), is_active=True,
        is_superadmin=True, school_id=school.id,
    )
    db_session.add(user)
    await db_session.flush()
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL", "identifier": "other-admin@test.gh", "password": "pw",
    })
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── School schedule ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_schedule(client: AsyncClient, auth: dict):
    resp = await client.post("/attendance/schedule", json={
        "day_of_week": "MON", "is_school_day": True,
        "start_time": "07:30:00", "end_time": "15:00:00",
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["day_of_week"] == "MON"
    assert data["is_school_day"] is True


@pytest.mark.asyncio
async def test_upsert_schedule_idempotent(client: AsyncClient, auth: dict):
    """Re-posting the same day updates, not duplicates."""
    for _ in range(2):
        resp = await client.post("/attendance/schedule", json={
            "day_of_week": "TUE", "is_school_day": True,
        }, headers=auth)
        assert resp.status_code == 201
    resp = await client.get("/attendance/schedule", headers=auth)
    tue_entries = [s for s in resp.json() if s["day_of_week"] == "TUE"]
    assert len(tue_entries) == 1


@pytest.mark.asyncio
async def test_list_schedule(client: AsyncClient, auth: dict):
    await client.post("/attendance/schedule", json={
        "day_of_week": "WED", "is_school_day": True,
    }, headers=auth)
    resp = await client.get("/attendance/schedule", headers=auth)
    assert resp.status_code == 200
    assert any(s["day_of_week"] == "WED" for s in resp.json())


# ── Calendar generation ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_calendar(
    client: AsyncClient, auth: dict, academic_term: AcademicTerm
):
    resp = await client.post("/attendance/calendar/generate", json={
        "term_id": str(academic_term.id),
    }, headers=auth)
    assert resp.status_code == 201
    days = resp.json()
    assert len(days) > 0
    # All days have the correct term_id
    assert all(d["academic_term_id"] == str(academic_term.id) for d in days)
    # Weekends must not be SCHOOL_DAY
    for d in days:
        dt = date.fromisoformat(d["date"])
        if dt.weekday() >= 5:  # Saturday=5, Sunday=6
            assert d["day_type"] == "WEEKEND", f"{dt} should be WEEKEND, got {d['day_type']}"


@pytest.mark.asyncio
async def test_generate_calendar_idempotent(
    client: AsyncClient, auth: dict, academic_term: AcademicTerm
):
    """Second generation skips already-created days."""
    r1 = await client.post("/attendance/calendar/generate", json={
        "term_id": str(academic_term.id),
    }, headers=auth)
    r2 = await client.post("/attendance/calendar/generate", json={
        "term_id": str(academic_term.id),
    }, headers=auth)
    assert r1.status_code == 201
    assert r2.status_code == 201
    # Second run creates 0 new days (all already exist)
    assert len(r2.json()) == 0


@pytest.mark.asyncio
async def test_list_calendar(
    client: AsyncClient, auth: dict, academic_term: AcademicTerm
):
    await client.post("/attendance/calendar/generate", json={
        "term_id": str(academic_term.id),
    }, headers=auth)
    resp = await client.get(f"/attendance/calendar?term_id={academic_term.id}", headers=auth)
    assert resp.status_code == 200
    assert len(resp.json()) > 0


@pytest.mark.asyncio
async def test_override_calendar_day(
    client: AsyncClient, auth: dict, school_calendar: SchoolCalendar
):
    resp = await client.patch(f"/attendance/calendar/{school_calendar.id}", json={
        "day_type": "SCHOOL_HOLIDAY", "notes": "Inter-school sports day",
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["day_type"] == "SCHOOL_HOLIDAY"
    assert resp.json()["notes"] == "Inter-school sports day"


# ── Attendance marking ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mark_attendance(
    client: AsyncClient, auth: dict,
    school_calendar: SchoolCalendar, school_class: Class, student: Student,
):
    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "PRESENT"
    assert data[0]["student_id"] == str(student.id)


@pytest.mark.asyncio
async def test_mark_attendance_on_holiday_rejected(
    client: AsyncClient, auth: dict,
    db_session: AsyncSession,
    school: School, school_class: Class, student: Student,
    academic_term: AcademicTerm,
):
    holiday_cal = SchoolCalendar(
        school_id=school.id,
        date=date(2024, 12, 25),
        day_type=DayType.PUBLIC_HOLIDAY,
        academic_term_id=academic_term.id,
    )
    db_session.add(holiday_cal)
    await db_session.flush()

    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(holiday_cal.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_remark_attendance_updates_record(
    client: AsyncClient, auth: dict,
    school_calendar: SchoolCalendar, school_class: Class, student: Student,
):
    await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=auth)
    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "LATE", "notes": "Arrived at 8:15"}],
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()[0]["status"] == "LATE"


@pytest.mark.asyncio
async def test_list_attendance_records(
    client: AsyncClient, auth: dict,
    school_calendar: SchoolCalendar, school_class: Class, student: Student,
):
    await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "ABSENT"}],
    }, headers=auth)
    resp = await client.get(
        f"/attendance/records?calendar_id={school_calendar.id}&class_id={school_class.id}",
        headers=auth,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["status"] == "ABSENT"


# ── Attendance summary ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_attendance_summary(
    client: AsyncClient, auth: dict,
    school_calendar: SchoolCalendar, school_class: Class,
    student: Student, academic_term: AcademicTerm,
):
    await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=auth)
    resp = await client.get(
        f"/attendance/summary?student_id={student.id}&term_id={academic_term.id}",
        headers=auth,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["student_id"] == str(student.id)
    assert data["days_present"] == 1
    assert data["total_school_days"] >= 1
    assert 0.0 <= data["attendance_rate"] <= 100.0


# ── Tenant isolation ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mark_attendance_rejects_cross_school_class(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_calendar: SchoolCalendar, student: Student,
):
    other_auth = await _other_school_auth(client, db_session)
    other_class_resp = await client.post("/academic/classes", json={
        "level": "SHS", "year_group": 1, "stream": "A",
    }, headers=other_auth)
    other_class_id = other_class_resp.json()["id"]

    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": other_class_id,
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_mark_attendance_rejects_cross_school_student(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school_calendar: SchoolCalendar, school_class: Class,
):
    other_auth = await _other_school_auth(client, db_session)
    other_student_resp = await client.post("/students", json={
        "admission_number": "OTH001", "first_name": "Other", "last_name": "Student",
    }, headers=other_auth)
    other_student_id = other_student_resp.json()["id"]

    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": other_student_id, "status": "PRESENT"}],
    }, headers=auth)
    assert resp.status_code == 422
    assert other_student_id in resp.json()["detail"]


# ── Rate consistency after a day is reclassified ──────────────────────────────

@pytest.mark.asyncio
async def test_attendance_rate_consistent_after_day_reclassified(
    client: AsyncClient, auth: dict,
    school_calendar: SchoolCalendar, school_class: Class,
    student: Student, academic_term: AcademicTerm,
):
    """A day marked PRESENT, then reclassified to a non-markable type, must
    drop out of both the numerator and denominator — not just the
    denominator (which would let the rate exceed 100%)."""
    await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=auth)

    before = await client.get(
        f"/attendance/summary?student_id={student.id}&term_id={academic_term.id}", headers=auth,
    )
    assert before.json()["days_present"] == 1

    await client.patch(f"/attendance/calendar/{school_calendar.id}", json={
        "day_type": "PUBLIC_HOLIDAY", "notes": "Reclassified after marking",
    }, headers=auth)

    after = await client.get(
        f"/attendance/summary?student_id={student.id}&term_id={academic_term.id}", headers=auth,
    )
    data = after.json()
    assert data["days_present"] == 0
    assert data["attendance_rate"] <= 100.0


# ── Manual override protection ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_force_regenerate_preserves_manual_override(
    client: AsyncClient, auth: dict, academic_term: AcademicTerm,
):
    await client.post("/attendance/calendar/generate", json={"term_id": str(academic_term.id)}, headers=auth)
    days = (await client.get(f"/attendance/calendar?term_id={academic_term.id}", headers=auth)).json()

    # Find a real WEEKEND day and manually override it to SCHOOL_DAY — the
    # kind of one-off correction (e.g. a Saturday class) force-regeneration
    # would otherwise blindly reset back to WEEKEND.
    weekend_day = next(d for d in days if d["day_type"] == "WEEKEND")
    override_resp = await client.patch(f"/attendance/calendar/{weekend_day['id']}", json={
        "day_type": "SCHOOL_DAY", "notes": "Special Saturday class",
    }, headers=auth)
    assert override_resp.json()["is_manual_override"] is True

    await client.post("/attendance/calendar/generate", json={
        "term_id": str(academic_term.id), "force": True,
    }, headers=auth)

    after = (await client.get(f"/attendance/calendar?term_id={academic_term.id}", headers=auth)).json()
    reloaded = next(d for d in after if d["id"] == weekend_day["id"])
    assert reloaded["day_type"] == "SCHOOL_DAY"  # survived force-regeneration
    assert reloaded["is_manual_override"] is True

    # A non-overridden day in the same batch still regenerates normally.
    other_weekend = next(d for d in days if d["day_type"] == "WEEKEND" and d["id"] != weekend_day["id"])
    reloaded_other = next(d for d in after if d["id"] == other_weekend["id"])
    assert reloaded_other["day_type"] == "WEEKEND"
    assert reloaded_other["is_manual_override"] is False


# ── Term lock ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mark_attendance_blocked_when_term_locked_without_reason(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school_calendar: SchoolCalendar, school_class: Class, student: Student,
    academic_term: AcademicTerm,
):
    academic_term.results_locked = True
    await db_session.flush()

    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=auth)
    assert resp.status_code == 423


@pytest.mark.asyncio
async def test_mark_attendance_allowed_when_locked_with_reason_and_permission(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_calendar: SchoolCalendar, school_class: Class, student: Student,
    academic_term: AcademicTerm, redis_permissions: None,
):
    academic_term.results_locked = True
    await db_session.flush()

    hod_auth = await _login_as_position(client, auth, db_session, school, "HOD")
    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
        "override_reason": "Late correction approved",
    }, headers=hod_auth)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_mark_attendance_reason_alone_insufficient_without_permission(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_calendar: SchoolCalendar, school_class: Class, student: Student,
    academic_term: AcademicTerm, redis_permissions: None,
):
    academic_term.results_locked = True
    await db_session.flush()

    teacher_auth = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
        "override_reason": "I really need to mark this",
    }, headers=teacher_auth)
    assert resp.status_code == 423


# ── Shared attendance stats helper ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_compute_attendance_stats_excludes_reclassified_day(
    db_session: AsyncSession, client: AsyncClient, auth: dict,
    school_calendar: SchoolCalendar, school_class: Class,
    student: Student, academic_term: AcademicTerm, school: School,
):
    from app.services.attendance_stats import compute_attendance_stats

    await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=auth)

    stats = await compute_attendance_stats(student.id, [academic_term.id], school.id, db_session)
    present, total = stats[academic_term.id]
    assert present == 1
    assert total >= 1

    await client.patch(f"/attendance/calendar/{school_calendar.id}", json={
        "day_type": "PUBLIC_HOLIDAY",
    }, headers=auth)

    stats_after = await compute_attendance_stats(student.id, [academic_term.id], school.id, db_session)
    present_after, total_after = stats_after.get(academic_term.id, (0, 0))
    assert present_after == 0
    assert present_after <= total_after
