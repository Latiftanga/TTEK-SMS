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
from app.models.academic import AcademicTerm, Class, ClassTeacher
from app.models.attendance import AttendanceAuditLog, DayType, SchoolCalendar
from app.models.auth import LoginType, PositionPermission, StaffPosition, User
from app.models.school import GhanaDistrict, GhanaRegion, School, SchoolType
from app.models.students import Student, StudentClassAssignment
from app.tests.legacy_position_perms import LEGACY_POSITION_PERMISSIONS


async def _login_as_position(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, position_code: str,
) -> tuple[dict, str]:
    """Create a staff member holding `position_code`, give them a login, and return
    (their bearer-token auth headers, their staff_member id) — mirrors
    test_scoring_lock.py's helper."""
    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == position_code))
    if pos is None and position_code in LEGACY_POSITION_PERMISSIONS:
        pos = StaffPosition(school_id=school.id, code=position_code, name=position_code.title(), is_template=False)
        db_session.add(pos)
        await db_session.flush()
        for module, action in LEGACY_POSITION_PERMISSIONS[position_code]:
            db_session.add(PositionPermission(position_id=pos.id, module=module, action=action, is_allowed=True))
        await db_session.flush()
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
        "school_code": school.school_code,
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, staff_id


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
    resp = await client.post("/auth/superadmin-login", json={
        "identifier": "other-admin@test.gh", "password": "pw",
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
async def test_generate_calendar_rejects_overlapping_term(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school: School, academic_term: AcademicTerm,
):
    """school_calendar is uniquely constrained on (school_id, date) — a
    calendar date can only ever belong to one term. Two terms whose date
    ranges overlap (e.g. a school mid-transition between academic years,
    or a term-dates typo) must not crash with a raw IntegrityError when the
    second term's calendar is generated — this is the real scenario that
    happened live: 'Semester 2' 2026-06-01..08-31 and a new-year 'Semester 1'
    2026-08-01..11-30 both claiming August."""
    await client.post("/attendance/calendar/generate", json={
        "term_id": str(academic_term.id),
    }, headers=auth)

    overlapping_term = AcademicTerm(
        school_id=school.id, academic_year_id=academic_term.academic_year_id,
        term_number=2, name="Overlapping Term",
        start_date=date(2024, 12, 1), end_date=date(2025, 3, 31), is_current=False,
    )
    db_session.add(overlapping_term)
    await db_session.flush()

    resp = await client.post("/attendance/calendar/generate", json={
        "term_id": str(overlapping_term.id),
    }, headers=auth)
    assert resp.status_code == 409
    assert "already belong to another term" in resp.json()["detail"]

    # No partial writes — zero calendar rows created for the rejected term.
    orphaned = await db_session.scalar(
        select(SchoolCalendar).where(SchoolCalendar.academic_term_id == overlapping_term.id)
    )
    assert orphaned is None


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


@pytest.mark.asyncio
async def test_mark_attendance_rejects_inactive_class(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school_calendar: SchoolCalendar, school_class: Class, student: Student,
):
    """A retired class (Class.is_active=False) shouldn't accept new
    attendance marks any more than a locked term does."""
    school_class.is_active = False
    await db_session.commit()

    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=auth)
    assert resp.status_code == 422
    assert "inactive" in resp.json()["detail"].lower()


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

    hod_auth, hod_staff_id = await _login_as_position(client, auth, db_session, school, "HOD")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=hod_staff_id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()
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

    teacher_auth, teacher_staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=teacher_staff_id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()
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


# ── Class-teacher scoping ──────────────────────────────────────────────────────
# A CLASS_TEACHER holds attendance.record but should only be able to mark/view
# attendance for class(es) they are the ClassTeacher of — matches the user's
# own framing ("the teacher should see only the class(s) assigned to that
# teacher as class_teacher to mark attendance").

@pytest.mark.asyncio
async def test_mark_attendance_404_for_non_owning_class_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_calendar: SchoolCalendar, school_class: Class, student: Student, redis_permissions: None,
):
    teacher_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=teacher_auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_mark_attendance_allowed_for_owning_class_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_calendar: SchoolCalendar, school_class: Class, student: Student,
    academic_term: AcademicTerm, redis_permissions: None,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=teacher_auth)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_my_attendance_classes_scoped_to_own_class_teacher_assignment(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_term: AcademicTerm, redis_permissions: None,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")

    empty = await client.get(f"/attendance/my-classes?term_id={academic_term.id}", headers=teacher_auth)
    assert empty.status_code == 200
    assert empty.json() == []

    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.get(f"/attendance/my-classes?term_id={academic_term.id}", headers=teacher_auth)
    assert resp.status_code == 200
    assert [c["id"] for c in resp.json()] == [str(school_class.id)]


@pytest.mark.asyncio
async def test_my_attendance_classes_unrestricted_for_admin(
    client: AsyncClient, auth: dict, school_class: Class, academic_term: AcademicTerm,
):
    """The school_admin fixture is a superadmin — always unrestricted."""
    resp = await client.get(f"/attendance/my-classes?term_id={academic_term.id}", headers=auth)
    assert resp.status_code == 200
    assert any(c["id"] == str(school_class.id) for c in resp.json())


# ── Current-term lock for marking ──────────────────────────────────────────────
# A class teacher may only mark attendance for the term admins have set as
# current — going back to a previous term doesn't make sense for them.

@pytest.mark.asyncio
async def test_mark_attendance_422_for_non_current_term(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_term: AcademicTerm, student: Student, redis_permissions: None,
):
    non_current_term = AcademicTerm(
        school_id=school.id, academic_year_id=academic_term.academic_year_id,
        term_number=2, name="Term 2",
        start_date=date(2025, 1, 1), end_date=date(2025, 4, 1), is_current=False,
    )
    db_session.add(non_current_term)
    await db_session.flush()
    past_cal = SchoolCalendar(
        school_id=school.id, date=date(2025, 1, 6),
        day_type=DayType.SCHOOL_DAY, academic_term_id=non_current_term.id,
    )
    db_session.add(past_cal)
    await db_session.flush()

    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(past_cal.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=teacher_auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_mark_attendance_unrestricted_for_attendance_approve_holder(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_term: AcademicTerm, student: Student, redis_permissions: None,
):
    """HEAD holds attendance.approve — can mark any term, current or not."""
    non_current_term = AcademicTerm(
        school_id=school.id, academic_year_id=academic_term.academic_year_id,
        term_number=2, name="Term 2",
        start_date=date(2025, 1, 1), end_date=date(2025, 4, 1), is_current=False,
    )
    db_session.add(non_current_term)
    await db_session.flush()
    past_cal = SchoolCalendar(
        school_id=school.id, date=date(2025, 1, 6),
        day_type=DayType.SCHOOL_DAY, academic_term_id=non_current_term.id,
    )
    db_session.add(past_cal)
    await db_session.flush()

    head_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "HEAD")
    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(past_cal.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=head_auth)
    assert resp.status_code == 201


# ── Duplicate-in-request / audit log (module review follow-up) ────────────────

@pytest.mark.asyncio
async def test_mark_attendance_rejects_duplicate_student_in_request(
    client: AsyncClient, auth: dict,
    school_calendar: SchoolCalendar, school_class: Class, student: Student,
):
    """Regression: two records for the same student in one payload previously
    both saw no existing row (autoflush is off) and both tried to INSERT,
    surfacing as a raw 500 on the unique constraint instead of a clean 422."""
    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [
            {"student_id": str(student.id), "status": "PRESENT"},
            {"student_id": str(student.id), "status": "ABSENT"},
        ],
    }, headers=auth)
    assert resp.status_code == 422
    assert str(student.id) in resp.json()["detail"]


