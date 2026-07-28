"""
Fee payments, discounts, instalment plans, and summary trigger integration tests.
Run inside Docker: docker compose exec api pytest app/tests/test_fees_payment.py -v
"""
import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm
from app.models.fees import StudentFeeRecord
from app.models.students import Student


# ── Payments ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_payment(
    client: AsyncClient, auth: dict,
    student: Student, academic_term: AcademicTerm, fee_record: StudentFeeRecord
):
    resp = await client.post("/fees/payments", json={
        "fee_record_id": str(fee_record.id),
        "amount_paid": "200.00",
        "payment_method": "CASH",
        "payment_date": "2024-10-01",
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["amount_paid"] == "200.00"
    assert data["payment_method"] == "CASH"
    assert data["student_id"] == str(student.id)


@pytest.mark.asyncio
async def test_payment_ignores_client_supplied_student_id(
    client: AsyncClient, auth: dict,
    student: Student, academic_term: AcademicTerm, fee_record: StudentFeeRecord
):
    """student_id is derived from the fee record server-side — a caller-supplied
    value (even a mismatched one) must never be trusted, since the DB trigger
    that refreshes StudentFeeSummary keys off this column."""
    resp = await client.post("/fees/payments", json={
        "student_id": str(uuid.uuid4()),  # ignored — not part of the schema anymore
        "fee_record_id": str(fee_record.id),
        "amount_paid": "200.00",
        "payment_method": "CASH",
        "payment_date": "2024-10-01",
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["student_id"] == str(student.id)


@pytest.mark.asyncio
async def test_payment_on_waived_record_rejected(
    client: AsyncClient, auth: dict,
    db_session: AsyncSession,
    student: Student, academic_term: AcademicTerm, fee_record: StudentFeeRecord
):
    fee_record.is_waived = True
    await db_session.flush()
    resp = await client.post("/fees/payments", json={
        "fee_record_id": str(fee_record.id),
        "amount_paid": "200.00",
        "payment_method": "CASH",
        "payment_date": "2024-10-01",
    }, headers=auth)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_payment_negative_amount_rejected(
    client: AsyncClient, auth: dict,
    student: Student, fee_record: StudentFeeRecord
):
    resp = await client.post("/fees/payments", json={
        "fee_record_id": str(fee_record.id),
        "amount_paid": "-50",
        "payment_method": "CASH",
        "payment_date": "2024-10-01",
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_payments(
    client: AsyncClient, auth: dict,
    student: Student, academic_term: AcademicTerm, fee_record: StudentFeeRecord
):
    await client.post("/fees/payments", json={
        "fee_record_id": str(fee_record.id),
        "amount_paid": "100.00",
        "payment_method": "MOBILE_MONEY",
        "payment_date": "2024-10-05",
    }, headers=auth)
    resp = await client.get(
        f"/fees/payments?student_id={student.id}&term_id={academic_term.id}", headers=auth
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── Discounts ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_discount_ignores_client_supplied_student_id(
    client: AsyncClient, auth: dict,
    student: Student, fee_record: StudentFeeRecord
):
    """Same derive-from-record guarantee as payments — see
    test_payment_ignores_client_supplied_student_id."""
    resp = await client.post("/fees/discounts", json={
        "student_id": str(uuid.uuid4()),  # ignored — not part of the schema anymore
        "fee_record_id": str(fee_record.id),
        "discount_type": "SCHOLARSHIP",
        "amount": "50.00",
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["student_id"] == str(student.id)


@pytest.mark.asyncio
async def test_apply_fixed_discount(
    client: AsyncClient, auth: dict,
    student: Student, fee_record: StudentFeeRecord
):
    resp = await client.post("/fees/discounts", json={
        "fee_record_id": str(fee_record.id),
        "discount_type": "SCHOLARSHIP",
        "amount": "100.00",
        "reason": "Academic excellence",
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["amount"] == "100.00"
    assert data["percentage"] is None


@pytest.mark.asyncio
async def test_apply_percentage_discount(
    client: AsyncClient, auth: dict,
    student: Student, fee_record: StudentFeeRecord
):
    resp = await client.post("/fees/discounts", json={
        "fee_record_id": str(fee_record.id),
        "discount_type": "BURSARY",
        "percentage": "20.00",
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["percentage"] == "20.00"
    assert data["amount"] is None


@pytest.mark.asyncio
async def test_discount_both_amount_and_percentage_rejected(
    client: AsyncClient, auth: dict,
    student: Student, fee_record: StudentFeeRecord
):
    resp = await client.post("/fees/discounts", json={
        "fee_record_id": str(fee_record.id),
        "discount_type": "SIBLING",
        "amount": "50.00",
        "percentage": "10.00",
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_discount_neither_amount_nor_percentage_rejected(
    client: AsyncClient, auth: dict,
    student: Student, fee_record: StudentFeeRecord
):
    resp = await client.post("/fees/discounts", json={
        "fee_record_id": str(fee_record.id),
        "discount_type": "OTHER",
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_discount_percentage_over_100_rejected(
    client: AsyncClient, auth: dict,
    student: Student, fee_record: StudentFeeRecord
):
    resp = await client.post("/fees/discounts", json={
        "fee_record_id": str(fee_record.id),
        "discount_type": "SCHOLARSHIP",
        "percentage": "110.00",
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_discounts(
    client: AsyncClient, auth: dict,
    student: Student, academic_term: AcademicTerm, fee_record: StudentFeeRecord
):
    await client.post("/fees/discounts", json={
        "fee_record_id": str(fee_record.id),
        "discount_type": "STAFF_WARD",
        "amount": "75.00",
    }, headers=auth)
    resp = await client.get(
        f"/fees/discounts?student_id={student.id}&term_id={academic_term.id}", headers=auth
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── Instalment plans ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_instalment_plan(
    client: AsyncClient, auth: dict, fee_record: StudentFeeRecord
):
    resp = await client.put(f"/fees/records/{fee_record.id}/instalments", json=[
        {"instalment_number": 1, "amount": "200.00", "due_date": "2024-10-01"},
        {"instalment_number": 2, "amount": "150.00", "due_date": "2024-11-01"},
        {"instalment_number": 3, "amount": "150.00", "due_date": "2024-12-01"},
    ], headers=auth)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 3
    assert items[0]["instalment_number"] == 1


@pytest.mark.asyncio
async def test_replace_instalment_plan(
    client: AsyncClient, auth: dict, fee_record: StudentFeeRecord
):
    """Calling PUT a second time replaces the entire plan."""
    await client.put(f"/fees/records/{fee_record.id}/instalments", json=[
        {"instalment_number": 1, "amount": "250.00", "due_date": "2024-10-01"},
        {"instalment_number": 2, "amount": "250.00", "due_date": "2024-11-01"},
    ], headers=auth)
    resp = await client.put(f"/fees/records/{fee_record.id}/instalments", json=[
        {"instalment_number": 1, "amount": "500.00", "due_date": "2024-10-15"},
    ], headers=auth)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["amount"] == "500.00"


@pytest.mark.asyncio
async def test_duplicate_instalment_numbers_rejected(
    client: AsyncClient, auth: dict, fee_record: StudentFeeRecord
):
    resp = await client.put(f"/fees/records/{fee_record.id}/instalments", json=[
        {"instalment_number": 1, "amount": "250.00", "due_date": "2024-10-01"},
        {"instalment_number": 1, "amount": "250.00", "due_date": "2024-11-01"},
    ], headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_instalments(
    client: AsyncClient, auth: dict, fee_record: StudentFeeRecord
):
    await client.put(f"/fees/records/{fee_record.id}/instalments", json=[
        {"instalment_number": 1, "amount": "300.00", "due_date": "2024-10-01"},
        {"instalment_number": 2, "amount": "200.00", "due_date": "2024-11-01"},
    ], headers=auth)
    resp = await client.get(f"/fees/records/{fee_record.id}/instalments", headers=auth)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    assert items[0]["instalment_number"] == 1


# ── Summary trigger ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fee_summary_updated_after_payment(
    client: AsyncClient, auth: dict,
    student: Student, academic_term: AcademicTerm, fee_record: StudentFeeRecord
):
    """The DB trigger fires on fee_payment INSERT, populating StudentFeeSummary."""
    await client.post("/fees/payments", json={
        "fee_record_id": str(fee_record.id),
        "amount_paid": "300.00",
        "payment_method": "BANK_TRANSFER",
        "payment_date": "2024-10-10",
    }, headers=auth)
    resp = await client.get(
        f"/fees/students/{student.id}/summary?term_id={academic_term.id}", headers=auth
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["total_due"]) == 500.0
    assert float(data["total_paid"]) == 300.0
    assert float(data["balance"]) == 200.0


@pytest.mark.asyncio
async def test_fee_summary_balance_after_discount(
    client: AsyncClient, auth: dict,
    student: Student, academic_term: AcademicTerm, fee_record: StudentFeeRecord
):
    """Percentage discount of 10% on 500 GHS = 50 GHS discounted; balance = 450."""
    await client.post("/fees/discounts", json={
        "fee_record_id": str(fee_record.id),
        "discount_type": "SCHOLARSHIP",
        "percentage": "10.00",
    }, headers=auth)
    resp = await client.get(
        f"/fees/students/{student.id}/summary?term_id={academic_term.id}", headers=auth
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["total_discounted"]) == 50.0
    assert float(data["balance"]) == 450.0
