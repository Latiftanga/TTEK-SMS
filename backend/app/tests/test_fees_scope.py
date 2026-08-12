"""
Fees read-endpoint scoping tests — a plain fees.view holder (e.g.
CLASS_TEACHER/TEACHER) was previously able to read *any* student's fee
summary/records/payments/discounts school-wide, with no scoping at all,
unlike every other module. assert_can_view_student() (already used by
Students/Behaviour/Report Cards) closes that gap; fees.collect/manage
holders (BURSAR, HEAD, ...) stay unrestricted per
core/student_scope.py::resolve_student_view_scope's own bypass list.

Run inside Docker: docker compose exec api pytest app/tests/test_fees_scope.py -v
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import AcademicTerm, AcademicYear, Class, ClassTeacher
from app.models.auth import LoginType, StaffPosition, User
from app.models.fees import FeeStructure, FeeType, StudentFeeRecord
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
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, staff_id


async def _assign_class(
    db_session: AsyncSession, school: School, student: Student, cls: Class, year: AcademicYear,
) -> None:
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=cls.id,
        academic_year_id=year.id, is_active=True,
    ))
    await db_session.flush()


@pytest.mark.asyncio
async def test_get_fee_summary_404_for_class_teacher_outside_scope(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    student: Student, school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm,
    fee_record: StudentFeeRecord, redis_permissions: None,
):
    """CLASS_TEACHER holds fees.view but not fees.collect/manage — a student
    outside their own class must 404, not leak a balance."""
    teacher_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    resp = await client.get(
        f"/fees/students/{student.id}/summary?term_id={academic_term.id}", headers=teacher_auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_fee_summary_allowed_for_owning_class_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    student: Student, school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm,
    fee_record: StudentFeeRecord, redis_permissions: None,
):
    await _assign_class(db_session, school, student, school_class, academic_year)
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.get(
        f"/fees/students/{student.id}/summary?term_id={academic_term.id}", headers=teacher_auth,
    )
    # The trigger populates StudentFeeSummary as soon as the fee_record
    # itself is inserted (not just on payment/discount) — 200 here confirms
    # the scoping check passed, not just that a summary happens to exist.
    assert resp.status_code == 200
    assert resp.json()["balance"] == "500.00"


@pytest.mark.asyncio
async def test_list_payments_404_for_class_teacher_outside_scope(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    student: Student, school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm,
    fee_record: StudentFeeRecord, redis_permissions: None,
):
    await client.post("/fees/payments", json={
        "fee_record_id": str(fee_record.id), "amount_paid": "100.00",
        "payment_method": "CASH", "payment_date": "2024-10-01",
    }, headers=auth)

    teacher_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    resp = await client.get(
        f"/fees/payments?student_id={student.id}&term_id={academic_term.id}", headers=teacher_auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_payments_allowed_for_bursar_regardless_of_class(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    student: Student, academic_term: AcademicTerm, fee_record: StudentFeeRecord, redis_permissions: None,
):
    """fees.collect/manage holders (BURSAR, HEAD, ...) stay unrestricted —
    a bursar's job legitimately spans every student, no class assignment
    needed at all."""
    await client.post("/fees/payments", json={
        "fee_record_id": str(fee_record.id), "amount_paid": "100.00",
        "payment_method": "CASH", "payment_date": "2024-10-01",
    }, headers=auth)

    bursar_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "BURSAR")
    resp = await client.get(
        f"/fees/payments?student_id={student.id}&term_id={academic_term.id}", headers=bursar_auth,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
