"""
Period-level attendance marking — additive to the always-available daily
(whole-day) roll call, opt-in via School.has_period_attendance.

Run inside Docker: docker compose exec api pytest app/tests/test_attendance_periods.py -v
"""
from datetime import date, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicYear, Class, ClassSubject, ClassTeacher, Subject, SubjectTeacher, TimetableSlot
from app.models.attendance import DayOfWeek, DayType, SchoolCalendar, SchoolPeriod
from app.models.school import School
from app.models.staff import StaffMember
from app.models.students import Student
from app.tests.test_attendance import _login_as_position
from app.tests.test_dashboard import _teacher_login


def _weekday_of(d: date) -> DayOfWeek:
    return list(DayOfWeek)[d.weekday()]


async def _make_subject(db_session: AsyncSession, school: School, code: str) -> Subject:
    subject = Subject(school_id=school.id, code=code, name=f"{code} subject", is_active=True)
    db_session.add(subject)
    await db_session.flush()
    return subject


async def _make_period(
    db_session: AsyncSession, school: School, day: DayOfWeek, *, number=1,
    start=time(8, 0), end=time(8, 45),
) -> SchoolPeriod:
    period = SchoolPeriod(
        school_id=school.id, name=f"Period {number}", day_of_week=day,
        period_number=number, start_time=start, end_time=end,
    )
    db_session.add(period)
    await db_session.flush()
    return period


async def _make_calendar_day(
    db_session: AsyncSession, school: School, d: date, term_id, day_type=DayType.SCHOOL_DAY,
) -> SchoolCalendar:
    cal = SchoolCalendar(school_id=school.id, date=d, day_type=day_type, academic_term_id=term_id)
    db_session.add(cal)
    await db_session.flush()
    return cal


