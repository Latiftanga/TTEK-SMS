"""
Guardian/student absence excuse workflow — services/attendance_excuse.py.
Run inside Docker: docker compose exec api pytest app/tests/test_attendance_excuse.py -v
"""
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import AcademicTerm, Class, ClassTeacher
from app.models.attendance import AttendanceAuditLog, AttendanceRecord, AttendanceStatus, DayType, SchoolCalendar
from app.models.attendance_excuse import AbsenceExcuseRequest, ExcuseStatus
from app.models.auth import LoginType, User
from app.models.school import School
from app.models.students import Student, StudentClassAssignment

from app.tests.test_guardian_portal import _add_guardian, _guardian_login, _make_guardian_user
from app.tests.test_sync import _login_as_position, _portal_login


async def _make_markable_days(db_session, school, academic_term, start_day, n):
    days = []
    for i in range(n):
        cal = SchoolCalendar(
            school_id=school.id, date=date(2024, 9, start_day + i),
            day_type=DayType.SCHOOL_DAY, academic_term_id=academic_term.id,
        )
        db_session.add(cal)
        days.append(cal)
    await db_session.flush()
    return days


async def _assign_student_to_class(db_session, school, student, school_class, academic_term):
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=school_class.id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()


@pytest.mark.asyncio
async def test_student_submits_and_lists_own_excuse_request(
    client: AsyncClient, db_session: AsyncSession, school: School, student: Student,
):
    portal_auth = await _portal_login(client, db_session, school, student)
    resp = await client.post("/portal/excuse-requests", json={
        "start_date": "2024-09-02", "end_date": "2024-09-03", "reason": "Fever, saw a doctor.",
    }, headers=portal_auth)
    assert resp.status_code == 201
    assert resp.json()["status"] == "PENDING"

    listed = await client.get("/portal/excuse-requests", headers=portal_auth)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["reason"] == "Fever, saw a doctor."


@pytest.mark.asyncio
async def test_guardian_submits_for_linked_child(
    client: AsyncClient, db_session: AsyncSession, school: School, student: Student,
):
    guardian = await _add_guardian(db_session, school, student)
    await _make_guardian_user(db_session, school, guardian)
    guardian_auth = await _guardian_login(client, guardian, school)

    resp = await client.post(
        f"/portal/excuse-requests?student_id={student.id}",
        json={"start_date": "2024-09-02", "end_date": "2024-09-02", "reason": "Family emergency."},
        headers=guardian_auth,
    )
    assert resp.status_code == 201

    excuse = await db_session.scalar(select(AbsenceExcuseRequest).where(AbsenceExcuseRequest.student_id == student.id))
    assert excuse.guardian_id == guardian.id
    assert excuse.requested_by_user_id is not None


@pytest.mark.asyncio
async def test_guardian_cannot_submit_for_unrelated_student(
    client: AsyncClient, db_session: AsyncSession, school: School, student: Student,
):
    other_student = Student(school_id=school.id, admission_number="STU-OTHER", first_name="Ama", last_name="Boateng", is_active=True)
    db_session.add(other_student)
    await db_session.flush()

    guardian = await _add_guardian(db_session, school, student)  # linked to `student`, not `other_student`
    await _make_guardian_user(db_session, school, guardian)
    guardian_auth = await _guardian_login(client, guardian, school)

    resp = await client.post(
        f"/portal/excuse-requests?student_id={other_student.id}",
        json={"start_date": "2024-09-02", "end_date": "2024-09-02", "reason": "Not their child."},
        headers=guardian_auth,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_pending_list_scoped_to_class_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, student: Student, academic_term: AcademicTerm, redis_permissions: None,
):
    await _assign_student_to_class(db_session, school, student, school_class, academic_term)
    db_session.add(AbsenceExcuseRequest(
        school_id=school.id, student_id=student.id, requested_by_user_id=(await db_session.scalar(select(User).limit(1))).id,
        start_date=date(2024, 9, 2), end_date=date(2024, 9, 2), reason="Sick.",
    ))
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

    resp = await client.get("/attendance/excuse-requests", headers=teacher_auth)
    assert resp.status_code == 200
    assert resp.json() == []  # the request is for a student in a DIFFERENT class

    admin_resp = await client.get("/attendance/excuse-requests", headers=auth)
    assert admin_resp.status_code == 200
    assert len(admin_resp.json()) == 1


