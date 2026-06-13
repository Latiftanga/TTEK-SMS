"""
Report card integration tests — behaviour records, PDF generation, QR verification.
Run inside Docker: docker compose exec api pytest app/tests/test_report_cards.py -v

These tests run against the real DB. PDF generation uses WeasyPrint so the
container must have libpango/libcairo installed (it does — see Dockerfile).
"""
import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class
from app.models.school import School
from app.models.students import Student, TermEnrollment
from app.models.auth import User


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _make_enrollment(
    db: AsyncSession, school: School, student: Student,
    school_class: Class, academic_term: AcademicTerm, school_admin: User
) -> TermEnrollment:
    te = TermEnrollment(
        school_id=school.id,
        student_id=student.id,
        class_id=school_class.id,
        academic_term_id=academic_term.id,
        enrolled_by_id=school_admin.id,
        is_active=True,
    )
    db.add(te)
    await db.flush()
    return te


# ── Behaviour records ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_behaviour_record(
    client: AsyncClient, auth: dict,
    student: Student, academic_term: AcademicTerm
):
    resp = await client.post("/behaviour", json={
        "student_id": str(student.id),
        "academic_term_id": str(academic_term.id),
        "incident_type": "Late to class",
        "description": "Student arrived 20 minutes late without excuse.",
        "severity": "LOW",
        "incident_date": "2024-10-15",
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["incident_type"] == "Late to class"
    assert data["severity"] == "LOW"


@pytest.mark.asyncio
async def test_create_behaviour_invalid_severity(
    client: AsyncClient, auth: dict,
    student: Student, academic_term: AcademicTerm
):
    resp = await client.post("/behaviour", json={
        "student_id": str(student.id),
        "academic_term_id": str(academic_term.id),
        "incident_type": "Test",
        "description": "Test",
        "severity": "CRITICAL",    # not a valid literal
        "incident_date": "2024-10-15",
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_behaviour_records(
    client: AsyncClient, auth: dict,
    student: Student, academic_term: AcademicTerm
):
    await client.post("/behaviour", json={
        "student_id": str(student.id),
        "academic_term_id": str(academic_term.id),
        "incident_type": "Fighting",
        "description": "Involved in altercation.",
        "severity": "HIGH",
        "incident_date": "2024-11-01",
    }, headers=auth)
    resp = await client.get(
        f"/behaviour?student_id={student.id}&term_id={academic_term.id}", headers=auth
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_behaviour_record(
    client: AsyncClient, auth: dict,
    student: Student, academic_term: AcademicTerm
):
    r = await client.post("/behaviour", json={
        "student_id": str(student.id),
        "academic_term_id": str(academic_term.id),
        "incident_type": "Noise",
        "description": "Disruptive in class.",
        "severity": "MEDIUM",
        "incident_date": "2024-10-20",
    }, headers=auth)
    record_id = r.json()["id"]
    resp = await client.delete(f"/behaviour/{record_id}", headers=auth)
    assert resp.status_code == 204


# ── Report card PDF ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_report_card_pdf_generated(
    client: AsyncClient, auth: dict,
    db_session: AsyncSession,
    school: School, student: Student, school_class: Class,
    academic_term: AcademicTerm, school_admin: User
):
    te = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    resp = await client.get(f"/report-cards/{te.id}?format=BASIC", headers=auth)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 1000   # non-trivial PDF


@pytest.mark.asyncio
async def test_report_card_shs_format(
    client: AsyncClient, auth: dict,
    db_session: AsyncSession,
    school: School, student: Student, school_class: Class,
    academic_term: AcademicTerm, school_admin: User
):
    te = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    resp = await client.get(f"/report-cards/{te.id}?format=SHS", headers=auth)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


@pytest.mark.asyncio
async def test_report_card_invalid_format(
    client: AsyncClient, auth: dict,
    db_session: AsyncSession,
    school: School, student: Student, school_class: Class,
    academic_term: AcademicTerm, school_admin: User
):
    te = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    resp = await client.get(f"/report-cards/{te.id}?format=INVALID", headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_report_card_unknown_enrollment(
    client: AsyncClient, auth: dict
):
    resp = await client.get(f"/report-cards/{uuid.uuid4()}", headers=auth)
    assert resp.status_code == 404


# ── QR verification ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_qr_verify_valid_token(
    client: AsyncClient, auth: dict,
    db_session: AsyncSession,
    school: School, student: Student, school_class: Class,
    academic_term: AcademicTerm, school_admin: User
):
    te = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    from app.services.qr import generate_token
    token = generate_token(te.id, school.id)
    resp = await client.get(f"/verify/{token}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["admission_number"] == student.admission_number


@pytest.mark.asyncio
async def test_qr_verify_tampered_token(client: AsyncClient):
    resp = await client.get("/verify/aGVsbG8.badhash123")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_qr_verify_garbage_token(client: AsyncClient):
    resp = await client.get("/verify/not-a-real-token")
    assert resp.status_code == 404
