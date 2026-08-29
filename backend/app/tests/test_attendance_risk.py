"""
Chronic-absenteeism early warning — services/attendance_risk.py.
Run inside Docker: docker compose exec api pytest app/tests/test_attendance_risk.py -v
"""
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class, ClassTeacher
from app.models.attendance import AttendanceRecord, AttendanceRiskAlert, AttendanceRiskTier, AttendanceStatus, DayType, SchoolCalendar
from app.models.school import School
from app.models.students import Student, StudentClassAssignment
from app.services.attendance_risk import compute_risk_tier


# ── Pure tier-boundary unit tests ───────────────────────────────────────────

def test_compute_risk_tier_below_minimum_days_is_none():
    assert compute_risk_tier(present=0, total=9) is None
    assert compute_risk_tier(present=9, total=9) is None


def test_compute_risk_tier_boundaries():
    assert compute_risk_tier(present=20, total=20) is None       # 100%
    assert compute_risk_tier(present=19, total=20) is None       # 95% — not < 95
    assert compute_risk_tier(present=18, total=20) == AttendanceRiskTier.WATCH     # 90% — not <90, but <95
    assert compute_risk_tier(present=17, total=20) == AttendanceRiskTier.AT_RISK   # 85%
    assert compute_risk_tier(present=8,  total=10) == AttendanceRiskTier.AT_RISK   # 80% — not <80, but <90
    assert compute_risk_tier(present=7,  total=10) == AttendanceRiskTier.SEVERE    # 70%


# ── Integration helpers ─────────────────────────────────────────────────────

async def _make_markable_days(
    db_session: AsyncSession, school: School, academic_term: AcademicTerm, n: int,
) -> list[SchoolCalendar]:
    days = []
    for i in range(n):
        cal = SchoolCalendar(
            school_id=school.id, date=date(2024, 9, 2 + i),
            day_type=DayType.SCHOOL_DAY, academic_term_id=academic_term.id,
        )
        db_session.add(cal)
        days.append(cal)
    await db_session.flush()
    return days


async def _record(
    db_session: AsyncSession, school: School, student: Student, school_class: Class,
    cal: SchoolCalendar, status: AttendanceStatus, recorded_by_id,
) -> None:
    db_session.add(AttendanceRecord(
        school_id=school.id, student_id=student.id, school_calendar_id=cal.id,
        class_id=school_class.id, status=status, recorded_by_id=recorded_by_id,
        recorded_at=datetime.now(timezone.utc),
    ))


async def _assign_student_to_class(db_session, school, student, school_class, academic_term):
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=school_class.id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()


