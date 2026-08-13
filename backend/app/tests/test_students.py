"""
Student profile integration tests (CRUD, guardians, medical record).
Run inside Docker: docker compose exec api pytest app/tests/test_students.py -v
"""
import io
import unittest.mock as mock
import uuid
from datetime import date

import httpx
import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import AcademicYear, Class
from app.models.auth import LoginType, StaffPosition, User
from app.models.school import School, SmsConfig, SmsProvider
from app.models.students import StudentClassAssignment


def _student(num: str = "ADM001", **kw) -> dict:
    return {"admission_number": num, "first_name": "Ama", "last_name": "Boateng", **kw}


def _tiny_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="PNG")
    return buf.getvalue()


async def _login_as_position(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, position_code: str,
) -> tuple[dict, str]:
    """Create a staff member holding `position_code`, give them a login, and
    return (their bearer-token auth headers, their staff_member id)."""
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


# ── Student CRUD ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_student(client: AsyncClient, auth: dict):
    resp = await client.post("/students", json=_student(), headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["admission_number"] == "ADM001"
    assert data["display_name"] == "Ama Boateng"
    assert data["guardians"] == []
    assert data["medical_record"] is None


@pytest.mark.asyncio
async def test_create_student_with_middle_name(client: AsyncClient, auth: dict):
    resp = await client.post("/students", json=_student(middle_name="Akua"), headers=auth)
    assert resp.status_code == 201
    assert resp.json()["display_name"] == "Ama Akua Boateng"


@pytest.mark.asyncio
async def test_duplicate_admission_number_rejected(client: AsyncClient, auth: dict):
    await client.post("/students", json=_student(), headers=auth)
    resp = await client.post("/students", json=_student(), headers=auth)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_students(client: AsyncClient, auth: dict):
    await client.post("/students", json=_student("ADM001"), headers=auth)
    await client.post("/students", json=_student("ADM002"), headers=auth)
    resp = await client.get("/students", headers=auth)
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert resp.headers["x-total-count"] == "2"


@pytest.mark.asyncio
async def test_list_students_total_count_exceeds_page(client: AsyncClient, auth: dict):
    for i in range(3):
        await client.post("/students", json=_student(f"ADM00{i}"), headers=auth)
    resp = await client.get("/students?limit=2", headers=auth)
    assert len(resp.json()) == 2
    assert resp.headers["x-total-count"] == "3"


@pytest.mark.asyncio
async def test_list_students_search(client: AsyncClient, auth: dict):
    await client.post("/students", json=_student("ADM001", last_name="Mensah"), headers=auth)
    await client.post("/students", json=_student("ADM002", last_name="Asante"), headers=auth)
    resp = await client.get("/students?search=mensah", headers=auth)
    assert len(resp.json()) == 1
    assert resp.json()[0]["last_name"] == "Mensah"
    assert resp.headers["x-total-count"] == "1"


# ── Sort ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_students_sort_by_name(client: AsyncClient, auth: dict):
    await client.post("/students", json=_student("ADM001", last_name="Zulu"), headers=auth)
    await client.post("/students", json=_student("ADM002", last_name="Asante"), headers=auth)
    resp = await client.get("/students?sort_by=name&sort_dir=asc", headers=auth)
    names = [s["last_name"] for s in resp.json()]
    assert names == ["Asante", "Zulu"]

    resp = await client.get("/students?sort_by=name&sort_dir=desc", headers=auth)
    names = [s["last_name"] for s in resp.json()]
    assert names == ["Zulu", "Asante"]


@pytest.mark.asyncio
async def test_list_students_sort_by_admission(client: AsyncClient, auth: dict):
    await client.post("/students", json=_student("ADM009"), headers=auth)
    await client.post("/students", json=_student("ADM001"), headers=auth)
    resp = await client.get("/students?sort_by=admission&sort_dir=asc", headers=auth)
    numbers = [s["admission_number"] for s in resp.json()]
    assert numbers == ["ADM001", "ADM009"]


@pytest.mark.asyncio
async def test_list_students_sort_by_class(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_year: AcademicYear, db_session: AsyncSession, school: School,
):
    # school_class fixture is SHS year_group=2; give it a lower-ranked Basic class to sort before it.
    basic_class = Class(school_id=school.id, level="Basic", year_group=6, is_active=True)
    db_session.add(basic_class)
    await db_session.flush()

    sid_shs = (await client.post("/students", json=_student("ADM001"), headers=auth)).json()["id"]
    sid_basic = (await client.post("/students", json=_student("ADM002"), headers=auth)).json()["id"]
    sid_none = (await client.post("/students", json=_student("ADM003"), headers=auth)).json()["id"]

    await client.post("/students/class-assignments", json={
        "student_id": sid_shs, "class_id": str(school_class.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)
    await client.post("/students/class-assignments", json={
        "student_id": sid_basic, "class_id": str(basic_class.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)

    resp = await client.get("/students?sort_by=class&sort_dir=asc", headers=auth)
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    # Basic (pedagogically before SHS) first, then SHS, then no-class student last (nulls_last).
    assert ids == [sid_basic, sid_shs, sid_none]


# ── Multi-active class assignment (promoted, not graduated) ───────────────────

@pytest.mark.asyncio
async def test_list_students_promoted_student_not_double_counted(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_year: AcademicYear, db_session: AsyncSession, school: School,
):
    """A promoted (non-graduated) student can hold 2+ is_active StudentClassAssignment
    rows across academic years — the list/count must dedup to the most recent one."""
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

    resp = await client.get("/students", headers=auth)
    assert resp.status_code == 200
    assert resp.headers["x-total-count"] == "1"
    assert len(resp.json()) == 1
    # Most-recently-created assignment (next_class, SHS year_group=3) wins.
    assert resp.json()[0]["current_class_id"] == str(next_class.id)


# ── Staff-scoped visibility ─────────────────────────────────────────────────────
# Staff without students.edit are scoped to their own students UNLESS they hold a
# broader administrative permission (fees, housing, score approval) that requires
# seeing the full roster to do their job.

@pytest.mark.asyncio
async def test_list_students_bursar_sees_full_roster(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions: None,
):
    """A Bursar has students.view + fees.collect/manage but no students.edit and no
    ClassTeacher/SubjectTeacher/HouseMaster row — they must still see every student
    to record a payment against them."""
    await client.post("/students", json=_student("ADM001"), headers=auth)
    await client.post("/students", json=_student("ADM002"), headers=auth)

    bursar_auth, _bursar_staff_id = await _login_as_position(client, auth, db_session, school, "BURSAR")
    resp = await client.get("/students", headers=bursar_auth)
    assert resp.status_code == 200
    assert resp.headers["x-total-count"] == "2"


@pytest.mark.asyncio
async def test_list_students_housemaster_sees_full_roster(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions: None,
):
    """A Housemaster has housing.assign/manage but no students.edit — they must
    still see students outside their own house to assign a new one in."""
    await client.post("/students", json=_student("ADM001"), headers=auth)

    housemaster_auth, _hm_staff_id = await _login_as_position(client, auth, db_session, school, "HOUSEMASTER")
    resp = await client.get("/students", headers=housemaster_auth)
    assert resp.status_code == 200
    assert resp.headers["x-total-count"] == "1"


@pytest.mark.asyncio
async def test_list_students_exam_officer_sees_full_roster(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions: None,
):
    """An Exam Officer has assessments.approve_scores but no students.edit — they
    must still see rosters for classes they don't personally teach."""
    await client.post("/students", json=_student("ADM001"), headers=auth)

    exam_officer_auth, _eo_staff_id = await _login_as_position(client, auth, db_session, school, "EXAM_OFFICER")
    resp = await client.get("/students", headers=exam_officer_auth)
    assert resp.status_code == 200
    assert resp.headers["x-total-count"] == "1"


@pytest.mark.asyncio
async def test_list_students_class_teacher_scoped_to_own_class(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, redis_permissions: None,
):
    """CLASS_TEACHER holds students.edit but — unlike Bursar/Housemaster/Exam
    Officer's genuinely broad permissions — that's not a signal to see the
    whole school. Scoped to their own ClassTeacher/SubjectTeacher classes via
    the existing student_list.py union, same as a plain subject-only teacher."""
    from app.models.academic import ClassTeacher

    sid_in_class = (await client.post("/students", json=_student("ADM001"), headers=auth)).json()["id"]
    await client.post("/students", json=_student("ADM002"), headers=auth)  # not in the teacher's class
    await client.post("/students/class-assignments", json={
        "student_id": sid_in_class, "class_id": str(school_class.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)

    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")

    unassigned = await client.get("/students", headers=teacher_auth)
    assert unassigned.status_code == 200
    assert unassigned.headers["x-total-count"] == "0"

    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.get("/students", headers=teacher_auth)
    assert resp.status_code == 200
    assert resp.headers["x-total-count"] == "1"
    assert resp.json()[0]["id"] == sid_in_class


@pytest.mark.asyncio
async def test_get_student(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    resp = await client.get(f"/students/{sid}", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["id"] == sid


@pytest.mark.asyncio
async def test_update_student(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    resp = await client.patch(f"/students/{sid}", json={"nationality": "Ghanaian"}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["nationality"] == "Ghanaian"


@pytest.mark.asyncio
async def test_deactivate_student(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    await client.patch(f"/students/{sid}", json={"is_active": False}, headers=auth)
    active_list = (await client.get("/students", headers=auth)).json()
    assert all(s["id"] != sid for s in active_list)
    all_list = (await client.get("/students?active_only=false", headers=auth)).json()
    assert any(s["id"] == sid for s in all_list)


# ── Class-teacher/subject-teacher scoping (core/student_scope.py) ─────────────

async def _assign_class(
    client: AsyncClient, auth: dict, sid: str, class_id, academic_year_id,
) -> None:
    resp = await client.post("/students/class-assignments", json={
        "student_id": sid, "class_id": str(class_id), "academic_year_id": str(academic_year_id),
    }, headers=auth)
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_get_student_404_for_class_teacher_outside_scope(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions: None,
):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    teacher_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    resp = await client.get(f"/students/{sid}", headers=teacher_auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_student_200_with_capability_flags_for_own_class_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, redis_permissions: None,
):
    from app.models.academic import ClassTeacher

    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    await _assign_class(client, auth, sid, school_class.id, academic_year.id)
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.get(f"/students/{sid}", headers=teacher_auth)
    assert resp.status_code == 200
    assert resp.json()["can_edit"] is True
    assert resp.json()["can_manage"] is False  # CLASS_TEACHER holds students.edit, not students.delete


@pytest.mark.asyncio
async def test_update_student_404_for_class_teacher_outside_scope(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions: None,
):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    teacher_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    resp = await client.patch(f"/students/{sid}", json={"nationality": "Ghanaian"}, headers=teacher_auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_student_200_for_own_class_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, redis_permissions: None,
):
    from app.models.academic import ClassTeacher

    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    await _assign_class(client, auth, sid, school_class.id, academic_year.id)
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.patch(f"/students/{sid}", json={"nationality": "Ghanaian"}, headers=teacher_auth)
    assert resp.status_code == 200
    assert resp.json()["nationality"] == "Ghanaian"


@pytest.mark.asyncio
async def test_update_student_is_active_requires_students_delete_even_for_own_class(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, redis_permissions: None,
):
    """Deactivate/reactivate is admin-tier (Category D) — a class teacher
    editing their own student's profile still can't flip is_active."""
    from app.models.academic import ClassTeacher

    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    await _assign_class(client, auth, sid, school_class.id, academic_year.id)
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.patch(f"/students/{sid}", json={"is_active": False}, headers=teacher_auth)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_grant_portal_access_requires_students_delete(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_year: AcademicYear, redis_permissions: None,
):
    """Admin-tier (Category D) regardless of class-teacher scope."""
    from app.models.academic import ClassTeacher

    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    await _assign_class(client, auth, sid, school_class.id, academic_year.id)
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.post(f"/students/{sid}/grant-portal-access", headers=teacher_auth)
    assert resp.status_code == 403

    resp = await client.post(f"/students/{sid}/grant-portal-access", headers=auth)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_deputy_head_and_hod_remain_unrestricted(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions: None,
):
    """students.delete added to DEPUTY_HEAD/HOD templates alongside this fix
    — they must not regress to zero students under the new scoping."""
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    for position in ("DEPUTY_HEAD", "HOD"):
        staff_auth, _staff_id = await _login_as_position(client, auth, db_session, school, position)
        resp = await client.get(f"/students/{sid}", headers=staff_auth)
        assert resp.status_code == 200, f"{position} should see any student: {resp.text}"
        resp = await client.patch(f"/students/{sid}", json={"nationality": "Ghanaian"}, headers=staff_auth)
        assert resp.status_code == 200, f"{position} should be able to edit any student: {resp.text}"


# ── Medical record ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_medical_record(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    resp = await client.put(f"/students/{sid}/medical", json={
        "blood_group": "O+", "allergies": "Peanuts",
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["blood_group"] == "O+"

    # Update (upsert — same endpoint)
    resp2 = await client.put(f"/students/{sid}/medical", json={"blood_group": "A+"}, headers=auth)
    assert resp2.json()["blood_group"] == "A+"
    assert resp2.json()["allergies"] == "Peanuts"   # previous value preserved


# ── Guardian management ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_and_remove_guardian(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    resp = await client.post(f"/students/{sid}/guardians", json={
        "first_name": "Kofi", "last_name": "Boateng",
        "phone": "0244000001", "relation_type": "Father", "is_primary": True,
    }, headers=auth)
    assert resp.status_code == 201
    guardian_id = resp.json()["guardian_id"]
    assert resp.json()["is_primary"] is True

    detail = (await client.get(f"/students/{sid}", headers=auth)).json()
    assert len(detail["guardians"]) == 1

    # A second guardian is required before the first can be removed — a
    # student must always have at least one guardian on record.
    await client.post(f"/students/{sid}/guardians", json={
        "first_name": "Abena", "last_name": "Boateng",
        "phone": "0244000002", "relation_type": "Mother",
    }, headers=auth)

    await client.delete(f"/students/{sid}/guardians/{guardian_id}", headers=auth)
    detail = (await client.get(f"/students/{sid}", headers=auth)).json()
    assert len(detail["guardians"]) == 1
    assert detail["guardians"][0]["first_name"] == "Abena"


@pytest.mark.asyncio
async def test_first_guardian_forced_primary(client: AsyncClient, auth: dict):
    """The first guardian added to a student is always primary, even if the
    request explicitly says otherwise — a student may never have guardians
    but no primary."""
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    resp = await client.post(f"/students/{sid}/guardians", json={
        "first_name": "Kofi", "last_name": "Boateng",
        "phone": "0244000001", "relation_type": "Father", "is_primary": False,
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["is_primary"] is True


@pytest.mark.asyncio
async def test_cannot_remove_only_guardian(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    guardian_id = (await client.post(f"/students/{sid}/guardians", json={
        "first_name": "Kofi", "last_name": "Boateng",
        "phone": "0244000001", "relation_type": "Father", "is_primary": True,
    }, headers=auth)).json()["guardian_id"]

    resp = await client.delete(f"/students/{sid}/guardians/{guardian_id}", headers=auth)
    assert resp.status_code == 409

    detail = (await client.get(f"/students/{sid}", headers=auth)).json()
    assert len(detail["guardians"]) == 1


@pytest.mark.asyncio
async def test_removing_primary_auto_promotes_remaining(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    primary_id = (await client.post(f"/students/{sid}/guardians", json={
        "first_name": "Kofi", "last_name": "Boateng",
        "phone": "0244000001", "relation_type": "Father", "is_primary": True,
    }, headers=auth)).json()["guardian_id"]
    secondary_id = (await client.post(f"/students/{sid}/guardians", json={
        "first_name": "Abena", "last_name": "Boateng",
        "phone": "0244000002", "relation_type": "Mother", "is_primary": False,
    }, headers=auth)).json()["guardian_id"]

    resp = await client.delete(f"/students/{sid}/guardians/{primary_id}", headers=auth)
    assert resp.status_code == 204

    detail = (await client.get(f"/students/{sid}", headers=auth)).json()
    assert len(detail["guardians"]) == 1
    assert detail["guardians"][0]["guardian_id"] == secondary_id
    assert detail["guardians"][0]["is_primary"] is True


@pytest.mark.asyncio
async def test_cannot_demote_sole_primary_without_replacement(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    primary_id = (await client.post(f"/students/{sid}/guardians", json={
        "first_name": "Kofi", "last_name": "Boateng",
        "phone": "0244000001", "relation_type": "Father", "is_primary": True,
    }, headers=auth)).json()["guardian_id"]
    await client.post(f"/students/{sid}/guardians", json={
        "first_name": "Abena", "last_name": "Boateng",
        "phone": "0244000002", "relation_type": "Mother", "is_primary": False,
    }, headers=auth)

    resp = await client.patch(f"/students/{sid}/guardians/{primary_id}", json={
        "is_primary": False,
    }, headers=auth)
    assert resp.status_code == 422

    # Promoting the other guardian instead works fine (existing demote-on-promote path).
    detail = (await client.get(f"/students/{sid}", headers=auth)).json()
    assert any(g["is_primary"] for g in detail["guardians"])


@pytest.mark.asyncio
async def test_primary_guardian_demoted(client: AsyncClient, auth: dict):
    """Adding a second primary guardian demotes the first."""
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    await client.post(f"/students/{sid}/guardians", json={
        "first_name": "Kofi", "last_name": "Boateng",
        "phone": "0244000001", "relation_type": "Father", "is_primary": True,
    }, headers=auth)
    await client.post(f"/students/{sid}/guardians", json={
        "first_name": "Abena", "last_name": "Boateng",
        "phone": "0244000002", "relation_type": "Mother", "is_primary": True,
    }, headers=auth)
    detail = (await client.get(f"/students/{sid}", headers=auth)).json()
    primaries = [g for g in detail["guardians"] if g["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["first_name"] == "Abena"


@pytest.mark.asyncio
async def test_update_guardian(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    add_resp = await client.post(f"/students/{sid}/guardians", json={
        "first_name": "Kofi", "last_name": "Boateng",
        "phone": "0244000001", "relation_type": "Father", "is_primary": True,
    }, headers=auth)
    guardian_id = add_resp.json()["guardian_id"]

    resp = await client.patch(f"/students/{sid}/guardians/{guardian_id}", json={
        "phone": "0244999999", "occupation": "Teacher",
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["phone"] == "0244999999"
    assert resp.json()["occupation"] == "Teacher"
    assert resp.json()["first_name"] == "Kofi"   # untouched field preserved


@pytest.mark.asyncio
async def test_update_guardian_promotes_new_primary_demotes_old(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    first_id = (await client.post(f"/students/{sid}/guardians", json={
        "first_name": "Kofi", "last_name": "Boateng",
        "phone": "0244000001", "relation_type": "Father", "is_primary": True,
    }, headers=auth)).json()["guardian_id"]
    second_id = (await client.post(f"/students/{sid}/guardians", json={
        "first_name": "Abena", "last_name": "Boateng",
        "phone": "0244000002", "relation_type": "Mother", "is_primary": False,
    }, headers=auth)).json()["guardian_id"]

    resp = await client.patch(f"/students/{sid}/guardians/{second_id}", json={
        "is_primary": True,
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["is_primary"] is True

    detail = (await client.get(f"/students/{sid}", headers=auth)).json()
    primaries = [g for g in detail["guardians"] if g["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["guardian_id"] == second_id


@pytest.mark.asyncio
async def test_update_guardian_not_found(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    resp = await client.patch(
        f"/students/{sid}/guardians/{uuid.uuid4()}", json={"phone": "0244000001"}, headers=auth,
    )
    assert resp.status_code == 404


# ── Portal access ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_grant_portal_access(client: AsyncClient, auth: dict, school: School):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    resp = await client.post(f"/students/{sid}/grant-portal-access", headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["has_portal_access"] is True
    assert data["admission_number"] == "ADM001"
    assert data["sms_sent"] is False   # no SMS provider configured in tests

    login = await client.post("/auth/login", json={
        "login_type": "ADMISSION_ID", "identifier": "ADM001",
        "school_code": school.school_code, "password": "ADM001",
    })
    assert login.status_code == 200, login.text


@pytest.mark.asyncio
async def test_grant_portal_access_sends_sms_to_primary_guardian(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    """Regression test: student_portal.py's _notify_guardian previously
    imported a function that doesn't exist (sms_notifications.get_active_driver
    — the real name is _get_active_driver) and called _log_result with the
    wrong argument order, so sms_sent was silently always False even with an
    active provider and a primary guardian configured. Both were swallowed by
    a broad except Exception. This drives the real path with a mocked HTTP
    transport to prove sms_sent actually reflects a real send now."""
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    await client.post(f"/students/{sid}/guardians", json={
        "first_name": "Kofi", "last_name": "Boateng",
        "phone": "0244000001", "relation_type": "Father", "is_primary": True,
    }, headers=auth)

    db_session.add(SmsConfig(
        school_id=school.id, provider=SmsProvider.ARKESEL,
        api_key="test-arkesel-key", sender_id="TESTSCHOOL", is_active=True,
    ))
    await db_session.flush()

    original_init = httpx.AsyncClient.__init__

    class _MockTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(200, json={"status": "ok"})

    with mock.patch("httpx.AsyncClient.__init__", lambda self, **kw: original_init(
        self, transport=_MockTransport(), **{k: v for k, v in kw.items() if k != "transport"}
    )):
        resp = await client.post(f"/students/{sid}/grant-portal-access", headers=auth)

    assert resp.status_code == 201
    assert resp.json()["sms_sent"] is True


@pytest.mark.asyncio
async def test_grant_portal_access_already_active_conflict(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    await client.post(f"/students/{sid}/grant-portal-access", headers=auth)
    resp = await client.post(f"/students/{sid}/grant-portal-access", headers=auth)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_revoke_portal_access(client: AsyncClient, auth: dict, school: School):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    await client.post(f"/students/{sid}/grant-portal-access", headers=auth)

    resp = await client.delete(f"/students/{sid}/revoke-portal-access", headers=auth)
    assert resp.status_code == 204

    login = await client.post("/auth/login", json={
        "login_type": "ADMISSION_ID", "identifier": "ADM001",
        "school_code": school.school_code, "password": "ADM001",
    })
    assert login.status_code in (401, 403)


@pytest.mark.asyncio
async def test_revoke_portal_access_without_grant_404(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    resp = await client.delete(f"/students/{sid}/revoke-portal-access", headers=auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_grant_portal_access_reactivates_after_revoke(client: AsyncClient, auth: dict, school: School):
    """Granting again after a revoke re-activates the same User row rather than
    rejecting with a conflict."""
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    await client.post(f"/students/{sid}/grant-portal-access", headers=auth)
    await client.delete(f"/students/{sid}/revoke-portal-access", headers=auth)

    resp = await client.post(f"/students/{sid}/grant-portal-access", headers=auth)
    assert resp.status_code == 201
    assert resp.json()["has_portal_access"] is True

    login = await client.post("/auth/login", json={
        "login_type": "ADMISSION_ID", "identifier": "ADM001",
        "school_code": school.school_code, "password": "ADM001",
    })
    assert login.status_code == 200, login.text


# ── Admission number auto-generation ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admission_number_auto_generated_when_omitted(client: AsyncClient, auth: dict, school: School):
    resp = await client.post("/students", json={
        "first_name": "Ama", "last_name": "Boateng",
    }, headers=auth)
    assert resp.status_code == 201
    year = date.today().year
    assert resp.json()["admission_number"] == f"{school.school_code}/{year}/0001"


@pytest.mark.asyncio
async def test_admission_number_auto_generated_sequence_increments(client: AsyncClient, auth: dict, school: School):
    first = await client.post("/students", json={"first_name": "Ama", "last_name": "Boateng"}, headers=auth)
    second = await client.post("/students", json={"first_name": "Kofi", "last_name": "Mensah"}, headers=auth)
    year = date.today().year
    assert first.json()["admission_number"] == f"{school.school_code}/{year}/0001"
    assert second.json()["admission_number"] == f"{school.school_code}/{year}/0002"


@pytest.mark.asyncio
async def test_admission_number_auto_generated_ignores_manual_numbers_outside_pattern(
    client: AsyncClient, auth: dict, school: School,
):
    """A pre-existing manually-entered admission number that doesn't match the
    auto-gen pattern shouldn't break sequence calculation for the next auto one."""
    await client.post("/students", json=_student("LEGACY-001"), headers=auth)
    resp = await client.post("/students", json={"first_name": "Ama", "last_name": "Boateng"}, headers=auth)
    year = date.today().year
    assert resp.json()["admission_number"] == f"{school.school_code}/{year}/0001"


@pytest.mark.asyncio
async def test_admission_number_blank_string_also_auto_generates(client: AsyncClient, auth: dict, school: School):
    resp = await client.post("/students", json={
        "admission_number": "   ", "first_name": "Ama", "last_name": "Boateng",
    }, headers=auth)
    assert resp.status_code == 201
    year = date.today().year
    assert resp.json()["admission_number"] == f"{school.school_code}/{year}/0001"


@pytest.mark.asyncio
async def test_admission_number_explicit_value_still_honoured(client: AsyncClient, auth: dict):
    resp = await client.post("/students", json=_student("CUSTOM/SCHEME/9"), headers=auth)
    assert resp.status_code == 201
    assert resp.json()["admission_number"] == "CUSTOM/SCHEME/9"


# ── Student photo ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_and_delete_student_photo(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    assert (await client.get(f"/students/{sid}", headers=auth)).json()["photo_url"] is None

    resp = await client.post(
        f"/students/{sid}/photo",
        files={"file": ("photo.png", _tiny_png(), "image/png")},
        headers=auth,
    )
    assert resp.status_code == 200
    photo_url = resp.json()["photo_url"]
    assert photo_url is not None
    assert photo_url.endswith(".webp")

    detail = (await client.get(f"/students/{sid}", headers=auth)).json()
    assert detail["photo_url"] == photo_url

    del_resp = await client.delete(f"/students/{sid}/photo", headers=auth)
    assert del_resp.status_code == 204

    detail = (await client.get(f"/students/{sid}", headers=auth)).json()
    assert detail["photo_url"] is None


@pytest.mark.asyncio
async def test_upload_student_photo_rejects_non_image(client: AsyncClient, auth: dict):
    sid = (await client.post("/students", json=_student(), headers=auth)).json()["id"]
    resp = await client.post(
        f"/students/{sid}/photo",
        files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
        headers=auth,
    )
    assert resp.status_code == 415


# ── Graduated filter ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_students_graduated_filter(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school: School, school_admin: User, academic_year: AcademicYear,
):
    from datetime import datetime
    from app.models.documents import GraduationRecord, GraduationType

    sid = (await client.post("/students", json=_student(num="GRAD001"), headers=auth)).json()["id"]

    resp = await client.get("/students?graduated=true", headers=auth)
    assert resp.status_code == 200
    assert not any(s["id"] == sid for s in resp.json())

    db_session.add(GraduationRecord(
        school_id=school.id, student_id=uuid.UUID(sid), academic_year_id=academic_year.id,
        graduation_type=GraduationType.GRADUATED,
        processed_at=datetime(2026, 7, 1), processed_by_id=school_admin.id,
    ))
    await db_session.flush()
    # Graduation only marks GraduationRecord — deactivation is a separate,
    # independent step (see student_lifecycle.py), so active_only must be
    # relaxed here the same way the frontend's "Graduated" pill forces it.
    resp = await client.get("/students?graduated=true&active_only=false", headers=auth)
    assert resp.status_code == 200
    assert any(s["id"] == sid for s in resp.json())