@pytest.mark.asyncio
async def test_approve_excuse_marks_range_excused(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, student: Student, academic_term: AcademicTerm,
):
    await _assign_student_to_class(db_session, school, student, school_class, academic_term)
    days = await _make_markable_days(db_session, school, academic_term, 2, 3)

    resp = await client.post("/portal/excuse-requests", json={
        "start_date": str(days[0].date), "end_date": str(days[-1].date), "reason": "Malaria.",
    }, headers=await _portal_login(client, db_session, school, student))
    assert resp.status_code == 201
    request_id = resp.json()["id"]

    review = await client.patch(f"/attendance/excuse-requests/{request_id}/review", json={
        "status": "APPROVED", "review_notes": "Confirmed with clinic note.",
    }, headers=auth)
    assert review.status_code == 200
    assert review.json()["status"] == "APPROVED"

    for cal in days:
        rec = await db_session.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.student_id == student.id, AttendanceRecord.school_calendar_id == cal.id,
            )
        )
        assert rec is not None
        assert rec.status == AttendanceStatus.EXCUSED


@pytest.mark.asyncio
async def test_reject_excuse_applies_no_attendance(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, student: Student, academic_term: AcademicTerm,
):
    await _assign_student_to_class(db_session, school, student, school_class, academic_term)
    days = await _make_markable_days(db_session, school, academic_term, 5, 1)

    resp = await client.post("/portal/excuse-requests", json={
        "start_date": str(days[0].date), "end_date": str(days[0].date), "reason": "Just checking.",
    }, headers=await _portal_login(client, db_session, school, student))
    request_id = resp.json()["id"]

    review = await client.patch(f"/attendance/excuse-requests/{request_id}/review", json={
        "status": "REJECTED", "review_notes": "No supporting evidence.",
    }, headers=auth)
    assert review.status_code == 200

    rec = await db_session.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.student_id == student.id, AttendanceRecord.school_calendar_id == days[0].id,
        )
    )
    assert rec is None


@pytest.mark.asyncio
async def test_review_already_reviewed_request_409(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, student: Student, academic_term: AcademicTerm,
):
    await _assign_student_to_class(db_session, school, student, school_class, academic_term)
    days = await _make_markable_days(db_session, school, academic_term, 6, 1)
    resp = await client.post("/portal/excuse-requests", json={
        "start_date": str(days[0].date), "end_date": str(days[0].date), "reason": "x",
    }, headers=await _portal_login(client, db_session, school, student))
    request_id = resp.json()["id"]
    await client.patch(f"/attendance/excuse-requests/{request_id}/review", json={"status": "REJECTED"}, headers=auth)

    second = await client.patch(f"/attendance/excuse-requests/{request_id}/review", json={"status": "APPROVED"}, headers=auth)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_approve_excuse_blocked_when_term_locked_without_reason(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, student: Student, academic_term: AcademicTerm,
):
    await _assign_student_to_class(db_session, school, student, school_class, academic_term)
    days = await _make_markable_days(db_session, school, academic_term, 7, 1)
    resp = await client.post("/portal/excuse-requests", json={
        "start_date": str(days[0].date), "end_date": str(days[0].date), "reason": "x",
    }, headers=await _portal_login(client, db_session, school, student))
    request_id = resp.json()["id"]

    lock = await client.patch(f"/academic/terms/{academic_term.id}", json={"results_locked": True}, headers=auth)
    assert lock.status_code == 200

    review = await client.patch(f"/attendance/excuse-requests/{request_id}/review", json={"status": "APPROVED"}, headers=auth)
    assert review.status_code == 423

    review_with_reason = await client.patch(f"/attendance/excuse-requests/{request_id}/review", json={
        "status": "APPROVED", "override_reason": "Backfilling after lock.",
    }, headers=auth)
    assert review_with_reason.status_code == 200

    rec = await db_session.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.student_id == student.id, AttendanceRecord.school_calendar_id == days[0].id,
        )
    )
    log = await db_session.scalar(
        select(AttendanceAuditLog).where(AttendanceAuditLog.attendance_record_id == rec.id)
    )
    assert log.reason == "Backfilling after lock."
