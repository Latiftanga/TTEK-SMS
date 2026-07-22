"""
Guardian portal integration tests — grant/revoke access via a student's
Guardians tab, PHONE login for a guardian_id account, and multi-child
term-enrollment/report-card reads gated by StudentGuardian.

Run inside Docker: docker compose exec api pytest app/tests/test_guardian_portal.py -v
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import AcademicTerm, Class
from app.models.auth import LoginType, User
from app.models.school import School
from app.models.students import Guardian, Student, StudentGuardian

from .test_portal import _make_enrollment, _publish_assessment


async def _add_guardian(db: AsyncSession, school: School, student: Student, phone: str = "0244000111") -> Guardian:
    guardian = Guardian(school_id=school.id, first_name="Efua", last_name="Mensah", phone=phone)
    db.add(guardian)
    await db.flush()
    db.add(StudentGuardian(
        school_id=school.id, student_id=student.id, guardian_id=guardian.id,
        relation_type="Mother", is_primary=True,
    ))
    await db.flush()
    return guardian


async def _make_guardian_user(db: AsyncSession, school: School, guardian: Guardian, password: str = "portal1234") -> User:
    user = User(
        school_id=school.id, login_type=LoginType.PHONE, phone=guardian.phone,
        password_hash=hash_password(password), guardian_id=guardian.id, is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _guardian_login(client: AsyncClient, guardian: Guardian, password: str = "portal1234") -> dict:
    resp = await client.post("/auth/login", json={
        "login_type": "PHONE", "identifier": guardian.phone, "password": password,
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Grant / revoke ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_grant_guardian_portal_access(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, student: Student,
):
    guardian = await _add_guardian(db_session, school, student)
    resp = await client.post(
        f"/students/{student.id}/guardians/{guardian.id}/grant-portal-access", headers=auth,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["has_portal_access"] is True
    assert data["phone"] == guardian.phone

    user = await db_session.scalar(select(User).where(User.guardian_id == guardian.id))
    assert user is not None
    assert user.login_type == LoginType.PHONE
    assert user.is_active is True


@pytest.mark.asyncio
async def test_grant_guardian_portal_access_twice_conflicts(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, student: Student,
):
    guardian = await _add_guardian(db_session, school, student)
    await client.post(f"/students/{student.id}/guardians/{guardian.id}/grant-portal-access", headers=auth)
    resp = await client.post(f"/students/{student.id}/guardians/{guardian.id}/grant-portal-access", headers=auth)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_grant_guardian_portal_access_phone_collision(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, student: Student,
):
    """The guardian's phone is already claimed by another User — 409, not a 500."""
    guardian = await _add_guardian(db_session, school, student, phone="0244000222")
    db_session.add(User(
        school_id=school.id, login_type=LoginType.PHONE, phone="0244000222",
        password_hash=hash_password("whatever"), is_active=True,
    ))
    await db_session.flush()

    resp = await client.post(f"/students/{student.id}/guardians/{guardian.id}/grant-portal-access", headers=auth)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_revoke_guardian_portal_access(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, student: Student,
):
    guardian = await _add_guardian(db_session, school, student)
    await client.post(f"/students/{student.id}/guardians/{guardian.id}/grant-portal-access", headers=auth)

    resp = await client.delete(f"/students/{student.id}/guardians/{guardian.id}/revoke-portal-access", headers=auth)
    assert resp.status_code == 204

    user = await db_session.scalar(select(User).where(User.guardian_id == guardian.id))
    assert user.is_active is False