@pytest.mark.asyncio
async def test_at_risk_list_excludes_below_minimum_markable_days(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, student: Student, academic_term: AcademicTerm,
):
    """Even 0% attendance must not appear before the 10-markable-day floor —
    a 5-day-old term's percentage is noise, not signal."""
    from app.models.auth import User
    recorder = await db_session.scalar(select(User).limit(1))
    await _assign_student_to_class(db_session, school, student, school_class, academic_term)
    days = await _make_markable_days(db_session, school, academic_term, 5)
    for cal in days:
        await _record(db_session, school, student, school_class, cal, AttendanceStatus.ABSENT, recorder.id)
    await db_session.flush()

    resp = await client.get(
        f"/attendance/at-risk?term_id={academic_term.id}", headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_at_risk_list_shows_severe_and_excludes_good_attendance(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, student: Student, academic_term: AcademicTerm,
):
    from app.models.auth import User
    recorder = await db_session.scalar(select(User).limit(1))
    await _assign_student_to_class(db_session, school, student, school_class, academic_term)

    good_student = Student(
        school_id=school.id, admission_number="STU-GOOD", first_name="Ama", last_name="Owusu", is_active=True,
    )
    db_session.add(good_student)
    await db_session.flush()
    await _assign_student_to_class(db_session, school, good_student, school_class, academic_term)

    days = await _make_markable_days(db_session, school, academic_term, 10)
    for i, cal in enumerate(days):
        # student: 2 present, 8 absent -> 20% -> SEVERE
        await _record(db_session, school, student, school_class, cal,
                      AttendanceStatus.PRESENT if i < 2 else AttendanceStatus.ABSENT, recorder.id)
        # good_student: all present -> 100% -> not listed
        await _record(db_session, school, good_student, school_class, cal, AttendanceStatus.PRESENT, recorder.id)
    await db_session.flush()

    resp = await client.get(f"/attendance/at-risk?term_id={academic_term.id}", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    by_id = {r["student_id"]: r for r in data}
    assert str(student.id) in by_id
    assert by_id[str(student.id)]["tier"] == "SEVERE"
    assert by_id[str(student.id)]["rate"] == 20.0
    assert str(good_student.id) not in by_id


@pytest.mark.asyncio
async def test_at_risk_list_scoped_to_class_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, student: Student, academic_term: AcademicTerm, redis_permissions: None,
):
    from app.models.auth import User
    from app.tests.test_attendance import _login_as_position
    recorder = await db_session.scalar(select(User).limit(1))
    await _assign_student_to_class(db_session, school, student, school_class, academic_term)
    days = await _make_markable_days(db_session, school, academic_term, 10)
    for cal in days:
        await _record(db_session, school, student, school_class, cal, AttendanceStatus.ABSENT, recorder.id)
    await db_session.flush()

    other_class = Class(school_id=school.id, level="SHS", year_group=1, stream="B", is_active=True)
    db_session.add(other_class)
    await db_session.flush()

    teacher_auth, teacher_staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=other_class.id, staff_member_id=teacher_staff_id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.get(f"/attendance/at-risk?term_id={academic_term.id}", headers=teacher_auth)
    assert resp.status_code == 200
    assert resp.json() == []  # the at-risk student is in a different class


# ── Notification dedup / tier escalation ────────────────────────────────────

@pytest.mark.asyncio
async def test_risk_alert_written_once_per_tier_and_escalates(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, student: Student, academic_term: AcademicTerm,
):
    """10 days at 80% (AT_RISK) should write one alert row at AT_RISK; adding
    enough absences to cross into SEVERE should update the SAME row (not a
    second one) to SEVERE."""
    await _assign_student_to_class(db_session, school, student, school_class, academic_term)
    days = await _make_markable_days(db_session, school, academic_term, 10)

    # First 10 days: 2 absent, 8 present -> 80% -> AT_RISK (not <80, but <90)
    for i, cal in enumerate(days):
        status = "ABSENT" if i < 2 else "PRESENT"
        resp = await client.post("/attendance/mark", json={
            "school_calendar_id": str(cal.id), "class_id": str(school_class.id),
            "records": [{"student_id": str(student.id), "status": status}],
        }, headers=auth)
        assert resp.status_code == 201

    alerts = (await db_session.scalars(
        select(AttendanceRiskAlert).where(AttendanceRiskAlert.student_id == student.id)
    )).all()
    assert len(alerts) == 1
    assert alerts[0].tier == AttendanceRiskTier.AT_RISK

    # Add 2 more markable days, both absent -> 8 present / 12 total = 66.7% -> SEVERE
    more_days = [
        SchoolCalendar(school_id=school.id, date=date(2024, 9, 20 + i),
                        day_type=DayType.SCHOOL_DAY, academic_term_id=academic_term.id)
        for i in range(2)
    ]
    db_session.add_all(more_days)
    await db_session.flush()
    for cal in more_days:
        resp = await client.post("/attendance/mark", json={
            "school_calendar_id": str(cal.id), "class_id": str(school_class.id),
            "records": [{"student_id": str(student.id), "status": "ABSENT"}],
        }, headers=auth)
        assert resp.status_code == 201

    alerts = (await db_session.scalars(
        select(AttendanceRiskAlert).where(AttendanceRiskAlert.student_id == student.id)
    )).all()
    assert len(alerts) == 1, "must update the same row, not insert a second one"
    assert alerts[0].tier == AttendanceRiskTier.SEVERE


# ── Consecutive-absence trigger ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_consecutive_absences(
    db_session: AsyncSession, school: School, student: Student, school_class: Class,
    academic_term: AcademicTerm,
):
    from app.models.auth import User
    from app.services.attendance_risk import check_consecutive_absences
    recorder = await db_session.scalar(select(User).limit(1))
    days = await _make_markable_days(db_session, school, academic_term, 3)

    # Only 2 of 3 absent so far
    await _record(db_session, school, student, school_class, days[0], AttendanceStatus.ABSENT, recorder.id)
    await _record(db_session, school, student, school_class, days[1], AttendanceStatus.ABSENT, recorder.id)
    await db_session.flush()
    assert await check_consecutive_absences(student.id, days[1].id, school.id, db_session) is False

    # Third consecutive absence
    await _record(db_session, school, student, school_class, days[2], AttendanceStatus.ABSENT, recorder.id)
    await db_session.flush()
    assert await check_consecutive_absences(student.id, days[2].id, school.id, db_session) is True
