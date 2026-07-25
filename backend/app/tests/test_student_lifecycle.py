"""
Year-end outcome tests — promotion/repetition/demotion (progression) and
graduation (exit), including the portal-login/term-enrollment exit cascade.
Run inside Docker: docker compose exec api pytest app/tests/test_student_lifecycle.py -v
"""
import pytest
from datetime import date
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, AcademicYear, Class
from app.models.auth import User
from app.models.fees import StudentFeeRecord
from app.models.school import School
from app.models.students import Student


async def _create_student(client, auth, num="ADM001"):
    resp = await client.post("/students", json={
        "admission_number": num, "first_name": "Kwame", "last_name": "Asante",
    }, headers=auth)
    assert resp.status_code == 201
    return resp.json()["id"]


async def _assign_class(client, auth, student_id: str, school_class: Class, academic_year: AcademicYear):
    resp = await client.post("/students/class-assignments", json={
        "student_id": student_id,
        "class_id": str(school_class.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)
    assert resp.status_code == 201


@pytest.fixture
async def next_year(db_session: AsyncSession, school: School) -> AcademicYear:
    year = AcademicYear(
        school_id=school.id, name="2025/2026",
        start_date=date(2025, 9, 1), end_date=date(2026, 7, 31), is_current=False,
    )
    db_session.add(year)
    await db_session.flush()
    return year


@pytest.fixture
async def next_class(db_session: AsyncSession, school: School) -> Class:
    cls = Class(school_id=school.id, level="SHS", year_group=3, stream="A", is_active=True)
    db_session.add(cls)
    await db_session.flush()
    return cls


# ── Promotion / repetition / demotion ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_promote_creates_record_and_assignment(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_year: AcademicYear,
    next_class: Class, next_year: AcademicYear,
):
    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_year)

    resp = await client.post("/students/promotions/bulk", json={
        "academic_year_id": str(next_year.id),
        "records": [{"student_id": sid, "graduation_type": "PROMOTED", "class_id": str(next_class.id)}],
    }, headers=auth)
    assert resp.status_code == 201
    body = resp.json()
    assert body["processed"] == 1
    assert body["skipped"] == 0
    assert body["records"][0]["graduation_type"] == "PROMOTED"

    assignments = (await client.get(f"/students/{sid}/class-assignments", headers=auth)).json()
    new_year_assignment = next(a for a in assignments if a["academic_year_id"] == str(next_year.id))
    assert new_year_assignment["class_id"] == str(next_class.id)
    assert new_year_assignment["is_active"] is True


