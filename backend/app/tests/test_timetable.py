"""
Class timetable tests — TimetableSlot CRUD, class/subject/teacher validation,
teacher double-booking, and the "what do I teach tomorrow" my-schedule read.

Run inside Docker: docker compose exec api pytest app/tests/test_timetable.py -v
"""
from datetime import time

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicYear, Class, ClassSubject, Subject, SubjectTeacher
from app.models.attendance import SchoolPeriod
from app.models.school import School
from app.models.staff import StaffMember
from app.tests.test_attendance import _login_as_position, _other_school_auth


async def _make_subject(db_session: AsyncSession, school: School, code: str) -> Subject:
    subject = Subject(school_id=school.id, code=code, name=f"{code} subject", is_active=True)
    db_session.add(subject)
    await db_session.flush()
    return subject


async def _put_on_curriculum(db_session: AsyncSession, school: School, cls: Class, subject: Subject) -> None:
    db_session.add(ClassSubject(school_id=school.id, class_id=cls.id, subject_id=subject.id, is_active=True))
    await db_session.flush()


async def _assign_teacher(
    db_session: AsyncSession, school: School, cls: Class, subject: Subject,
    year: AcademicYear, staff: StaffMember,
) -> None:
    db_session.add(SubjectTeacher(
        school_id=school.id, class_id=cls.id, subject_id=subject.id,
        staff_member_id=staff.id, academic_year_id=year.id, is_active=True,
    ))
    await db_session.flush()


def _t(s: str) -> time:
    h, m, sec = (int(p) for p in s.split(":"))
    return time(h, m, sec)


async def _make_period(
    db_session: AsyncSession, school: School, *, day="MON", number=1, start="08:00:00", end="08:45:00",
) -> SchoolPeriod:
    period = SchoolPeriod(
        school_id=school.id, name=f"Period {number}", day_of_week=day,
        period_number=number, start_time=_t(start), end_time=_t(end),
    )
    db_session.add(period)
    await db_session.flush()
    return period


