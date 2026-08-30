"""
Offline sync tests — period-level attendance marking (additive to the
always-available whole-day roll call), mirroring test_attendance_periods.py's
online-path test shapes but through POST /sync/outbox.

Run inside Docker: docker compose exec api pytest app/tests/test_sync_attendance_periods.py -v
"""
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicYear, Class
from app.models.attendance import AttendanceRecord
from app.models.school import School
from app.models.staff import StaffMember
from app.models.students import Student
from app.tests.test_attendance_periods import _make_calendar_day, _setup_timetabled_period, _weekday_of
from app.tests.test_sync_attendance import _outbox_attendance_payload


@pytest.mark.asyncio
async def test_outbox_period_mark_rejected_when_feature_off(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, academic_term, staff_member: StaffMember,
    student: Student,
):
    day = _weekday_of(academic_term.start_date)
    _, period = await _setup_timetabled_period(
        db_session, school, school_class, academic_year, staff_member, day=day,
    )
    cal = await _make_calendar_day(db_session, school, academic_term.start_date, academic_term.id)
    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    resp = await client.post("/sync/outbox",
        json=_outbox_attendance_payload(
            cal, school_class.id, student, "PRESENT", "ob-pat-off", offline_ts, period_id=period.id,
        ),
        headers=auth,
    )
    assert resp.status_code == 422
    assert "not enabled" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_outbox_period_mark_applied_and_coexists_with_daily(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, academic_term, staff_member: StaffMember,
    student: Student,
):
    school.has_period_attendance = True
    day = _weekday_of(academic_term.start_date)
    _, period = await _setup_timetabled_period(
        db_session, school, school_class, academic_year, staff_member, day=day,
    )
    cal = await _make_calendar_day(db_session, school, academic_term.start_date, academic_term.id)
    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    resp = await client.post("/sync/outbox",
        json=_outbox_attendance_payload(
            cal, school_class.id, student, "ABSENT", "ob-pat-1", offline_ts, period_id=period.id,
        ),
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "applied"

    resp = await client.post("/sync/outbox",
        json=_outbox_attendance_payload(cal, school_class.id, student, "PRESENT", "ob-pat-2", offline_ts),
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "applied"

    recs = list(await db_session.scalars(
        select(AttendanceRecord).where(
            AttendanceRecord.school_calendar_id == cal.id, AttendanceRecord.student_id == student.id,
        )
    ))
    assert len(recs) == 2
    by_period = {r.period_id: r.status.value for r in recs}
    assert by_period[period.id] == "ABSENT"
    assert by_period[None] == "PRESENT"


@pytest.mark.asyncio
async def test_outbox_period_mark_rejected_without_timetable_slot(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, academic_term, student: Student,
):
    from app.tests.test_attendance_periods import _make_period

    school.has_period_attendance = True
    day = _weekday_of(academic_term.start_date)
    period = await _make_period(db_session, school, day)  # no TimetableSlot
    cal = await _make_calendar_day(db_session, school, academic_term.start_date, academic_term.id)
    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    resp = await client.post("/sync/outbox",
        json=_outbox_attendance_payload(
            cal, school_class.id, student, "PRESENT", "ob-pat-noslot", offline_ts, period_id=period.id,
        ),
        headers=auth,
    )
    assert resp.status_code == 422
    assert "timetabled" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_outbox_period_absent_mark_fires_no_notifications(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, academic_term, staff_member: StaffMember,
    student: Student, monkeypatch,
):
    school.has_period_attendance = True
    day = _weekday_of(academic_term.start_date)
    _, period = await _setup_timetabled_period(
        db_session, school, school_class, academic_year, staff_member, day=day,
    )
    cal = await _make_calendar_day(db_session, school, academic_term.start_date, academic_term.id)
    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    calls: list = []

    async def _fake_check_and_notify_risk(*args, **kwargs):
        calls.append(args)

    monkeypatch.setattr("app.services.sync_attendance.risk_svc.check_and_notify_risk", _fake_check_and_notify_risk)

    resp = await client.post("/sync/outbox",
        json=_outbox_attendance_payload(
            cal, school_class.id, student, "ABSENT", "ob-pat-notif", offline_ts, period_id=period.id,
        ),
        headers=auth,
    )
    assert resp.status_code == 200
    assert calls == []


@pytest.mark.asyncio
async def test_outbox_period_mark_conflict_detected_independently_of_daily(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, academic_term, staff_member: StaffMember,
    student: Student,
):
    """A newer whole-day record must not falsely trigger a conflict for a
    period-level sync of the SAME student/day, and vice versa — the two are
    independent rows, matched by period_id in the conflict lookup."""
    school.has_period_attendance = True
    day = _weekday_of(academic_term.start_date)
    _, period = await _setup_timetabled_period(
        db_session, school, school_class, academic_year, staff_member, day=day,
    )
    cal = await _make_calendar_day(db_session, school, academic_term.start_date, academic_term.id)

    # A very old offline session — anything already recorded server-side
    # for THIS period counts as "newer than the offline session."
    old_offline_ts = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    # Seed a real, current period-level record server-side first.
    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(cal.id), "class_id": str(school_class.id),
        "period_id": str(period.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=auth)
    assert resp.status_code == 201

    # Offline sync for the SAME period, stale relative to that seed -> conflict.
    resp = await client.post("/sync/outbox",
        json=_outbox_attendance_payload(
            cal, school_class.id, student, "ABSENT", "ob-pat-conflict", old_offline_ts, period_id=period.id,
        ),
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "conflict"

    # Offline sync for the WHOLE DAY (period_id=None) with the same stale
    # timestamp must apply cleanly — no whole-day record exists yet, so
    # there's nothing to conflict against.
    resp = await client.post("/sync/outbox",
        json=_outbox_attendance_payload(cal, school_class.id, student, "LATE", "ob-pat-daily-ok", old_offline_ts),
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "applied"
