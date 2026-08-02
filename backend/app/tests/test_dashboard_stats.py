"""
Dashboard stat-accuracy regression tests.

Covers three bugs found in review, all in services/dashboard.py /
dashboard_admin.py / dashboard_teacher.py:
  1. "Pending approvals" (admin + approver views) counted every unapproved
     Score in the school's history, never scoped to the current term.
  2. The admin view's present_map query didn't filter
     StudentClassAssignment.is_active, so a student withdrawn the same day
     attendance was taken still counted toward their old class's present total.
  3. The teacher view's attendance_marked_today only recognised PRESENT/ABSENT,
     so a class marked entirely LATE/EXCUSED read as "not yet marked".

Run inside Docker: docker compose exec api pytest app/tests/test_dashboard_stats.py -v
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import (
    AcademicTerm, AcademicYear, Class, ClassTeacher,
    SchoolLevel, Subject, SubjectCatalogue, SubjectType,
)
from app.models.assessments import Assessment, AssessmentType, Score
from app.models.attendance import AttendanceRecord, AttendanceStatus, DayType, SchoolCalendar
from app.models.auth import LoginType, StaffPosition, User
from app.models.school import School
from app.models.staff import StaffMember
from app.models.students import Student, StudentClassAssignment


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


async def _teacher_login(
    client: AsyncClient, db_session: AsyncSession, school: School, staff: StaffMember,
) -> dict:
    email = f"{staff.staff_number.lower()}@presec-test.edu.gh"
    db_session.add(User(
        school_id=school.id, login_type=LoginType.EMAIL, email=email,
        password_hash=hash_password("Whatever123!"), is_active=True, staff_member_id=staff.id,
    ))
    await db_session.flush()
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL", "identifier": email, "password": "Whatever123!",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _unapproved_score(
    db_session: AsyncSession, school: School, cls: Class, term: AcademicTerm,
    student: Student, entered_by: User, suffix: str,
) -> Score:
    """Insert one Score with is_approved=False under a fresh Assessment/Subject/
    AssessmentType for `term`, bypassing the API (dashboard tests only care about
    what get_dashboard() reads, not create_assessment()'s own eligibility rules)."""
    cat = SubjectCatalogue(
        name=f"Subject {suffix}", code=f"SUB_{suffix}", subject_type=SubjectType.CORE, level=SchoolLevel.SHS,
    )
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code=f"SUB_{suffix}", name=f"Subject {suffix}", is_active=True)
    db_session.add(subj)
    await db_session.flush()

    atype = AssessmentType(school_id=school.id, name=f"Test {suffix}", code=f"CT_{suffix}", weight=Decimal("30.00"))
    db_session.add(atype)
    await db_session.flush()

    assessment = Assessment(
        school_id=school.id, class_id=cls.id, subject_id=subj.id,
        assessment_type_id=atype.id, academic_term_id=term.id,
        description=f"Assessment {suffix}", recorded_date=date.today(), max_score=Decimal("100.00"),
    )
    db_session.add(assessment)
    await db_session.flush()

    score = Score(
        school_id=school.id, assessment_id=assessment.id, student_id=student.id,
        raw_score=Decimal("70.00"), entered_by_id=entered_by.id,
    )
    db_session.add(score)
    await db_session.flush()
    return score


# ── "Pending approvals" must be scoped to the current term ─────────────────────