@pytest.mark.asyncio
async def test_mark_attendance_locked_term_override_writes_audit_log(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_calendar: SchoolCalendar, school_class: Class, student: Student,
    academic_term: AcademicTerm, redis_permissions: None,
):
    """Regression: check_term_lock_override()'s resolved reason was validated
    then discarded — a locked-term override left zero record of who did it
    or why, unlike every sibling flow (Scoring/Assessment/Behaviour)."""
    academic_term.results_locked = True
    await db_session.flush()

    hod_auth, hod_staff_id = await _login_as_position(client, auth, db_session, school, "HOD")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=hod_staff_id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()
    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
        "override_reason": "Late correction approved",
    }, headers=hod_auth)
    assert resp.status_code == 201
    record_id = resp.json()[0]["id"]

    logs = (await db_session.scalars(
        select(AttendanceAuditLog).where(AttendanceAuditLog.student_id == student.id)
    )).all()
    assert len(logs) == 1
    assert logs[0].reason == "Late correction approved"
    assert logs[0].status.value == "PRESENT"
    assert str(logs[0].attendance_record_id) == record_id
    assert str(logs[0].class_id) == str(school_class.id)


@pytest.mark.asyncio
async def test_mark_attendance_no_audit_log_when_term_not_locked(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school_calendar: SchoolCalendar, school_class: Class, student: Student,
):
    resp = await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "PRESENT"}],
    }, headers=auth)
    assert resp.status_code == 201

    logs = (await db_session.scalars(
        select(AttendanceAuditLog).where(AttendanceAuditLog.student_id == student.id)
    )).all()
    assert logs == []


