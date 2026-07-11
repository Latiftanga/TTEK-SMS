"""
Year-end outcome tests — promotion/repetition/demotion (progression) and
graduation (exit), including the portal-login/term-enrollment exit cascade.
Run inside Docker: docker compose exec api pytest app/tests/test_student_lifecycle.py -v
"""
import pytest
from datetime import date
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, AcademicYear, Class
from app.models.school import School


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
