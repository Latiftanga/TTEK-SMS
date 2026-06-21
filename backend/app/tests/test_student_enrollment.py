"""
Student enrollment integration tests — initial enrollment, term enrollment,
subject registration, and transfer requests.
Run inside Docker: docker compose exec api pytest app/tests/test_student_enrollment.py -v
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class
from app.models.school import School


async def _assign_class(client, auth, student_id: str, school_class: Class, academic_term: AcademicTerm):
    """Create a StudentClassAssignment before enrolling for a term."""
    resp = await client.post("/students/class-assignments", json={
        "student_id": student_id,
        "class_id": str(school_class.id),
        "academic_year_id": str(academic_term.academic_year_id),
    }, headers=auth)
    assert resp.status_code == 201
    return resp.json()


async def _create_student(client, auth, num="ADM001"):
    resp = await client.post("/students", json={
        "admission_number": num, "first_name": "Kwame", "last_name": "Asante",
    }, headers=auth)
    assert resp.status_code == 201
    return resp.json()["id"]


# ── Initial enrollment ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_initial_enrollment(client: AsyncClient, auth: dict):
    sid = await _create_student(client, auth)
    resp = await client.post(f"/students/{sid}/enroll", json={
        "enrolled_at": "2024-09-02",
        "enrollment_type": "NEW",
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["enrollment_type"] == "NEW"


@pytest.mark.asyncio
async def test_transfer_enrollment_records_source_school(client: AsyncClient, auth: dict):
    sid = await _create_student(client, auth)
    resp = await client.post(f"/students/{sid}/enroll", json={
        "enrolled_at": "2024-09-02",
        "enrollment_type": "TRANSFER",
        "transfer_from_school": "Accra Academy",
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["transfer_from_school"] == "Accra Academy"


# ── Term enrollment ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_class_assignment(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
):
    sid = await _create_student(client, auth)
    data = await _assign_class(client, auth, sid, school_class, academic_term)
    assert data["student_id"] == sid
    assert data["class_id"] == str(school_class.id)
    assert "class_display_name" in data
    assert data["class_display_name"]


@pytest.mark.asyncio
async def test_duplicate_class_assignment_rejected(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
):
    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    resp = await client.post("/students/class-assignments", json={
        "student_id": sid,
        "class_id": str(school_class.id),
        "academic_year_id": str(academic_term.academic_year_id),
    }, headers=auth)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_term_enrollment(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
):
    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    resp = await client.post("/students/term-enrollments", json={
        "student_id": sid,
        "academic_term_id": str(academic_term.id),
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["student_id"] == sid
    assert "class_display_name" in data
    assert data["class_display_name"]  # derived from StudentClassAssignment


@pytest.mark.asyncio
async def test_term_enrollment_requires_class_assignment(
    client: AsyncClient, auth: dict,
    academic_term: AcademicTerm,
):
    sid = await _create_student(client, auth)
    resp = await client.post("/students/term-enrollments", json={
        "student_id": sid,
        "academic_term_id": str(academic_term.id),
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_term_enrollment_rejected(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
):
    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    payload = {"student_id": sid, "academic_term_id": str(academic_term.id)}
    await client.post("/students/term-enrollments", json=payload, headers=auth)
    resp = await client.post("/students/term-enrollments", json=payload, headers=auth)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_term_enrollments(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
):
    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    await client.post("/students/term-enrollments", json={
        "student_id": sid,
        "academic_term_id": str(academic_term.id),
    }, headers=auth)
    resp = await client.get(f"/students/{sid}/term-enrollments", headers=auth)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_list_students_by_class(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
):
    sid1 = await _create_student(client, auth, "ADM001")
    sid2 = await _create_student(client, auth, "ADM002")
    # Assign only sid1 to the class
    await _assign_class(client, auth, sid1, school_class, academic_term)
    resp = await client.get(
        f"/students?class_id={school_class.id}",
        headers=auth,
    )
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert sid1 in ids
    assert sid2 not in ids


# ── Subject registration ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_subjects(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
    db_session: AsyncSession, school: School,
):
    from app.models.academic import Subject
    sub = Subject(school_id=school.id, code="MATH01", name="Mathematics", is_active=True)
    db_session.add(sub)
    await db_session.flush()

    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    te_id = (await client.post("/students/term-enrollments", json={
        "student_id": sid,
        "academic_term_id": str(academic_term.id),
    }, headers=auth)).json()["id"]

    resp = await client.post(f"/students/term-enrollments/{te_id}/subjects", json=[
        {"subject_id": str(sub.id), "registration_type": "CORE"},
    ], headers=auth)
    assert resp.status_code == 201
    assert len(resp.json()) == 1
    assert resp.json()[0]["registration_type"] == "CORE"


@pytest.mark.asyncio
async def test_duplicate_subject_skipped_silently(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
    db_session: AsyncSession, school: School,
):
    from app.models.academic import Subject
    sub = Subject(school_id=school.id, code="ENG01", name="English", is_active=True)
    db_session.add(sub)
    await db_session.flush()

    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    te_id = (await client.post("/students/term-enrollments", json={
        "student_id": sid,
        "academic_term_id": str(academic_term.id),
    }, headers=auth)).json()["id"]

    await client.post(f"/students/term-enrollments/{te_id}/subjects", json=[
        {"subject_id": str(sub.id), "registration_type": "CORE"},
    ], headers=auth)
    # Register same subject again — should silently skip
    resp = await client.post(f"/students/term-enrollments/{te_id}/subjects", json=[
        {"subject_id": str(sub.id), "registration_type": "CORE"},
    ], headers=auth)
    assert resp.status_code == 201
    assert resp.json() == []   # nothing new registered


# ── Transfer requests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_and_approve_transfer(client: AsyncClient, auth: dict):
    sid = await _create_student(client, auth)
    tr_resp = await client.post(f"/students/{sid}/transfers", json={
        "reason": "Family relocation",
    }, headers=auth)
    assert tr_resp.status_code == 201
    tr_id = tr_resp.json()["id"]
    assert tr_resp.json()["status"] == "PENDING"

    # Appears in pending list
    pending = (await client.get("/students/transfers/pending", headers=auth)).json()
    assert any(t["id"] == tr_id for t in pending)

    # Approve it — student should become inactive
    resp = await client.patch(f"/students/transfers/{tr_id}/review",
        json={"status": "APPROVED"}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["status"] == "APPROVED"

    detail = (await client.get(f"/students/{sid}", headers=auth)).json()
    assert detail["is_active"] is False


@pytest.mark.asyncio
async def test_double_review_rejected(client: AsyncClient, auth: dict):
    sid = await _create_student(client, auth)
    tr_id = (await client.post(f"/students/{sid}/transfers", json={}, headers=auth)).json()["id"]
    await client.patch(f"/students/transfers/{tr_id}/review", json={"status": "REJECTED"}, headers=auth)
    resp = await client.patch(f"/students/transfers/{tr_id}/review", json={"status": "APPROVED"}, headers=auth)
    assert resp.status_code == 409
