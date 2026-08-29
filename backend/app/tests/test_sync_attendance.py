"""
Offline sync tests — Attendance (entity_type="attendance"), mirroring
test_sync.py's Score-sync test shapes.
Run inside Docker: docker compose exec api pytest app/tests/test_sync_attendance.py -v
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class, ClassTeacher
from app.models.attendance import AttendanceAuditLog, AttendanceRecord, DayType, SchoolCalendar
from app.models.school import School
from app.models.students import Student
from app.tests.test_sync import _login_as_position, _portal_login


def _outbox_attendance_payload(
    calendar: SchoolCalendar, class_id, student: Student, status: str,
    outbox_id: str, offline_ts: str, client_op_id: str | None = None,
) -> dict:
    return {
        "items": [{
            "outbox_id": outbox_id,
            "client_op_id": client_op_id or f"op-{outbox_id}",
            "entity_type": "attendance",
            "offline_session_started_at": offline_ts,
            "data": {
                "student_id": str(student.id),
                "school_calendar_id": str(calendar.id),
                "class_id": str(class_id),
                "status": status,
            },
        }]
    }


@pytest.mark.asyncio
async def test_outbox_applies_new_attendance(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school_calendar: SchoolCalendar,
    school_class: Class, student: Student,
):
    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = await client.post("/sync/outbox",
        json=_outbox_attendance_payload(school_calendar, school_class.id, student, "ABSENT", "ob-att-1", offline_ts),
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "applied"

    rec = await db_session.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.school_calendar_id == school_calendar.id,
            AttendanceRecord.student_id == student.id,
        )
    )
    assert rec is not None
    assert rec.status.value == "ABSENT"


@pytest.mark.asyncio
async def test_outbox_attendance_duplicate_client_op_id_is_noop(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school_calendar: SchoolCalendar, school_class: Class, student: Student,
):
    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    payload = _outbox_attendance_payload(
        school_calendar, school_class.id, student, "ABSENT", "ob-att-dup", offline_ts, client_op_id="op-dup-1",
    )
    r1 = await client.post("/sync/outbox", json=payload, headers=auth)
    r2 = await client.post("/sync/outbox", json=payload, headers=auth)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()[0]["status"] == r2.json()[0]["status"] == "applied"

    recs = (await db_session.scalars(
        select(AttendanceRecord).where(
            AttendanceRecord.school_calendar_id == school_calendar.id,
            AttendanceRecord.student_id == student.id,
        )
    )).all()
    assert len(recs) == 1


@pytest.mark.asyncio
async def test_outbox_attendance_detects_conflict(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_calendar: SchoolCalendar, school_class: Class, student: Student, school_admin,
):
    # Server already has a record marked AFTER the client's offline session began.
    db_session.add(AttendanceRecord(
        school_id=school.id, student_id=student.id, school_calendar_id=school_calendar.id,
        class_id=school_class.id, status="PRESENT",
        recorded_by_id=school_admin.id,
        recorded_at=datetime.now(timezone.utc) - timedelta(minutes=30),
    ))
    await db_session.flush()

    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = await client.post("/sync/outbox",
        json=_outbox_attendance_payload(school_calendar, school_class.id, student, "ABSENT", "ob-att-conf", offline_ts),
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "conflict"
    assert resp.json()[0]["conflict_id"] is not None


@pytest.mark.asyncio
async def test_outbox_rejects_cross_school_calendar_id(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school_class: Class, student: Student,
):
    from app.models.school import GhanaDistrict, GhanaRegion, SchoolType

    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    other = School(
        name="Other School Sync Test", school_code="OTHER_SYNC_ATT", school_type=SchoolType.SHS,
        region_id=region.id, district_id=district.id, is_active=True,
    )
    db_session.add(other)
    await db_session.flush()
    other_cal = SchoolCalendar(school_id=other.id, date=date(2024, 9, 3), day_type=DayType.SCHOOL_DAY)
    db_session.add(other_cal)
    await db_session.flush()

    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = await client.post("/sync/outbox",
        json=_outbox_attendance_payload(other_cal, school_class.id, student, "ABSENT", "ob-att-xschool", offline_ts),
        headers=auth,
    )
    assert resp.status_code == 422
    leaked = await db_session.scalar(
        select(AttendanceRecord).where(AttendanceRecord.school_calendar_id == other_cal.id)
    )
    assert leaked is None


@pytest.mark.asyncio
async def test_outbox_rejects_student_portal_login(
    client: AsyncClient, db_session: AsyncSession, school: School,
    school_calendar: SchoolCalendar, school_class: Class, student: Student,
):
    portal_auth = await _portal_login(client, db_session, school, student)
    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = await client.post("/sync/outbox",
        json=_outbox_attendance_payload(school_calendar, school_class.id, student, "ABSENT", "ob-att-portal", offline_ts),
        headers=portal_auth,
    )
    assert resp.status_code == 403
    leaked = await db_session.scalar(
        select(AttendanceRecord).where(AttendanceRecord.school_calendar_id == school_calendar.id)
    )
    assert leaked is None


@pytest.mark.asyncio
async def test_outbox_rejects_class_teacher_outside_their_class(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_calendar: SchoolCalendar, school_class: Class, student: Student, redis_permissions: None,
):
    teacher_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = await client.post("/sync/outbox",
        json=_outbox_attendance_payload(school_calendar, school_class.id, student, "ABSENT", "ob-att-scope1", offline_ts),
        headers=teacher_auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_outbox_allowed_for_scoped_class_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_calendar: SchoolCalendar, school_class: Class, student: Student,
    academic_term: AcademicTerm, redis_permissions: None,
):
    teacher_auth, teacher_staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=teacher_staff_id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()

    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = await client.post("/sync/outbox",
        json=_outbox_attendance_payload(school_calendar, school_class.id, student, "ABSENT", "ob-att-scope2", offline_ts),
        headers=teacher_auth,
    )
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "applied"


@pytest.mark.asyncio
async def test_outbox_attendance_blocked_when_term_locked_without_reason(
    client: AsyncClient, auth: dict, school_calendar: SchoolCalendar,
    school_class: Class, student: Student, academic_term: AcademicTerm,
):
    lock = await client.patch(f"/academic/terms/{academic_term.id}", json={"results_locked": True}, headers=auth)
    assert lock.status_code == 200

    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = await client.post("/sync/outbox",
        json=_outbox_attendance_payload(school_calendar, school_class.id, student, "ABSENT", "ob-att-lock1", offline_ts),
        headers=auth,
    )
    assert resp.status_code == 423


@pytest.mark.asyncio
async def test_outbox_attendance_allowed_when_term_locked_with_reason(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school_calendar: SchoolCalendar,
    school_class: Class, student: Student, academic_term: AcademicTerm,
):
    lock = await client.patch(f"/academic/terms/{academic_term.id}", json={"results_locked": True}, headers=auth)
    assert lock.status_code == 200

    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    payload = _outbox_attendance_payload(school_calendar, school_class.id, student, "ABSENT", "ob-att-lock2", offline_ts)
    payload["items"][0]["override_reason"] = "Backfilling an offline mark from before the lock."
    resp = await client.post("/sync/outbox", json=payload, headers=auth)
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "applied"

    rec = await db_session.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.school_calendar_id == school_calendar.id, AttendanceRecord.student_id == student.id,
        )
    )
    log = await db_session.scalar(
        select(AttendanceAuditLog).where(AttendanceAuditLog.attendance_record_id == rec.id)
    )
    assert log.reason == "Backfilling an offline mark from before the lock."


@pytest.mark.asyncio
async def test_outbox_rejects_non_markable_day(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, student: Student, academic_term: AcademicTerm,
):
    holiday_cal = SchoolCalendar(
        school_id=school.id, date=date(2024, 9, 9),
        day_type=DayType.PUBLIC_HOLIDAY, academic_term_id=academic_term.id,
    )
    db_session.add(holiday_cal)
    await db_session.flush()

    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = await client.post("/sync/outbox",
        json=_outbox_attendance_payload(holiday_cal, school_class.id, student, "ABSENT", "ob-att-holiday", offline_ts),
        headers=auth,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_outbox_synced_absence_reaches_consecutive_absence_check(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, student: Student, academic_term: AcademicTerm,
):
    """Proves an offline-synced ABSENT mark runs through the exact same
    downstream side-effect path as an online one — check_consecutive_absences
    only returns True once the THIRD offline-synced absence lands."""
    from app.services.attendance_risk import check_consecutive_absences

    days = [
        SchoolCalendar(school_id=school.id, date=date(2024, 9, 10 + i),
                       day_type=DayType.SCHOOL_DAY, academic_term_id=academic_term.id)
        for i in range(3)
    ]
    db_session.add_all(days)
    await db_session.flush()

    for i, cal in enumerate(days):
        offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        resp = await client.post("/sync/outbox",
            json=_outbox_attendance_payload(cal, school_class.id, student, "ABSENT", f"ob-att-consec-{i}", offline_ts),
            headers=auth,
        )
        assert resp.status_code == 200
        assert resp.json()[0]["status"] == "applied"

    assert await check_consecutive_absences(student.id, days[-1].id, school.id, db_session) is True
