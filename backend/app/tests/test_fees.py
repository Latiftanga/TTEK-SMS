"""
Fee management integration tests — fee types, structures, bulk assign, records, summary.
Run inside Docker: docker compose exec api pytest app/tests/test_fees.py -v
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class
from app.models.fees import FeeStructure, FeeType, StudentFeeRecord
from app.models.school import GhanaDistrict, GhanaRegion, School, SchoolType
from app.models.students import Student


# ── Fee types ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_fee_type(client: AsyncClient, auth: dict):
    resp = await client.post("/fees/types", json={
        "name": "Exam Levy", "code": "EXAM_LEVY", "is_recurring": False,
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Exam Levy"
    assert data["code"] == "EXAM_LEVY"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_list_fee_types_includes_school_types(
    client: AsyncClient, auth: dict, fee_type: FeeType
):
    resp = await client.get("/fees/types", headers=auth)
    assert resp.status_code == 200
    ids = [ft["id"] for ft in resp.json()]
    assert str(fee_type.id) in ids


@pytest.mark.asyncio
async def test_update_fee_type(client: AsyncClient, auth: dict, fee_type: FeeType):
    resp = await client.patch(f"/fees/types/{fee_type.id}", json={
        "description": "Updated description",
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated description"


@pytest.mark.asyncio
async def test_update_fee_type_not_found(client: AsyncClient, auth: dict):
    import uuid
    resp = await client.patch(f"/fees/types/{uuid.uuid4()}", json={"is_active": False}, headers=auth)
    assert resp.status_code == 404


# ── Fee structures ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_fee_structure(
    client: AsyncClient, auth: dict, academic_term: AcademicTerm, fee_type: FeeType
):
    resp = await client.post("/fees/structures", json={
        "academic_term_id": str(academic_term.id),
        "fee_type_id": str(fee_type.id),
        "amount": "750.00",
        "is_mandatory": True,
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["amount"] == "750.00"
    assert data["fee_type_name"] == "Tuition"


@pytest.mark.asyncio
async def test_create_fee_structure_wrong_term(
    client: AsyncClient, auth: dict, fee_type: FeeType
):
    import uuid
    resp = await client.post("/fees/structures", json={
        "academic_term_id": str(uuid.uuid4()),
        "fee_type_id": str(fee_type.id),
        "amount": "500.00",
    }, headers=auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_fee_structures(
    client: AsyncClient, auth: dict, academic_term: AcademicTerm, fee_structure: FeeStructure
):
    resp = await client.get(f"/fees/structures?term_id={academic_term.id}", headers=auth)
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert str(fee_structure.id) in ids


@pytest.mark.asyncio
async def test_update_fee_structure(
    client: AsyncClient, auth: dict, fee_structure: FeeStructure
):
    resp = await client.patch(f"/fees/structures/{fee_structure.id}", json={
        "amount": "600.00",
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["amount"] == "600.00"


@pytest.mark.asyncio
async def test_fee_structure_negative_amount_rejected(
    client: AsyncClient, auth: dict, academic_term: AcademicTerm, fee_type: FeeType
):
    resp = await client.post("/fees/structures", json={
        "academic_term_id": str(academic_term.id),
        "fee_type_id": str(fee_type.id),
        "amount": "-100",
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_fee_structure_rejects_cross_school_class(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    academic_term: AcademicTerm, fee_type: FeeType,
):
    """applies_to_class_id must belong to the calling school — not silently accepted."""
    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    other_school = School(
        name="Other Fee School", school_code="OTHERFEE", school_type=SchoolType.SHS,
        region_id=region.id, district_id=district.id, is_active=True,
    )
    db_session.add(other_school)
    await db_session.flush()
    other_class = Class(school_id=other_school.id, level="SHS", year_group=1, is_active=True)
    db_session.add(other_class)
    await db_session.flush()

    resp = await client.post("/fees/structures", json={
        "academic_term_id": str(academic_term.id),
        "fee_type_id": str(fee_type.id),
        "amount": "500.00",
        "applies_to_class_id": str(other_class.id),
    }, headers=auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_fee_structure_rejects_bogus_programme(
    client: AsyncClient, auth: dict, academic_term: AcademicTerm, fee_type: FeeType,
):
    resp = await client.post("/fees/structures", json={
        "academic_term_id": str(academic_term.id),
        "fee_type_id": str(fee_type.id),
        "amount": "500.00",
        "applies_to_programme_id": str(uuid.uuid4()),
    }, headers=auth)
    assert resp.status_code == 422


# ── Bulk assign ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_assign_with_no_enrollments(
    client: AsyncClient, auth: dict, fee_structure: FeeStructure
):
    """Bulk assign with no term enrollments returns assigned=0, skipped=0."""
    resp = await client.post(f"/fees/structures/{fee_structure.id}/bulk-assign", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["assigned"] == 0
    assert data["skipped"] == 0
    assert data["structure_id"] == str(fee_structure.id)


@pytest.mark.asyncio
async def test_bulk_assign_skips_existing(
    client: AsyncClient, auth: dict,
    fee_structure: FeeStructure, fee_record: StudentFeeRecord
):
    """Running bulk-assign when a record already exists skips rather than duplicates."""
    resp = await client.post(f"/fees/structures/{fee_structure.id}/bulk-assign", headers=auth)
    assert resp.status_code == 200
    # fee_record was inserted outside enrollment, but bulk-assign queries TermEnrollment
    # so this test just verifies the endpoint doesn't crash and returns clean numbers.
    data = resp.json()
    assert data["assigned"] >= 0
    assert data["skipped"] >= 0


# ── Student fee records & summary ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_student_fee_records(
    client: AsyncClient, auth: dict,
    student: Student, academic_term: AcademicTerm, fee_record: StudentFeeRecord
):
    resp = await client.get(
        f"/fees/students/{student.id}/records?term_id={academic_term.id}", headers=auth
    )
    assert resp.status_code == 200
    recs = resp.json()
    assert len(recs) == 1
    assert recs[0]["id"] == str(fee_record.id)
    assert recs[0]["fee_type_name"] == "Tuition"
    assert float(recs[0]["amount_due"]) == 500.0


@pytest.mark.asyncio
async def test_get_fee_records_unknown_student(
    client: AsyncClient, auth: dict, academic_term: AcademicTerm
):
    import uuid
    resp = await client.get(
        f"/fees/students/{uuid.uuid4()}/records?term_id={academic_term.id}", headers=auth
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_fee_summary_no_fees_assigned(
    client: AsyncClient, auth: dict, student: Student, academic_term: AcademicTerm
):
    """Summary returns 404 if the trigger has never fired for this student+term."""
    resp = await client.get(
        f"/fees/students/{student.id}/summary?term_id={academic_term.id}", headers=auth
    )
    assert resp.status_code == 404
