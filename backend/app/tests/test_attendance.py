"""
Attendance integration tests — schedule, calendar generation, marking, summary.
Run inside Docker: docker compose exec api pytest app/tests/test_attendance.py -v
"""
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class
from app.models.attendance import DayType, SchoolCalendar
from app.models.school import School
from app.models.students import Student


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
