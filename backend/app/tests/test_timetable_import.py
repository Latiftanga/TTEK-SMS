"""
FET CSV timetable bulk-import tests — POST /academic/timetable/import.

Reuses school_class/academic_year/staff_member fixtures and the
_make_subject/_put_on_curriculum/_assign_teacher/_make_period helpers from
test_timetable.py, same convention test_lesson_plan_chat.py uses for
test_curriculum_materials.py's fixtures.

Run inside Docker: docker compose exec api pytest app/tests/test_timetable_import.py -v
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicYear, Class, Subject, SubjectTeacher, TimetableSlot
from app.models.school import School
from app.models.staff import StaffMember
from app.tests.test_attendance import _login_as_position, _other_school_auth
from app.tests.test_timetable import _assign_teacher, _make_period, _make_subject, _put_on_curriculum

_HEADER = "Day,Hour,Subject,Teacher(s),Students/Class(es)\n"


def _csv(*lines: str) -> bytes:
    return (_HEADER + "\n".join(lines)).encode("utf-8")


async def _import(client: AsyncClient, auth: dict, year: AcademicYear, csv_bytes: bytes):
    return await client.post(
        "/academic/timetable/import",
        params={"year_id": str(year.id)},
        files={"file": ("fet.csv", csv_bytes, "text/csv")},
        headers=auth,
    )


@pytest.mark.asyncio
async def test_valid_import_creates_slot(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, staff_member: StaffMember,
):
    subject = await _make_subject(db_session, school, "MATH")
    await _put_on_curriculum(db_session, school, school_class, subject)
    await _assign_teacher(db_session, school, school_class, subject, academic_year, staff_member)
    await _make_period(db_session, school, day="MON", number=1)

    resp = await _import(client, auth, academic_year, _csv(f"Monday,1,{subject.name},Mr X,2 A"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 1
    assert body["failed"] == 0

    resp = await client.get(
        f"/academic/classes/{school_class.id}/timetable",
        params={"year_id": str(academic_year.id)}, headers=auth,
    )
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["subject_id"] == str(subject.id)


@pytest.mark.asyncio
async def test_unmatched_class_name_reports_error_others_still_import(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, staff_member: StaffMember,
):
    subject = await _make_subject(db_session, school, "ENG")
    await _put_on_curriculum(db_session, school, school_class, subject)
    await _assign_teacher(db_session, school, school_class, subject, academic_year, staff_member)
    await _make_period(db_session, school, day="MON", number=1)
    await _make_period(db_session, school, day="MON", number=2, start="08:45:00", end="09:30:00")

    resp = await _import(client, auth, academic_year, _csv(
        f"Monday,1,{subject.name},Mr X,2 A",
        "Monday,2,Nonexistent Subject,Mr X,Nonexistent Class",
    ))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 1
    assert body["failed"] == 1
    assert "not found" in body["errors"][0]["error"]


@pytest.mark.asyncio
async def test_unmatched_subject_name_reports_error(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear,
):
    await _make_period(db_session, school, day="MON", number=1)

    resp = await _import(client, auth, academic_year, _csv("Monday,1,Nonexistent Subject,Mr X,2 A"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 0
    assert body["failed"] == 1
    assert "Subject" in body["errors"][0]["error"]


@pytest.mark.asyncio
async def test_missing_subject_teacher_reports_error(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear,
):
    subject = await _make_subject(db_session, school, "CHEM")
    await _put_on_curriculum(db_session, school, school_class, subject)
    await _make_period(db_session, school, day="MON", number=1)

    resp = await _import(client, auth, academic_year, _csv(f"Monday,1,{subject.name},Mr X,2 A"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 0
    assert body["failed"] == 1
    assert "no teacher assigned" in body["errors"][0]["error"]


@pytest.mark.asyncio
async def test_teacher_double_booking_reports_error_on_second_row(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, staff_member: StaffMember,
):
    other_class = Class(school_id=school.id, level="SHS", year_group=2, stream="B", is_active=True)
    db_session.add(other_class)
    await db_session.flush()

    subject_a = await _make_subject(db_session, school, "GEO")
    subject_b = await _make_subject(db_session, school, "HIST")
    await _put_on_curriculum(db_session, school, school_class, subject_a)
    await _put_on_curriculum(db_session, school, other_class, subject_b)
    await _assign_teacher(db_session, school, school_class, subject_a, academic_year, staff_member)
    await _assign_teacher(db_session, school, other_class, subject_b, academic_year, staff_member)
    await _make_period(db_session, school, day="MON", number=1)

    # Two SEPARATE source lines, not one line's multi-class expansion — a
    # single line sharing a teacher/period across classes is a deliberate
    # combined activity (see _load_booked's docstring), not a conflict, so
    # a genuine double-booking has to come from two distinct rows.
    resp = await _import(client, auth, academic_year, _csv(
        f"Monday,1,{subject_a.name},Mr X,2 A",
        f"Monday,1,{subject_b.name},Mr X,2 B",
    ))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 1
    assert body["failed"] == 1
    assert "already scheduled to teach" in body["errors"][0]["error"]


@pytest.mark.asyncio
async def test_malformed_header_csv_rejected_before_any_row_processed(
    client: AsyncClient, auth: dict, academic_year: AcademicYear,
):
    resp = await _import(client, auth, academic_year, b"Foo,Bar\nMon,1\n")
    assert resp.status_code == 422
    assert "Unexpected CSV columns" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_cross_school_isolation(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, staff_member: StaffMember,
):
    other_auth = await _other_school_auth(client, db_session)
    other_school = await db_session.scalar(select(School).where(School.school_code == "OTHER001"))

    subject = await _make_subject(db_session, school, "FRE")
    await _put_on_curriculum(db_session, school, school_class, subject)
    await _assign_teacher(db_session, school, school_class, subject, academic_year, staff_member)
    await _make_period(db_session, school, day="MON", number=1)

    # An identically-named class/subject in the OTHER school.
    other_class = Class(school_id=other_school.id, level="SHS", year_group=2, stream="A", is_active=True)
    db_session.add(other_class)
    await db_session.flush()
    other_subject = Subject(school_id=other_school.id, code="FRE", name=subject.name, is_active=True)
    db_session.add(other_subject)
    await db_session.flush()

    resp = await _import(client, other_auth, academic_year, _csv(f"Monday,1,{subject.name},Mr X,2 A"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # No matching period/curriculum/teacher assignment exists in the OTHER
    # school, so the identically-named class/subject must NOT resolve —
    # this row fails, not silently succeeds against the wrong school's row.
    assert body["created"] == 0
    assert body["failed"] == 1

    slots = list(await db_session.scalars(
        select(TimetableSlot).where(TimetableSlot.school_id == school.id)
    ))
    assert slots == []
    other_slots = list(await db_session.scalars(
        select(TimetableSlot).where(TimetableSlot.school_id == other_school.id)
    ))
    assert other_slots == []


@pytest.mark.asyncio
async def test_idempotent_reimport_updates_not_duplicates(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, staff_member: StaffMember,
):
    subject = await _make_subject(db_session, school, "BIO")
    await _put_on_curriculum(db_session, school, school_class, subject)
    await _assign_teacher(db_session, school, school_class, subject, academic_year, staff_member)
    await _make_period(db_session, school, day="MON", number=1)

    csv_bytes = _csv(f"Monday,1,{subject.name},Mr X,2 A")
    resp1 = await _import(client, auth, academic_year, csv_bytes)
    assert resp1.json()["created"] == 1

    resp2 = await _import(client, auth, academic_year, csv_bytes)
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["created"] == 1

    slots = list(await db_session.scalars(
        select(TimetableSlot).where(TimetableSlot.class_id == school_class.id)
    ))
    assert len(slots) == 1


@pytest.mark.asyncio
async def test_multi_class_row_expands_to_two_slots(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, staff_member: StaffMember,
):
    other_class = Class(school_id=school.id, level="SHS", year_group=2, stream="C", is_active=True)
    db_session.add(other_class)
    await db_session.flush()

    subject = await _make_subject(db_session, school, "ICT")
    await _put_on_curriculum(db_session, school, school_class, subject)
    await _put_on_curriculum(db_session, school, other_class, subject)
    await _assign_teacher(db_session, school, school_class, subject, academic_year, staff_member)
    await _assign_teacher(db_session, school, other_class, subject, academic_year, staff_member)
    await _make_period(db_session, school, day="MON", number=1)

    resp = await _import(client, auth, academic_year, _csv(f"Monday,1,{subject.name},Mr X,2 A;2 C"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Same teacher, same period, but DIFFERENT class per expanded row — this
    # is one shared activity across two classes, not a double-booking.
    assert body["created"] == 2
    assert body["failed"] == 0

    slots = list(await db_session.scalars(
        select(TimetableSlot).where(TimetableSlot.academic_year_id == academic_year.id)
    ))
    assert {s.class_id for s in slots} == {school_class.id, other_class.id}


@pytest.mark.asyncio
async def test_permission_denied_without_academic_edit(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, redis_permissions: None,
):
    teacher_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    resp = await _import(client, teacher_auth, academic_year, _csv("Monday,1,Math,Mr X,2 A"))
    assert resp.status_code == 403