@pytest.mark.asyncio
async def test_revoke_guardian_portal_access_without_access_404(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, student: Student,
):
    guardian = await _add_guardian(db_session, school, student)
    resp = await client.delete(f"/students/{student.id}/guardians/{guardian.id}/revoke-portal-access", headers=auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_student_detail_reflects_guardian_portal_access(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, student: Student,
):
    guardian = await _add_guardian(db_session, school, student)
    resp = await client.get(f"/students/{student.id}", headers=auth)
    assert resp.json()["guardians"][0]["has_portal_access"] is False

    await client.post(f"/students/{student.id}/guardians/{guardian.id}/grant-portal-access", headers=auth)
    resp2 = await client.get(f"/students/{student.id}", headers=auth)
    assert resp2.json()["guardians"][0]["has_portal_access"] is True


# ── PHONE login ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_guardian_can_login_via_phone(
    client: AsyncClient, db_session: AsyncSession, school: School, student: Student,
):
    guardian = await _add_guardian(db_session, school, student)
    await _make_guardian_user(db_session, school, guardian)
    portal_auth = await _guardian_login(client, guardian)

    resp = await client.get("/auth/me", headers=portal_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["guardian_id"] == str(guardian.id)
    assert data["student_id"] is None
    assert data["login_type"] == "PHONE"


# ── Multi-child portal reads ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_portal_children_lists_linked_students(
    client: AsyncClient, db_session: AsyncSession, school: School, student: Student,
    school_class: Class, academic_term: AcademicTerm, school_admin: User,
):
    other = Student(school_id=school.id, admission_number="STU010", first_name="Kwabena", last_name="Osei", is_active=True)
    db_session.add(other)
    await db_session.flush()

    guardian = await _add_guardian(db_session, school, student)
    db_session.add(StudentGuardian(
        school_id=school.id, student_id=other.id, guardian_id=guardian.id,
        relation_type="Father", is_primary=True,
    ))
    await db_session.flush()
    await _make_guardian_user(db_session, school, guardian)
    await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    await _make_enrollment(db_session, school, other, school_class, academic_term, school_admin)
    portal_auth = await _guardian_login(client, guardian)

    resp = await client.get("/portal/children", headers=portal_auth)
    assert resp.status_code == 200
    ids = {c["student_id"] for c in resp.json()}
    assert ids == {str(student.id), str(other.id)}


@pytest.mark.asyncio
async def test_portal_children_rejects_student_account(
    client: AsyncClient, db_session: AsyncSession, school: School, student: Student,
):
    from .test_portal import _make_student_user, _portal_login
    await _make_student_user(db_session, school, student)
    portal_auth = await _portal_login(client, school, student)

    resp = await client.get("/portal/children", headers=portal_auth)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_portal_term_enrollments_requires_student_id_for_guardian(
    client: AsyncClient, db_session: AsyncSession, school: School, student: Student,
):
    guardian = await _add_guardian(db_session, school, student)
    await _make_guardian_user(db_session, school, guardian)
    portal_auth = await _guardian_login(client, guardian)

    resp = await client.get("/portal/term-enrollments", headers=portal_auth)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_portal_term_enrollments_rejects_non_child(
    client: AsyncClient, db_session: AsyncSession, school: School, student: Student,
):
    unrelated = Student(school_id=school.id, admission_number="STU011", first_name="Yaa", last_name="Asantewaa", is_active=True)
    db_session.add(unrelated)
    await db_session.flush()

    guardian = await _add_guardian(db_session, school, student)
    await _make_guardian_user(db_session, school, guardian)
    portal_auth = await _guardian_login(client, guardian)

    resp = await client.get("/portal/term-enrollments", params={"student_id": str(unrelated.id)}, headers=portal_auth)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_portal_term_enrollments_for_own_child(
    client: AsyncClient, db_session: AsyncSession, school: School, student: Student,
    school_class: Class, academic_term: AcademicTerm, school_admin: User,
):
    guardian = await _add_guardian(db_session, school, student)
    await _make_guardian_user(db_session, school, guardian)
    te = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    portal_auth = await _guardian_login(client, guardian)

    resp = await client.get("/portal/term-enrollments", params={"student_id": str(student.id)}, headers=portal_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == str(te.id)


@pytest.mark.asyncio
async def test_portal_report_card_for_child(
    client: AsyncClient, db_session: AsyncSession, school: School, student: Student,
    school_class: Class, academic_term: AcademicTerm, school_admin: User,
):
    guardian = await _add_guardian(db_session, school, student)
    await _make_guardian_user(db_session, school, guardian)
    te = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    await _publish_assessment(db_session, school, school_class, academic_term)
    portal_auth = await _guardian_login(client, guardian)

    resp = await client.get(
        f"/portal/report-cards/{te.id}", params={"student_id": str(student.id)}, headers=portal_auth,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