# ── Attendance-rate formula consistency ────────────────────────────────────────

@pytest.mark.asyncio
async def test_attendance_summary_rate_counts_present_only(
    client: AsyncClient, auth: dict,
    school_calendar: SchoolCalendar, school_class: Class,
    student: Student, academic_term: AcademicTerm,
):
    """Regression: get_summary() previously counted LATE/EXCUSED toward the
    rate numerator, disagreeing with attendance_stats.py::compute_attendance_
    stats() (the single definition report_card.py/transcript.py are built on,
    which counts PRESENT only) — the same student's rate could genuinely
    differ between the live Attendance page and their report card."""
    await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "LATE"}],
    }, headers=auth)
    resp = await client.get(
        f"/attendance/summary?student_id={student.id}&term_id={academic_term.id}",
        headers=auth,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["days_late"] == 1
    assert data["attendance_rate"] == 0.0


# ── Cross-school / retired-entity ownership checks ──────────────────────────────

@pytest.mark.asyncio
async def test_get_summary_404_for_bogus_term(
    client: AsyncClient, auth: dict, student: Student,
):
    import uuid as _uuid
    resp = await client.get(
        f"/attendance/summary?student_id={student.id}&term_id={_uuid.uuid4()}",
        headers=auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_calendar_404_for_bogus_term(client: AsyncClient, auth: dict):
    import uuid as _uuid
    resp = await client.get(f"/attendance/calendar?term_id={_uuid.uuid4()}", headers=auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_override_calendar_day_notes_oversized_rejected(
    client: AsyncClient, auth: dict, school_calendar: SchoolCalendar,
):
    resp = await client.patch(f"/attendance/calendar/{school_calendar.id}", json={
        "day_type": "SCHOOL_HOLIDAY", "notes": "x" * 301,
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_class_summaries_excludes_withdrawn_student(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_calendar: SchoolCalendar, school_class: Class, student: Student,
    academic_term: AcademicTerm,
):
    """Regression: get_class_summaries() never filtered
    StudentClassAssignment.is_active — a student withdrawn/transferred out
    of the class mid-term (row deactivated, not deleted) stayed visible in
    their old class teacher's absence summary forever, the same stale-row
    shape as the report-card ranking bug fixed in 12u."""
    await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "ABSENT"}],
    }, headers=auth)

    assignment = StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=school_class.id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    )
    db_session.add(assignment)
    await db_session.flush()

    still_active = await client.get(
        f"/attendance/class-summaries?class_id={school_class.id}&term_id={academic_term.id}",
        headers=auth,
    )
    assert still_active.status_code == 200
    assert len(still_active.json()) == 1

    assignment.is_active = False
    await db_session.flush()

    withdrawn = await client.get(
        f"/attendance/class-summaries?class_id={school_class.id}&term_id={academic_term.id}",
        headers=auth,
    )
    assert withdrawn.status_code == 200
    assert withdrawn.json() == []


