"""
Attendance trends + export — services/attendance_trends.py.
Run inside Docker: docker compose exec api pytest app/tests/test_attendance_trends.py -v
"""
import csv
import io
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from app.models.academic import AcademicTerm, Class, ClassTeacher
from app.models.attendance import AttendanceRecord, DayType, SchoolCalendar
from app.models.auth import User
from app.models.school import School
from app.models.students import Student, StudentClassAssignment

from app.tests.test_sync import _login_as_position


async def _assign_student_to_class(db_session, school, student, school_class, academic_term):
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=school_class.id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()


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


async def _record(db_session, school, student, school_class, cal, status, recorded_by_id):
    db_session.add(AttendanceRecord(
        school_id=school.id, student_id=student.id, school_calendar_id=cal.id,
        class_id=school_class.id, status=status, recorded_by_id=recorded_by_id,
        recorded_at=datetime.now(timezone.utc),
    ))


@pytest.mark.asyncio
async def test_trend_series_correct(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, student: Student, academic_term: AcademicTerm,
):
    recorder = await db_session.scalar(select(User).limit(1))
    await _assign_student_to_class(db_session, school, student, school_class, academic_term)
    days = await _make_markable_days(db_session, school, academic_term, 2, 3)
    await _record(db_session, school, student, school_class, days[0], "PRESENT", recorder.id)
    await _record(db_session, school, student, school_class, days[1], "ABSENT", recorder.id)
    # day 3 left unmarked
    await db_session.flush()

    resp = await client.get(f"/attendance/trends?term_id={academic_term.id}", headers=auth)
    assert resp.status_code == 200
    points = {p["date"]: p for p in resp.json()}
    assert points[str(days[0].date)]["present"] == 1
    assert points[str(days[0].date)]["total"] == 1
    assert points[str(days[0].date)]["rate"] == 100.0
    assert points[str(days[1].date)]["present"] == 0
    assert points[str(days[1].date)]["rate"] == 0.0
    assert points[str(days[2].date)]["present"] == 0  # unmarked day still appears, present=0


@pytest.mark.asyncio
async def test_trend_scoped_to_class_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, student: Student, academic_term: AcademicTerm, redis_permissions: None,
):
    await _assign_student_to_class(db_session, school, student, school_class, academic_term)
    await _make_markable_days(db_session, school, academic_term, 5, 1)

    other_class = Class(school_id=school.id, level="SHS", year_group=1, stream="B", is_active=True)
    db_session.add(other_class)
    await db_session.flush()

    teacher_auth, teacher_staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=other_class.id, staff_member_id=teacher_staff_id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()

    # This teacher doesn't teach school_class — no students in scope → empty.
    resp = await client.get(f"/attendance/trends?term_id={academic_term.id}", headers=teacher_auth)
    assert resp.status_code == 200
    assert resp.json() == []

    # Explicit class_id for a class outside their scope → 404.
    resp2 = await client.get(
        f"/attendance/trends?term_id={academic_term.id}&class_id={school_class.id}", headers=teacher_auth,
    )
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_export_csv_rows(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, student: Student, academic_term: AcademicTerm,
):
    recorder = await db_session.scalar(select(User).limit(1))
    await _assign_student_to_class(db_session, school, student, school_class, academic_term)
    days = await _make_markable_days(db_session, school, academic_term, 8, 2)
    await _record(db_session, school, student, school_class, days[0], "PRESENT", recorder.id)
    await _record(db_session, school, student, school_class, days[1], "ABSENT", recorder.id)
    await db_session.flush()

    resp = await client.get(f"/attendance/export?term_id={academic_term.id}&fmt=csv", headers=auth)
    assert resp.status_code == 200
    rows = list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))
    header, data_row = rows[0], rows[1]
    assert data_row[header.index("Admission Number")] == student.admission_number
    assert data_row[header.index("Present")] == "1"
    assert data_row[header.index("Absent")] == "1"
    assert data_row[header.index("Attendance Rate (%)")] == "50.0"


@pytest.mark.asyncio
async def test_export_pdf_and_excel(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, student: Student, academic_term: AcademicTerm,
):
    await _assign_student_to_class(db_session, school, student, school_class, academic_term)
    await _make_markable_days(db_session, school, academic_term, 10, 1)

    pdf_resp = await client.get(f"/attendance/export?term_id={academic_term.id}&fmt=pdf", headers=auth)
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"

    excel_resp = await client.get(f"/attendance/export?term_id={academic_term.id}&fmt=excel", headers=auth)
    assert excel_resp.status_code == 200
    assert "spreadsheetml" in excel_resp.headers["content-type"]


@pytest.mark.asyncio
async def test_export_rejects_unknown_format(client: AsyncClient, auth: dict, academic_term: AcademicTerm):
    resp = await client.get(f"/attendance/export?term_id={academic_term.id}&fmt=xml", headers=auth)
    assert resp.status_code == 422
