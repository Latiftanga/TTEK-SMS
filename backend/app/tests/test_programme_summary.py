"""
Programme-level summary — aggregates Class/StudentClassAssignment across
every class in the school running a given programme. Simpler than
test_subject_summary.py: no teacher/term dimension, just year-scoped
class-membership counts.

Run inside Docker: docker compose exec api pytest app/tests/test_programme_summary.py -v
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicYear, Class, SHSProgramme
from app.models.school import School
from app.models.students import Student, StudentClassAssignment


async def _make_programme(db_session: AsyncSession, school: School, code: str, name: str) -> SHSProgramme:
    prog = SHSProgramme(school_id=school.id, code=code, name=name, is_active=True)
    db_session.add(prog)
    await db_session.flush()
    return prog


async def _make_class(db_session: AsyncSession, school: School, prog: SHSProgramme, year_group: int, stream: str) -> Class:
    cls = Class(school_id=school.id, level="SHS", year_group=year_group, programme_id=prog.id, stream=stream, is_active=True)
    db_session.add(cls)
    await db_session.flush()
    return cls


async def _assign_student(
    db_session: AsyncSession, school: School, cls: Class, academic_year: AcademicYear, suffix: str, *, active: bool = True,
) -> Student:
    student = Student(
        school_id=school.id, admission_number=f"PROG{suffix}", first_name="Test", last_name=suffix, is_active=True,
    )
    db_session.add(student)
    await db_session.flush()
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=cls.id,
        academic_year_id=academic_year.id, is_active=active,
    ))
    await db_session.flush()
    return student


@pytest.mark.asyncio
async def test_summary_aggregates_across_classes(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, academic_year: AcademicYear,
):
    prog = await _make_programme(db_session, school, "PROG_SCI", "General Science")
    class_a = await _make_class(db_session, school, prog, 1, "A")
    class_b = await _make_class(db_session, school, prog, 1, "B")

    for i in range(5):
        await _assign_student(db_session, school, class_a, academic_year, f"A{i}")
    # class_b has zero active assignments — one withdrawn student shouldn't count.
    await _assign_student(db_session, school, class_b, academic_year, "W1", active=False)

    resp = await client.get(
        f"/academic/programmes/{prog.id}/summary",
        params={"academic_year_id": str(academic_year.id)}, headers=auth,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_classes"] == 2
    assert data["total_students"] == 5

    by_class = {c["class_id"]: c for c in data["classes"]}
    assert by_class[str(class_a.id)]["student_count"] == 5
    assert by_class[str(class_b.id)]["student_count"] == 0
    assert by_class[str(class_a.id)]["display_name"] == "Year 1 · A"


@pytest.mark.asyncio
async def test_summary_empty_when_no_classes_have_programme(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, academic_year: AcademicYear,
):
    prog = await _make_programme(db_session, school, "PROG_EMPTY", "Empty Programme")
    resp = await client.get(
        f"/academic/programmes/{prog.id}/summary",
        params={"academic_year_id": str(academic_year.id)}, headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "programme_id": str(prog.id), "programme_name": "Empty Programme",
        "total_classes": 0, "total_students": 0, "classes": [],
    }


@pytest.mark.asyncio
async def test_summary_404_cross_school_programme(
    client: AsyncClient, auth: dict, academic_year: AcademicYear,
):
    resp = await client.get(
        f"/academic/programmes/{uuid.uuid4()}/summary",
        params={"academic_year_id": str(academic_year.id)}, headers=auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_summary_404_unadopted_catalogue_programme(
    client: AsyncClient, auth: dict, db_session: AsyncSession, academic_year: AcademicYear,
):
    """A shared (school_id=NULL) catalogue programme this school never
    adopted must 404, same boundary create_class/update_class enforce."""
    catalogue_prog = SHSProgramme(school_id=None, code="PROG_SHARED", name="Shared Catalogue Programme", is_active=True)
    db_session.add(catalogue_prog)
    await db_session.flush()

    resp = await client.get(
        f"/academic/programmes/{catalogue_prog.id}/summary",
        params={"academic_year_id": str(academic_year.id)}, headers=auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_summary_excludes_withdrawn_student_with_stale_active_assignment(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, academic_year: AcademicYear,
):
    """A withdrawn student (Student.is_active=False) whose
    StudentClassAssignment row was never deactivated in lockstep (stale
    data — confirmed live on the real dev DB) must not be counted."""
    prog = await _make_programme(db_session, school, "PROG_WITHDRAWN", "Withdrawn Test Programme")
    cls = await _make_class(db_session, school, prog, 1, "W")

    student = Student(
        school_id=school.id, admission_number="PROGWD1", first_name="With", last_name="Drawn", is_active=False,
    )
    db_session.add(student)
    await db_session.flush()
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=cls.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.get(
        f"/academic/programmes/{prog.id}/summary",
        params={"academic_year_id": str(academic_year.id)}, headers=auth,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_students"] == 0
    assert data["classes"][0]["student_count"] == 0