# ── Marking status ("who's marked, who hasn't") ─────────────────────────────

async def _assign_student_to_class(
    db_session: AsyncSession, school: School, student: Student,
    school_class: Class, academic_term: AcademicTerm,
) -> None:
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=school_class.id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()


@pytest.mark.asyncio
async def test_marking_status_unmarked_class(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_calendar: SchoolCalendar, school_class: Class, student: Student,
    academic_term: AcademicTerm,
):
    await _assign_student_to_class(db_session, school, student, school_class, academic_term)

    resp = await client.get(
        f"/attendance/marking-status?calendar_id={school_calendar.id}", headers=auth,
    )
    assert resp.status_code == 200
    line = next(c for c in resp.json() if c["class_id"] == str(school_class.id))
    assert line["marked"] is False
    assert line["student_count"] == 1
    assert line["present"] == 0
    assert line["absent"] == 0
    assert line["class_teacher_name"] is None


@pytest.mark.asyncio
async def test_marking_status_flips_true_once_marked(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_calendar: SchoolCalendar, school_class: Class, student: Student,
    academic_term: AcademicTerm,
):
    await _assign_student_to_class(db_session, school, student, school_class, academic_term)

    await client.post("/attendance/mark", json={
        "school_calendar_id": str(school_calendar.id),
        "class_id": str(school_class.id),
        "records": [{"student_id": str(student.id), "status": "ABSENT"}],
    }, headers=auth)

    resp = await client.get(
        f"/attendance/marking-status?calendar_id={school_calendar.id}", headers=auth,
    )
    assert resp.status_code == 200
    line = next(c for c in resp.json() if c["class_id"] == str(school_class.id))
    assert line["marked"] is True
    assert line["present"] == 0
    assert line["absent"] == 1


@pytest.mark.asyncio
async def test_marking_status_reports_class_teacher_name(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_calendar: SchoolCalendar, school_class: Class, academic_term: AcademicTerm,
):
    staff_id = (await client.post("/staff", json={
        "staff_number": "TST-CT", "first_name": "Ama", "last_name": "Mensah",
    }, headers=auth)).json()["id"]
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.get(
        f"/attendance/marking-status?calendar_id={school_calendar.id}", headers=auth,
    )
    assert resp.status_code == 200
    line = next(c for c in resp.json() if c["class_id"] == str(school_class.id))
    assert line["class_teacher_name"] == "Ama Mensah"


@pytest.mark.asyncio
async def test_marking_status_scoped_to_own_class_teacher_assignment(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_calendar: SchoolCalendar, school_class: Class, academic_term: AcademicTerm,
    redis_permissions: None,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")

    empty = await client.get(
        f"/attendance/marking-status?calendar_id={school_calendar.id}", headers=teacher_auth,
    )
    assert empty.status_code == 200
    assert empty.json() == []

    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.get(
        f"/attendance/marking-status?calendar_id={school_calendar.id}", headers=teacher_auth,
    )
    assert resp.status_code == 200
    assert [c["class_id"] for c in resp.json()] == [str(school_class.id)]


@pytest.mark.asyncio
async def test_marking_status_404_for_bogus_calendar(client: AsyncClient, auth: dict):
    import uuid as _uuid
    resp = await client.get(
        f"/attendance/marking-status?calendar_id={_uuid.uuid4()}", headers=auth,
    )
    assert resp.status_code == 404
