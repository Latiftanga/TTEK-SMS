"""
Password-reset OTP delivery — services/auth_reset.py.
Run inside Docker: docker compose exec api pytest app/tests/test_auth_reset.py -v

A student (ADMISSION_ID) account has no phone of its own — Student has no
phone field at all — so _resolve_phone() must fall back to the primary
guardian's phone, mirroring services/student_portal.py::_notify_guardian's
query. Before this fix, forgot_password() silently no-op'd for every
student: POST /auth/forgot-password always returns 204/200 regardless (to
prevent account enumeration), so the frontend proceeded to the OTP screen
even though nothing was ever sent — a real dead end, not just a rough edge.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import LoginType, User
from app.models.school import School
from app.models.students import Student
from app.services.auth_reset import _reset_sms_text, _resolve_phone


def _student(num: str, **kw) -> dict:
    return {"admission_number": num, "first_name": "Kojo", "last_name": "Mensah", **kw}


@pytest.mark.asyncio
async def test_forgot_password_student_with_guardian_phone_returns_otp(
    client: AsyncClient, auth: dict, school: School,
):
    """The regression this fix closes: settings.is_development (the test
    default) only exposes dev_otp when forgot_password() actually generated
    one — a plain 204 wouldn't distinguish "OTP sent" from "silently
    skipped," so dev_otp being present is the real proof the fix works."""
    sid = (await client.post("/students", json=_student("ADM_RESET01"), headers=auth)).json()["id"]
    await client.post(f"/students/{sid}/guardians", json={
        "first_name": "Yaw", "last_name": "Mensah",
        "phone": "0244000099", "relation_type": "Father", "is_primary": True,
    }, headers=auth)
    grant = await client.post(f"/students/{sid}/grant-portal-access", headers=auth)
    assert grant.status_code == 201, grant.text

    resp = await client.post("/auth/forgot-password", json={
        "login_type": "ADMISSION_ID", "identifier": "ADM_RESET01",
        "school_code": school.school_code,
    })
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["dev_otp"]) == 6


@pytest.mark.asyncio
async def test_forgot_password_student_without_guardian_safely_noops(
    client: AsyncClient, auth: dict, school: School,
):
    """No guardian on record at all — _resolve_phone has nothing to fall
    back to. Must not crash and must not leak whether the account exists —
    same plain 204 as every other "nothing to send to" case."""
    sid = (await client.post("/students", json=_student("ADM_RESET02"), headers=auth)).json()["id"]
    grant = await client.post(f"/students/{sid}/grant-portal-access", headers=auth)
    assert grant.status_code == 201, grant.text

    resp = await client.post("/auth/forgot-password", json={
        "login_type": "ADMISSION_ID", "identifier": "ADM_RESET02",
        "school_code": school.school_code,
    })
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_reset_sms_text_includes_student_name(db_session: AsyncSession, school: School):
    """A student's reset code is relayed to a guardian, not the account
    holder — the message must name the student, since a guardian may also
    hold their own separate guardian-portal account with resets of its own,
    and shouldn't be left guessing which one a code belongs to."""
    student = Student(
        school_id=school.id, admission_number="ADM_RESET03",
        first_name="Abena", last_name="Owusu", is_active=True,
    )
    db_session.add(student)
    await db_session.flush()
    user = User(
        school_id=school.id, login_type=LoginType.ADMISSION_ID, admission_id="ADM_RESET03",
        password_hash="x", student_id=student.id, is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    msg = await _reset_sms_text(user, "654321", db_session)
    assert "Abena Owusu" in msg
    assert "654321" in msg


@pytest.mark.asyncio
async def test_resolve_phone_staff_path_unaffected(db_session: AsyncSession, school: School):
    """Regression — the new student/guardian branch must not change the
    pre-existing staff-phone resolution."""
    from app.models.staff import StaffMember
    staff = StaffMember(
        school_id=school.id, staff_number="RESET-ST01",
        first_name="Test", last_name="Staff", phone="0209990000",
    )
    db_session.add(staff)
    await db_session.flush()
    user = User(
        school_id=school.id, login_type=LoginType.PHONE, phone="0209990000",
        password_hash="x", staff_member_id=staff.id, is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    assert await _resolve_phone(user, db_session) == "0209990000"
