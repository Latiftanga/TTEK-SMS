"""
School-wide period-level "who's marked, who hasn't" oversight — the
period-level sibling of test_attendance.py's marking-status tests.

Run inside Docker: docker compose exec api pytest app/tests/test_attendance_period_status.py -v
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicYear, Class, ClassTeacher
from app.models.school import School
from app.models.staff import StaffMember
from app.models.students import Student
from app.tests.test_attendance_periods import _make_calendar_day, _make_period, _setup_timetabled_period, _weekday_of
from app.tests.test_dashboard import _teacher_login


@pytest.mark.asyncio
async def test_period_marking_status_empty_when_feature_off(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, academic_term, staff_member: StaffMember,
):
    day = _weekday_of(academic_term.start_date)
    await _setup_timetabled_period(db_session, school, school_class, academic_year, staff_member, day=day)
    cal = await _make_calendar_day(db_session, school, academic_term.start_date, academic_term.id)

    resp = await client.get(
        "/attendance/period-marking-status", params={"calendar_id": str(cal.id)}, headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_period_marking_status_empty_without_timetable_slot(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, academic_term,
):
    school.has_period_attendance = True
    day = _weekday_of(academic_term.start_date)
    await _make_period(db_session, school, day)  # no TimetableSlot
    cal = await _make_calendar_day(db_session, school, academic_term.start_date, academic_term.id)

    resp = await client.get(
        "/attendance/period-marking-status", params={"calendar_id": str(cal.id)}, headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_period_marking_status_shows_unmarked_then_marked(
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

    resp = await client.get(
        "/attendance/period-marking-status", params={"calendar_id": str(cal.id)}, headers=auth,
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["class_id"] == str(school_class.id)
    assert rows[0]["period_id"] == str(period.id)
    assert rows[0]["subject_name"] == subject.name
    assert rows[0]["marked"] is False

    await client.post("/attendance/mark", json={
        "school_calendar_id": str(cal.id), "class_id": str(school_class.id),
        "period_id": str(period.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=auth)

    resp = await client.get(
        "/attendance/period-marking-status", params={"calendar_id": str(cal.id)}, headers=auth,
    )
    assert resp.json()[0]["marked"] is True


@pytest.mark.asyncio
async def test_period_marking_status_unmarked_sorts_first(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, academic_term, staff_member: StaffMember,
    student: Student,
):
    school.has_period_attendance = True
    day = _weekday_of(academic_term.start_date)
    other_class = Class(school_id=school.id, level="SHS", year_group=2, stream="B", is_active=True)
    db_session.add(other_class)
    await db_session.flush()

    _, period_a = await _setup_timetabled_period(
        db_session, school, school_class, academic_year, staff_member, day=day, code="MATH",
    )
    _, period_b = await _setup_timetabled_period(
        db_session, school, other_class, academic_year, staff_member, day=day, code="ENG", number=2,
    )
    cal = await _make_calendar_day(db_session, school, academic_term.start_date, academic_term.id)

    await client.post("/attendance/mark", json={
        "school_calendar_id": str(cal.id), "class_id": str(school_class.id),
        "period_id": str(period_a.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=auth)

    resp = await client.get(
        "/attendance/period-marking-status", params={"calendar_id": str(cal.id)}, headers=auth,
    )
    rows = resp.json()
    assert len(rows) == 2
    assert rows[0]["period_id"] == str(period_b.id)  # unmarked first
    assert rows[0]["marked"] is False
    assert rows[1]["period_id"] == str(period_a.id)
    assert rows[1]["marked"] is True


@pytest.mark.asyncio
async def test_period_marking_status_scoped_to_own_class_teacher_assignment(
    client: AsyncClient, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, academic_term, staff_member: StaffMember,
    redis_permissions: None,
):
    """A scoped caller (ClassTeacher of one class, no attendance.approve)
    only sees their own class' period rows — the other class' is invisible,
    not just unmarked."""
    school.has_period_attendance = True
    day = _weekday_of(academic_term.start_date)

    other_class = Class(school_id=school.id, level="SHS", year_group=2, stream="B", is_active=True)
    db_session.add(other_class)
    other_staff = StaffMember(school_id=school.id, staff_number="OTH003", first_name="Other", last_name="Teacher", is_active=True)
    db_session.add(other_staff)
    await db_session.flush()

    await _setup_timetabled_period(
        db_session, school, school_class, academic_year, staff_member, day=day, code="MATH",
    )
    await _setup_timetabled_period(
        db_session, school, other_class, academic_year, other_staff, day=day, code="ENG", number=2,
    )
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_member.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()
    cal = await _make_calendar_day(db_session, school, academic_term.start_date, academic_term.id)

    ct_auth = await _teacher_login(client, db_session, school, staff_member)
    resp = await client.get(
        "/attendance/period-marking-status", params={"calendar_id": str(cal.id)}, headers=ct_auth,
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["class_id"] == str(school_class.id)
