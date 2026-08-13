"""
Behaviour record scoping tests — assessments.record_behaviour is a Class
Teacher duty (per the staff-roles spec), scoped to the caller's own
ClassTeacher assignment via the shared resolve_report_card_scope() resolver.
Mirrors test_report_cards.py's report-card-scope tests and
test_students.py's Category-A student-scope tests.

Run inside Docker: docker compose exec api pytest app/tests/test_behaviour_scope.py -v
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import AcademicTerm, AcademicYear, Class, ClassTeacher
from app.models.auth import LoginType, StaffPosition, User
from app.models.school import School
from app.models.students import Student, StudentClassAssignment


async def _login_as_position(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, position_code: str,
) -> tuple[dict, str]:
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
        "school_code": school.school_code,
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, staff_id


def _payload(student: Student, academic_term: AcademicTerm, **overrides) -> dict:
    base = {
        "student_id": str(student.id),
        "academic_term_id": str(academic_term.id),
        "incident_type": "Late to class",
        "description": "Arrived 20 minutes late without excuse.",
        "severity": "LOW",
        "incident_date": "2024-10-15",
    }
    base.update(overrides)
    return base


async def _assign_class(
    db_session: AsyncSession, school: School, student: Student, cls: Class, year: AcademicYear,
) -> None:
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=cls.id,
        academic_year_id=year.id, is_active=True,
    ))
    await db_session.flush()


@pytest.mark.asyncio
async def test_create_404_for_class_teacher_outside_scope(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    student: Student, school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm,
    redis_permissions: None,
):
    await _assign_class(db_session, school, student, school_class, academic_year)
    teacher_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    resp = await client.post("/behaviour", json=_payload(student, academic_term), headers=teacher_auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_allowed_for_owning_class_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    student: Student, school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm,
    redis_permissions: None,
):
    await _assign_class(db_session, school, student, school_class, academic_year)
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.post("/behaviour", json=_payload(student, academic_term), headers=teacher_auth)
    assert resp.status_code == 201
    assert resp.json()["incident_type"] == "Late to class"


@pytest.mark.asyncio
async def test_create_404_when_teacher_has_zero_class_assignments(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    student: Student, school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm,
    redis_permissions: None,
):
    """A hard access-control boundary, not a fallback: zero ClassTeacher rows
    means 404 everywhere scoped, never silent full access."""
    await _assign_class(db_session, school, student, school_class, academic_year)
    teacher_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    resp = await client.get(
        f"/behaviour?student_id={student.id}&term_id={academic_term.id}", headers=teacher_auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_and_delete_allowed_for_owning_class_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    student: Student, school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm,
    redis_permissions: None,
):
    await _assign_class(db_session, school, student, school_class, academic_year)
    record_id = (await client.post(
        "/behaviour", json=_payload(student, academic_term), headers=auth,
    )).json()["id"]

    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.get(
        f"/behaviour?student_id={student.id}&term_id={academic_term.id}", headers=teacher_auth,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = await client.delete(f"/behaviour/{record_id}", headers=teacher_auth)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_create_403_for_plain_teacher_without_record_behaviour(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    student: Student, academic_term: AcademicTerm, redis_permissions: None,
):
    """A plain TEACHER-position holder (Subject Teacher core duty) doesn't
    hold assessments.record_behaviour at all — 403 at the router, before any
    scope check."""
    teacher_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    resp = await client.post("/behaviour", json=_payload(student, academic_term), headers=teacher_auth)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_unrestricted_for_approve_scores_holder(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    student: Student, academic_term: AcademicTerm, redis_permissions: None,
):
    """HOD holds assessments.approve_scores — always unrestricted, no
    ClassTeacher assignment needed."""
    hod_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "HOD")
    resp = await client.post("/behaviour", json=_payload(student, academic_term), headers=hod_auth)
    assert resp.status_code == 201