@pytest.mark.asyncio
async def test_bulk_promote_demoted_type_accepted(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_year: AcademicYear,
    next_class: Class, next_year: AcademicYear,
):
    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_year)

    resp = await client.post("/students/promotions/bulk", json={
        "academic_year_id": str(next_year.id),
        "records": [{"student_id": sid, "graduation_type": "DEMOTED", "class_id": str(next_class.id)}],
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["records"][0]["graduation_type"] == "DEMOTED"


@pytest.mark.asyncio
async def test_bulk_promote_rejects_exit_type(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_year: AcademicYear,
    next_class: Class, next_year: AcademicYear,
):
    sid = await _create_student(client, auth)
    resp = await client.post("/students/promotions/bulk", json={
        "academic_year_id": str(next_year.id),
        "records": [{"student_id": sid, "graduation_type": "GRADUATED", "class_id": str(next_class.id)}],
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_promote_idempotent(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_year: AcademicYear,
    next_class: Class, next_year: AcademicYear,
):
    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_year)
    payload = {
        "academic_year_id": str(next_year.id),
        "records": [{"student_id": sid, "graduation_type": "PROMOTED", "class_id": str(next_class.id)}],
    }
    first = await client.post("/students/promotions/bulk", json=payload, headers=auth)
    assert first.json()["processed"] == 1

    second = await client.post("/students/promotions/bulk", json=payload, headers=auth)
    assert second.status_code == 201
    assert second.json()["processed"] == 0
    assert second.json()["skipped"] == 1


@pytest.mark.asyncio
async def test_bulk_promote_also_enrolls_term(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_year: AcademicYear,
    next_class: Class, next_year: AcademicYear,
    db_session: AsyncSession, school: School,
):
    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_year)

    next_term = AcademicTerm(
        school_id=school.id, academic_year_id=next_year.id,
        term_number=1, name="Term 1",
        start_date=date(2025, 9, 1), end_date=date(2025, 12, 20), is_current=False,
    )
    db_session.add(next_term)
    await db_session.flush()

    resp = await client.post("/students/promotions/bulk", json={
        "academic_year_id": str(next_year.id),
        "academic_term_id": str(next_term.id),
        "records": [{"student_id": sid, "graduation_type": "PROMOTED", "class_id": str(next_class.id)}],
    }, headers=auth)
    assert resp.status_code == 201

    terms = (await client.get(f"/students/{sid}/term-enrollments", headers=auth)).json()
    assert any(t["academic_term_id"] == str(next_term.id) for t in terms)


# ── Graduation exit cascade ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_graduation_revokes_portal_access_and_closes_term_enrollment(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm,
):
    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_year)
    await client.post("/students/term-enrollments", json={
        "student_id": sid, "academic_term_id": str(academic_term.id),
    }, headers=auth)
    grant = await client.post(f"/students/{sid}/grant-portal-access", headers=auth)
    assert grant.status_code == 201

    resp = await client.post("/students/graduation/bulk", json={
        "academic_year_id": str(academic_year.id),
        "records": [{"student_id": sid, "graduation_type": "GRADUATED"}],
        "deactivate_students": True,
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["processed"] == 1

    detail = (await client.get(f"/students/{sid}", headers=auth)).json()
    assert detail["is_active"] is False

    terms = (await client.get(f"/students/{sid}/term-enrollments", headers=auth)).json()
    assert all(t["is_active"] is False for t in terms)

    # Portal login revoked: a second grant should succeed (no active user blocking it)
    # rather than 409 "already has portal access".
    regrant = await client.post(f"/students/{sid}/grant-portal-access", headers=auth)
    assert regrant.status_code == 201


@pytest.mark.asyncio
async def test_bulk_graduate_idempotent(client: AsyncClient, auth: dict, academic_year: AcademicYear):
    sid = await _create_student(client, auth)
    payload = {
        "academic_year_id": str(academic_year.id),
        "records": [{"student_id": sid, "graduation_type": "GRADUATED"}],
        "deactivate_students": True,
    }
    first = await client.post("/students/graduation/bulk", json=payload, headers=auth)
    assert first.json()["processed"] == 1

    second = await client.post("/students/graduation/bulk", json=payload, headers=auth)
    assert second.json()["processed"] == 0
    assert second.json()["skipped"] == 1


@pytest.mark.asyncio
async def test_transfer_approval_revokes_portal_access(client: AsyncClient, auth: dict):
    sid = await _create_student(client, auth)
    grant = await client.post(f"/students/{sid}/grant-portal-access", headers=auth)
    assert grant.status_code == 201

    tr_id = (await client.post(f"/students/{sid}/transfers", json={}, headers=auth)).json()["id"]
    resp = await client.patch(f"/students/transfers/{tr_id}/review",
        json={"status": "APPROVED"}, headers=auth)
    assert resp.status_code == 200

    regrant = await client.post(f"/students/{sid}/grant-portal-access", headers=auth)
    assert regrant.status_code == 201


# ── Manual deactivate / reactivate (student profile page) ─────────────────────
# grant_portal_access() itself has a "re-activate if previously revoked" branch,
# so re-calling it after reactivation would mask whether reactivate_student()
# actually did the restoring — assert the portal User row directly instead.

@pytest.mark.asyncio
async def test_manual_deactivate_cascades_to_class_term_and_portal(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm,
):
    """Deactivating via PATCH /students/{id} (not via transfer/graduation)
    must cascade the same way — previously this bypassed the cascade
    entirely, leaving the class assignment, term enrollment, and portal
    login all still active."""
    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_year)
    await client.post("/students/term-enrollments", json={
        "student_id": sid, "academic_term_id": str(academic_term.id),
    }, headers=auth)
    grant = await client.post(f"/students/{sid}/grant-portal-access", headers=auth)
    assert grant.status_code == 201

    resp = await client.patch(f"/students/{sid}", json={"is_active": False}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    assignments = (await client.get(f"/students/{sid}/class-assignments", headers=auth)).json()
    assert all(a["is_active"] is False for a in assignments)

    terms = (await client.get(f"/students/{sid}/term-enrollments", headers=auth)).json()
    assert all(t["is_active"] is False for t in terms)

    user = await db_session.scalar(select(User).where(User.student_id == sid))
    assert user.is_active is False


@pytest.mark.asyncio
async def test_reactivate_restores_class_term_and_portal(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm,
):
    """A student reactivated within the same academic year gets their
    previous class assignment, term enrollment, and portal login back —
    without staff having to manually re-assign anything."""
    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_year)
    await client.post("/students/term-enrollments", json={
        "student_id": sid, "academic_term_id": str(academic_term.id),
    }, headers=auth)
    await client.post(f"/students/{sid}/grant-portal-access", headers=auth)
    await client.patch(f"/students/{sid}", json={"is_active": False}, headers=auth)

    resp = await client.patch(f"/students/{sid}", json={"is_active": True}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True

    assignments = (await client.get(f"/students/{sid}/class-assignments", headers=auth)).json()
    current = next(a for a in assignments if a["academic_year_id"] == str(academic_year.id))
    assert current["is_active"] is True
    assert current["class_id"] == str(school_class.id)

    terms = (await client.get(f"/students/{sid}/term-enrollments", headers=auth)).json()
    current_term = next(t for t in terms if t["academic_term_id"] == str(academic_term.id))
    assert current_term["is_active"] is True

    user = await db_session.scalar(select(User).where(User.student_id == sid))
    assert user.is_active is True


@pytest.mark.asyncio
async def test_reactivate_skips_term_restore_when_fee_gate_blocks(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    student: Student, school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm,
    fee_record: StudentFeeRecord,
):
    """Restoring class/term on reactivation is best-effort — if the fee gate
    now blocks the term (e.g. new charges accrued while the student was
    away), Student.is_active and the portal login must still be restored;
    only the term enrollment restore is skipped, for staff to finish
    manually with a waiver via EnrollmentTab."""
    sid = str(student.id)
    await _assign_class(client, auth, sid, school_class, academic_year)
    await client.post("/students/term-enrollments", json={
        "student_id": sid, "academic_term_id": str(academic_term.id),
    }, headers=auth)
    await client.post(f"/students/{sid}/grant-portal-access", headers=auth)
    await client.patch(f"/students/{sid}", json={"is_active": False}, headers=auth)

    await client.patch(f"/academic/terms/{academic_term.id}", json={
        "block_owing_students": True,
    }, headers=auth)

    resp = await client.patch(f"/students/{sid}", json={"is_active": True}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True

    user = await db_session.scalar(select(User).where(User.student_id == student.id))
    assert user.is_active is True

    terms = (await client.get(f"/students/{sid}/term-enrollments", headers=auth)).json()
    current_term = next(t for t in terms if t["academic_term_id"] == str(academic_term.id))
    assert current_term["is_active"] is False


@pytest.mark.asyncio
async def test_reassign_to_class_reactivates_stale_assignment(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_year: AcademicYear, next_class: Class,
):
    """The manual EnrollmentTab path: assigning a student with an existing
    inactive class-assignment row for that year to a (possibly different)
    class reactivates the row in place instead of 409ing."""
    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_year)
    await client.patch(f"/students/{sid}", json={"is_active": False}, headers=auth)

    resp = await client.post("/students/class-assignments", json={
        "student_id": sid,
        "class_id": str(next_class.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["class_id"] == str(next_class.id)
    assert resp.json()["is_active"] is True