@pytest.mark.asyncio
async def test_approver_dashboard_pending_scoped_to_current_term(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_admin: User, academic_year: AcademicYear, academic_term: AcademicTerm,
    school_class: Class, student: Student, redis_permissions: None,
):
    past_term = AcademicTerm(
        school_id=school.id, academic_year_id=academic_year.id,
        term_number=3, name="Old Term", start_date=date(2023, 1, 1), end_date=date(2023, 4, 1),
        is_current=False,
    )
    db_session.add(past_term)
    await db_session.flush()

    await _unapproved_score(db_session, school, school_class, past_term, student, school_admin, "APR_OLD")
    await _unapproved_score(db_session, school, school_class, academic_term, student, school_admin, "APR_CUR")

    hod_auth = await _login_as_position(client, auth, db_session, school, "HOD")
    resp = await client.get("/dashboard", headers=hod_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["view"] == "approver"
    assert data["pending_approvals"] == 1
    assert data["assessments_this_term"] == 1


@pytest.mark.asyncio
async def test_admin_dashboard_pending_scoped_to_current_term(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_admin: User, academic_year: AcademicYear, academic_term: AcademicTerm,
    school_class: Class, student: Student, redis_permissions: None,
):
    past_term = AcademicTerm(
        school_id=school.id, academic_year_id=academic_year.id,
        term_number=3, name="Old Term", start_date=date(2023, 1, 1), end_date=date(2023, 4, 1),
        is_current=False,
    )
    db_session.add(past_term)
    await db_session.flush()

    await _unapproved_score(db_session, school, school_class, past_term, student, school_admin, "ADM_OLD")
    await _unapproved_score(db_session, school, school_class, academic_term, student, school_admin, "ADM_CUR")

    head_auth = await _login_as_position(client, auth, db_session, school, "HEAD")
    resp = await client.get("/dashboard", headers=head_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["view"] == "admin"
    assert data["pending_approvals"] == 1


# ── Admin attendance stat must not count a withdrawn student's stale record ───

@pytest.mark.asyncio
async def test_admin_dashboard_excludes_present_count_for_withdrawn_assignment(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_admin: User, academic_year: AcademicYear, academic_term: AcademicTerm,
    school_class: Class, student: Student, redis_permissions: None,
):
    # A second, still-active student keeps school_class in the class_rows widget
    # so the bug (present count surviving on a now-inactive assignment) has
    # somewhere to attach to.
    other_student = Student(
        school_id=school.id, admission_number="STU-OTHER", first_name="Ama", last_name="Boateng", is_active=True,
    )
    db_session.add(other_student)
    await db_session.flush()
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=other_student.id, class_id=school_class.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    sca = StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=school_class.id,
        academic_year_id=academic_year.id, is_active=True,
    )
    db_session.add(sca)
    await db_session.flush()

    cal = SchoolCalendar(
        school_id=school.id, date=date.today(), day_type=DayType.SCHOOL_DAY, academic_term_id=academic_term.id,
    )
    db_session.add(cal)
    await db_session.flush()

    db_session.add(AttendanceRecord(
        school_id=school.id, student_id=student.id, school_calendar_id=cal.id,
        class_id=school_class.id, status=AttendanceStatus.PRESENT, recorded_by_id=school_admin.id,
        recorded_at=datetime.now(timezone.utc),
    ))
    await db_session.flush()

    # Withdrawn later the same day, after attendance was already taken.
    sca.is_active = False
    await db_session.flush()

    head_auth = await _login_as_position(client, auth, db_session, school, "HEAD")
    resp = await client.get("/dashboard", headers=head_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["view"] == "admin"
    assert data["today_total"] == 1
    assert data["today_present"] == 0
    assert data["attendance_pct"] == 0.0


# ── Teacher dashboard: same is_active gap, plus LATE/EXCUSED "marked" gap ─────
# Both scenarios exercise dashboard_teacher.py's _class_snapshot(); combined into
# one dashboard call (one login) rather than two, to match the fixture shape.

@pytest.mark.asyncio
async def test_teacher_dashboard_class_snapshot_is_active_and_late_handling(
    client: AsyncClient, db_session: AsyncSession, school: School, staff_member: StaffMember,
    school_admin: User, academic_year: AcademicYear, academic_term: AcademicTerm, school_class: Class,
    student: Student, redis_permissions: None,
):
    other_student = Student(
        school_id=school.id, admission_number="STU-LATE", first_name="Kojo", last_name="Mensah", is_active=True,
    )
    db_session.add(other_student)
    await db_session.flush()

    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_member.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    # `student`'s assignment will be deactivated after being marked present today
    # (same-day withdrawal); `other_student` stays active and is marked LATE only.
    sca = StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=school_class.id,
        academic_year_id=academic_year.id, is_active=True,
    )
    db_session.add(sca)
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=other_student.id, class_id=school_class.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    cal = SchoolCalendar(
        school_id=school.id, date=date.today(), day_type=DayType.SCHOOL_DAY, academic_term_id=academic_term.id,
    )
    db_session.add(cal)
    await db_session.flush()

    db_session.add(AttendanceRecord(
        school_id=school.id, student_id=student.id, school_calendar_id=cal.id,
        class_id=school_class.id, status=AttendanceStatus.PRESENT, recorded_by_id=school_admin.id,
        recorded_at=datetime.now(timezone.utc),
    ))
    db_session.add(AttendanceRecord(
        school_id=school.id, student_id=other_student.id, school_calendar_id=cal.id,
        class_id=school_class.id, status=AttendanceStatus.LATE, recorded_by_id=school_admin.id,
        recorded_at=datetime.now(timezone.utc),
    ))
    await db_session.flush()

    sca.is_active = False
    await db_session.flush()

    auth = await _teacher_login(client, db_session, school, staff_member)
    resp = await client.get("/dashboard", headers=auth)
    assert resp.status_code == 200
    cls = resp.json()["my_classes"][0]
    # Only other_student's active assignment counts; student's stale present
    # record must not survive their withdrawal.
    assert cls["student_count"] == 1
    assert cls["present_today"] == 0
    # LATE alone still means the roster was marked today.
    assert cls["attendance_marked_today"] is True
    assert cls["absent_today"] == 0