async def _setup_timetabled_period(
    db_session, school, school_class, academic_year, staff, *, day: DayOfWeek, code="MATH", number=1,
):
    """A class with a subject on its curriculum, a teacher assigned to it,
    a bell period on `day`, and a TimetableSlot tying them together — the
    minimum a period needs to become markable. `number` disambiguates when
    two calls target the same school+day (periods are school+day scoped,
    not class-scoped, and now also unique on name/start_time/end_time)."""
    subject = await _make_subject(db_session, school, code)
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subject.id, is_active=True))
    db_session.add(SubjectTeacher(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        staff_member_id=staff.id, academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()
    start = time(8 + number, 0)
    end = time(8 + number, 45)
    period = await _make_period(db_session, school, day, number=number, start=start, end=end)
    db_session.add(TimetableSlot(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        academic_year_id=academic_year.id, period_id=period.id,
    ))
    await db_session.flush()
    return subject, period


@pytest.mark.asyncio
async def test_period_mark_rejected_when_feature_off(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, academic_term, staff_member: StaffMember,
    student: Student,
):
    day = _weekday_of(academic_term.start_date)
    _, period = await _setup_timetabled_period(
        db_session, school, school_class, academic_year, staff_member, day=day,
    )
    cal = await _make_calendar_day(db_session, school, academic_term.start_date, academic_term.id)

    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(cal.id), "class_id": str(school_class.id),
        "period_id": str(period.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=auth)
    assert resp.status_code == 422
    assert "not enabled" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_period_mark_allowed_once_enabled_and_coexists_with_daily(
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

    # Daily (whole-day) mark first.
    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(cal.id), "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=auth)
    assert resp.status_code == 201

    # Period-level mark for the same student/day — additive, not a replacement.
    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(cal.id), "class_id": str(school_class.id),
        "period_id": str(period.id),
        "records": [{"student_id": str(student.id), "status": "ABSENT"}],
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()[0]["period_id"] == str(period.id)

    # Both rows exist independently.
    daily = await client.get("/attendance/records", params={
        "calendar_id": str(cal.id), "class_id": str(school_class.id),
    }, headers=auth)
    assert len(daily.json()) == 1
    assert daily.json()[0]["status"] == "PRESENT"

    period_recs = await client.get("/attendance/records", params={
        "calendar_id": str(cal.id), "class_id": str(school_class.id), "period_id": str(period.id),
    }, headers=auth)
    assert len(period_recs.json()) == 1
    assert period_recs.json()[0]["status"] == "ABSENT"


@pytest.mark.asyncio
async def test_period_mark_rejected_without_timetable_slot(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, academic_term, student: Student,
):
    school.has_period_attendance = True
    day = _weekday_of(academic_term.start_date)
    period = await _make_period(db_session, school, day)  # no TimetableSlot at all
    cal = await _make_calendar_day(db_session, school, academic_term.start_date, academic_term.id)

    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(cal.id), "class_id": str(school_class.id),
        "period_id": str(period.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=auth)
    assert resp.status_code == 422
    assert "timetabled" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_period_mark_rejected_on_weekday_mismatch(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, academic_term, staff_member: StaffMember,
    student: Student,
):
    school.has_period_attendance = True
    real_day = _weekday_of(academic_term.start_date)
    other_day = DayOfWeek.SUN if real_day != DayOfWeek.SUN else DayOfWeek.SAT
    _, period = await _setup_timetabled_period(
        db_session, school, school_class, academic_year, staff_member, day=other_day,
    )
    cal = await _make_calendar_day(db_session, school, academic_term.start_date, academic_term.id)

    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(cal.id), "class_id": str(school_class.id),
        "period_id": str(period.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=auth)
    assert resp.status_code == 422
    assert "different weekday" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_class_teacher_can_mark_period_they_dont_teach(
    client: AsyncClient, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, academic_term, staff_member: StaffMember,
    student: Student, redis_permissions: None,
):
    """ClassTeacher scope grants period marking too, regardless of who the
    period's own SubjectTeacher is."""
    school.has_period_attendance = True
    other_staff = StaffMember(school_id=school.id, staff_number="OTH001", first_name="Other", last_name="Teacher", is_active=True)
    db_session.add(other_staff)
    await db_session.flush()

    day = _weekday_of(academic_term.start_date)
    _, period = await _setup_timetabled_period(
        db_session, school, school_class, academic_year, other_staff, day=day,
    )
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_member.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()
    cal = await _make_calendar_day(db_session, school, academic_term.start_date, academic_term.id)

    ct_auth = await _teacher_login(client, db_session, school, staff_member)

    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(cal.id), "class_id": str(school_class.id),
        "period_id": str(period.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=ct_auth)
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_subject_teacher_can_mark_own_period_not_a_different_one(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, academic_term, staff_member: StaffMember,
    student: Student, redis_permissions: None,
):
    school.has_period_attendance = True
    day = _weekday_of(academic_term.start_date)

    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    staff = await db_session.get(StaffMember, staff_id)

    subject_a, period_a = await _setup_timetabled_period(
        db_session, school, school_class, academic_year, staff, day=day, code="MATH",
    )

    other_class = Class(school_id=school.id, level="SHS", year_group=2, stream="B", is_active=True)
    db_session.add(other_class)
    await db_session.flush()
    other_staff = StaffMember(school_id=school.id, staff_number="OTH002", first_name="Not", last_name="Teaching", is_active=True)
    db_session.add(other_staff)
    await db_session.flush()
    subject_b, period_b = await _setup_timetabled_period(
        db_session, school, other_class, academic_year, other_staff, day=day, code="ENG", number=2,
    )
    cal = await _make_calendar_day(db_session, school, academic_term.start_date, academic_term.id)

    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(cal.id), "class_id": str(school_class.id),
        "period_id": str(period_a.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=teacher_auth)
    assert resp.status_code == 201, resp.text

    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(cal.id), "class_id": str(other_class.id),
        "period_id": str(period_b.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=teacher_auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_period_absent_mark_does_not_trigger_risk_check(
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

    calls: list = []

    async def _fake_check_and_notify_risk(*args, **kwargs):
        calls.append(args)

    monkeypatch.setattr("app.services.attendance.risk_svc.check_and_notify_risk", _fake_check_and_notify_risk)

    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(cal.id), "class_id": str(school_class.id),
        "period_id": str(period.id),
        "records": [{"student_id": str(student.id), "status": "ABSENT"}],
    }, headers=auth)
    assert resp.status_code == 201
    assert calls == []

    # The daily path still calls it.
    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(cal.id), "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "ABSENT"}],
    }, headers=auth)
    assert resp.status_code == 201
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_list_markable_periods(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, academic_term, staff_member: StaffMember,
    student: Student,
):
    school.has_period_attendance = True
    day = _weekday_of(academic_term.start_date)
    subject, period = await _setup_timetabled_period(
        db_session, school, school_class, academic_year, staff_member, day=day,
    )
    cal = await _make_calendar_day(db_session, school, academic_term.start_date, academic_term.id)

    resp = await client.get("/attendance/markable-periods", params={
        "class_id": str(school_class.id), "calendar_id": str(cal.id),
    }, headers=auth)
    assert resp.status_code == 200
    periods = resp.json()
    assert len(periods) == 1
    assert periods[0]["period_id"] == str(period.id)
    assert periods[0]["subject_id"] == str(subject.id)
    assert periods[0]["can_mark"] is True
    assert periods[0]["already_marked"] is False

    await client.post("/attendance/mark", json={
        "school_calendar_id": str(cal.id), "class_id": str(school_class.id),
        "period_id": str(period.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=auth)

    resp = await client.get("/attendance/markable-periods", params={
        "class_id": str(school_class.id), "calendar_id": str(cal.id),
    }, headers=auth)
    assert resp.json()[0]["already_marked"] is True


@pytest.mark.asyncio
async def test_markable_periods_empty_when_feature_off(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, academic_term, staff_member: StaffMember,
):
    day = _weekday_of(academic_term.start_date)
    await _setup_timetabled_period(db_session, school, school_class, academic_year, staff_member, day=day)
    cal = await _make_calendar_day(db_session, school, academic_term.start_date, academic_term.id)

    resp = await client.get("/attendance/markable-periods", params={
        "class_id": str(school_class.id), "calendar_id": str(cal.id),
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.json() == []
