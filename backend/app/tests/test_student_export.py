"""
Student register export tests (CSV full export + custom field export).
Run inside Docker: docker compose exec api pytest app/tests/test_student_export.py -v
"""
import csv
import io
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicYear, Class
from app.models.school import School
from app.models.students import StudentClassAssignment


def _student(num: str = "ADM001", **kw) -> dict:
    return {"admission_number": num, "first_name": "Ama", "last_name": "Boateng", **kw}


async def _promote_student(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear,
) -> str:
    """Create a student with 2 concurrent is_active StudentClassAssignment rows —
    the old class (school_class, year 1) and a newer one (next_class, year 2) —
    mirroring a promoted-but-not-graduated student. Returns the student id."""
    sid = (await client.post("/students", json=_student("ADM001"), headers=auth)).json()["id"]

    next_year = AcademicYear(
        school_id=school.id, name="2025/2026",
        start_date=date(2025, 9, 1), end_date=date(2026, 7, 31), is_current=False,
    )
    db_session.add(next_year)
    await db_session.flush()
    next_class = Class(school_id=school.id, level="SHS", year_group=3, stream="A", is_active=True)
    db_session.add(next_class)
    await db_session.flush()

    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=sid, class_id=school_class.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=sid, class_id=next_class.id,
        academic_year_id=next_year.id, is_active=True,
    ))
    await db_session.flush()
    return sid


@pytest.mark.asyncio
async def test_export_csv_shows_current_class_for_promoted_student(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear,
):
    """A promoted (non-graduated) student has 2 active class assignments —
    the export must show the current (most recent) class, not the old one."""
    await _promote_student(client, auth, db_session, school, school_class, academic_year)

    resp = await client.get("/students/export", headers=auth)
    assert resp.status_code == 200
    rows = list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))
    header, data_row = rows[0], rows[1]
    # SHS classes drop the redundant "SHS" word (school-wide format, matches the
    # class list / dashboards) — see student_display.py::_class_display_name.
    assert data_row[header.index("Current Class")] == "3 A"


@pytest.mark.asyncio
async def test_custom_export_shows_current_class_for_promoted_student(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear,
):
    """Same promoted-student scenario, exercised through the custom-field export."""
    await _promote_student(client, auth, db_session, school, school_class, academic_year)

    resp = await client.get(
        "/students/export/custom?fields=admission_number,current_class,level", headers=auth,
    )
    assert resp.status_code == 200
    rows = list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))
    header, data_row = rows[0], rows[1]
    assert data_row[header.index("Current Class")] == "3 A"
    assert data_row[header.index("Level")] == "SHS"