@pytest.mark.asyncio
async def test_upsert_and_get_class_timetable(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, staff_member: StaffMember,
):
    subject = await _make_subject(db_session, school, "MATH")
    await _put_on_curriculum(db_session, school, school_class, subject)
    await _assign_teacher(db_session, school, school_class, subject, academic_year, staff_member)
    period = await _make_period(db_session, school)

    resp = await client.put(
        f"/academic/classes/{school_class.id}/timetable/{period.id}",
        json={"subject_id": str(subject.id)},
        params={"year_id": str(academic_year.id)},
        headers=auth,
    )
    assert resp.status_code == 200, resp.text
    slot = resp.json()
    assert slot["subject_id"] == str(subject.id)
    assert slot["staff_member_id"] == str(staff_member.id)
    assert slot["teacher_name"]

    resp = await client.get(
        f"/academic/classes/{school_class.id}/timetable",
        params={"year_id": str(academic_year.id)}, headers=auth,
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["period_id"] == str(period.id)


@pytest.mark.asyncio
async def test_upsert_auto_adds_subject_missing_from_curriculum(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, staff_member: StaffMember,
):
    """Scheduling a subject that isn't on the class's curriculum yet auto-adds
    it (as core) instead of rejecting the request — transcribing a printed
    timetable slot by slot shouldn't require a separate prior "add subject"
    step. Still requires a teacher (staff_member_id here) to actually place
    the slot, same as any other row."""
    subject = await _make_subject(db_session, school, "PHY")
    period = await _make_period(db_session, school)

    resp = await client.put(
        f"/academic/classes/{school_class.id}/timetable/{period.id}",
        json={"subject_id": str(subject.id), "staff_member_id": str(staff_member.id)},
        params={"year_id": str(academic_year.id)},
        headers=auth,
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(f"/academic/classes/{school_class.id}/subjects", headers=auth)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["subject_id"] == str(subject.id)
    assert rows[0]["is_elective"] is False


@pytest.mark.asyncio
async def test_upsert_auto_adds_curriculum_but_still_requires_a_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear,
):
    """The curriculum auto-add happens before the teacher gate, so a request
    with no staff_member_id and no prior teacher still 422s — but the
    subject is added to the curriculum regardless of that later failure."""
    subject = await _make_subject(db_session, school, "CRS")
    period = await _make_period(db_session, school)

    resp = await client.put(
        f"/academic/classes/{school_class.id}/timetable/{period.id}",
        json={"subject_id": str(subject.id)},
        params={"year_id": str(academic_year.id)},
        headers=auth,
    )
    assert resp.status_code == 422
    assert resp.headers["x-error-code"] == "no_teacher_assigned"

    resp = await client.get(f"/academic/classes/{school_class.id}/subjects", headers=auth)
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_upsert_rejects_unknown_subject_id(
    client: AsyncClient, auth: dict, school_class: Class, academic_year: AcademicYear, db_session: AsyncSession, school: School,
):
    period = await _make_period(db_session, school)
    resp = await client.put(
        f"/academic/classes/{school_class.id}/timetable/{period.id}",
        json={"subject_id": "00000000-0000-0000-0000-000000000000"},
        params={"year_id": str(academic_year.id)},
        headers=auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upsert_rejects_subject_from_other_school(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear,
):
    await _other_school_auth(client, db_session)
    other_school = await db_session.scalar(select(School).where(School.school_code == "OTHER001"))
    other_subject = await _make_subject(db_session, other_school, "OTH")
    period = await _make_period(db_session, school)

    resp = await client.put(
        f"/academic/classes/{school_class.id}/timetable/{period.id}",
        json={"subject_id": str(other_subject.id)},
        params={"year_id": str(academic_year.id)},
        headers=auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upsert_rejects_no_teacher_assigned(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear,
):
    subject = await _make_subject(db_session, school, "CHEM")
    await _put_on_curriculum(db_session, school, school_class, subject)
    period = await _make_period(db_session, school)

    resp = await client.put(
        f"/academic/classes/{school_class.id}/timetable/{period.id}",
        json={"subject_id": str(subject.id)},
        params={"year_id": str(academic_year.id)},
        headers=auth,
    )
    assert resp.status_code == 422
    assert resp.headers["x-error-code"] == "no_teacher_assigned"


@pytest.mark.asyncio
async def test_upsert_with_staff_member_id_creates_subject_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, staff_member: StaffMember,
):
    """The class-detail Timetable tab's combined slot editor: no prior
    SubjectTeacher exists, but supplying staff_member_id atomically creates
    it and places the slot in the same request."""
    subject = await _make_subject(db_session, school, "ICT")
    await _put_on_curriculum(db_session, school, school_class, subject)
    period = await _make_period(db_session, school)

    resp = await client.put(
        f"/academic/classes/{school_class.id}/timetable/{period.id}",
        json={"subject_id": str(subject.id), "staff_member_id": str(staff_member.id)},
        params={"year_id": str(academic_year.id)}, headers=auth,
    )
    assert resp.status_code == 200, resp.text
    slot = resp.json()
    assert slot["staff_member_id"] == str(staff_member.id)

    resp = await client.get(
        f"/academic/classes/{school_class.id}/subject-teachers",
        params={"year_id": str(academic_year.id)}, headers=auth,
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["subject_id"] == str(subject.id)
    assert rows[0]["staff_member_id"] == str(staff_member.id)
    assert rows[0]["is_active"] is True


@pytest.mark.asyncio
async def test_upsert_omitted_staff_member_id_keeps_existing_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, staff_member: StaffMember,
):
    """Back-compat path: omitting staff_member_id (e.g. the bulk CSV import,
    or any other caller) still succeeds against an already-assigned teacher,
    unchanged."""
    subject = await _make_subject(db_session, school, "GOV")
    await _put_on_curriculum(db_session, school, school_class, subject)
    await _assign_teacher(db_session, school, school_class, subject, academic_year, staff_member)
    period = await _make_period(db_session, school)

    resp = await client.put(
        f"/academic/classes/{school_class.id}/timetable/{period.id}",
        json={"subject_id": str(subject.id)},
        params={"year_id": str(academic_year.id)}, headers=auth,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["staff_member_id"] == str(staff_member.id)


@pytest.mark.asyncio
async def test_upsert_with_staff_member_id_still_rejects_double_booking(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, staff_member: StaffMember,
):
    """The double-booking check must fire against a teacher freshly upserted
    in this same request, not just one already on record."""
    other_class = Class(school_id=school.id, level="SHS", year_group=2, stream="D", is_active=True)
    db_session.add(other_class)
    await db_session.flush()

    subject_a = await _make_subject(db_session, school, "ECON")
    subject_b = await _make_subject(db_session, school, "ACC")
    await _put_on_curriculum(db_session, school, school_class, subject_a)
    await _put_on_curriculum(db_session, school, other_class, subject_b)
    await _assign_teacher(db_session, school, school_class, subject_a, academic_year, staff_member)
    period = await _make_period(db_session, school)

    resp = await client.put(
        f"/academic/classes/{school_class.id}/timetable/{period.id}",
        json={"subject_id": str(subject_a.id)},
        params={"year_id": str(academic_year.id)}, headers=auth,
    )
    assert resp.status_code == 200

    resp = await client.put(
        f"/academic/classes/{other_class.id}/timetable/{period.id}",
        json={"subject_id": str(subject_b.id), "staff_member_id": str(staff_member.id)},
        params={"year_id": str(academic_year.id)}, headers=auth,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_upsert_rejects_staff_member_from_other_school(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear,
):
    other_auth = await _other_school_auth(client, db_session)
    other_staff_id = (await client.post("/staff", json={
        "staff_number": "OTH-TT", "first_name": "Other", "last_name": "Teacher",
    }, headers=other_auth)).json()["id"]

    subject = await _make_subject(db_session, school, "MUS")
    await _put_on_curriculum(db_session, school, school_class, subject)
    period = await _make_period(db_session, school)

    resp = await client.put(
        f"/academic/classes/{school_class.id}/timetable/{period.id}",
        json={"subject_id": str(subject.id), "staff_member_id": other_staff_id},
        params={"year_id": str(academic_year.id)}, headers=auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upsert_rejects_teacher_double_booking(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, staff_member: StaffMember,
):
    other_class = Class(school_id=school.id, level="SHS", year_group=2, stream="B", is_active=True)
    db_session.add(other_class)
    await db_session.flush()

    subject_a = await _make_subject(db_session, school, "ENG")
    subject_b = await _make_subject(db_session, school, "LIT")
    await _put_on_curriculum(db_session, school, school_class, subject_a)
    await _put_on_curriculum(db_session, school, other_class, subject_b)
    await _assign_teacher(db_session, school, school_class, subject_a, academic_year, staff_member)
    await _assign_teacher(db_session, school, other_class, subject_b, academic_year, staff_member)
    period = await _make_period(db_session, school)

    resp = await client.put(
        f"/academic/classes/{school_class.id}/timetable/{period.id}",
        json={"subject_id": str(subject_a.id)},
        params={"year_id": str(academic_year.id)}, headers=auth,
    )
    assert resp.status_code == 200

    resp = await client.put(
        f"/academic/classes/{other_class.id}/timetable/{period.id}",
        json={"subject_id": str(subject_b.id)},
        params={"year_id": str(academic_year.id)}, headers=auth,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_reassigning_same_cell_is_not_a_double_booking(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, staff_member: StaffMember,
):
    """A class's own cell is an upsert, not a conflict against itself."""
    subject_a = await _make_subject(db_session, school, "GEO")
    subject_b = await _make_subject(db_session, school, "HIST")
    await _put_on_curriculum(db_session, school, school_class, subject_a)
    await _put_on_curriculum(db_session, school, school_class, subject_b)
    await _assign_teacher(db_session, school, school_class, subject_a, academic_year, staff_member)
    await _assign_teacher(db_session, school, school_class, subject_b, academic_year, staff_member)
    period = await _make_period(db_session, school)

    resp = await client.put(
        f"/academic/classes/{school_class.id}/timetable/{period.id}",
        json={"subject_id": str(subject_a.id)},
        params={"year_id": str(academic_year.id)}, headers=auth,
    )
    assert resp.status_code == 200

    resp = await client.put(
        f"/academic/classes/{school_class.id}/timetable/{period.id}",
        json={"subject_id": str(subject_b.id)},
        params={"year_id": str(academic_year.id)}, headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["subject_id"] == str(subject_b.id)

    resp = await client.get(
        f"/academic/classes/{school_class.id}/timetable",
        params={"year_id": str(academic_year.id)}, headers=auth,
    )
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_timetable_slot(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, staff_member: StaffMember,
):
    subject = await _make_subject(db_session, school, "FRE")
    await _put_on_curriculum(db_session, school, school_class, subject)
    await _assign_teacher(db_session, school, school_class, subject, academic_year, staff_member)
    period = await _make_period(db_session, school)

    await client.put(
        f"/academic/classes/{school_class.id}/timetable/{period.id}",
        json={"subject_id": str(subject.id)},
        params={"year_id": str(academic_year.id)}, headers=auth,
    )

    resp = await client.delete(
        f"/academic/classes/{school_class.id}/timetable/{period.id}",
        params={"year_id": str(academic_year.id)}, headers=auth,
    )
    assert resp.status_code == 204

    resp = await client.delete(
        f"/academic/classes/{school_class.id}/timetable/{period.id}",
        params={"year_id": str(academic_year.id)}, headers=auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_class_timetable_cross_school_class_404(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear,
):
    other_auth = await _other_school_auth(client, db_session)
    resp = await client.get(
        f"/academic/classes/{school_class.id}/timetable",
        params={"year_id": str(academic_year.id)}, headers=other_auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_my_schedule_returns_teachers_own_slots(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, redis_permissions: None,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    staff = await db_session.get(StaffMember, staff_id)

    subject = await _make_subject(db_session, school, "BIO")
    await _put_on_curriculum(db_session, school, school_class, subject)
    await _assign_teacher(db_session, school, school_class, subject, academic_year, staff)
    period = await _make_period(db_session, school, day="TUE", number=3, start="09:30:00", end="10:15:00")

    await client.put(
        f"/academic/classes/{school_class.id}/timetable/{period.id}",
        json={"subject_id": str(subject.id)},
        params={"year_id": str(academic_year.id)}, headers=auth,
    )

    resp = await client.get(
        "/timetable/my-schedule", params={"year_id": str(academic_year.id)}, headers=teacher_auth,
    )
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["day_of_week"] == "TUE"
    assert entries[0]["class_id"] == str(school_class.id)
    assert entries[0]["subject_id"] == str(subject.id)
    assert entries[0]["start_time"] == "09:30:00"
