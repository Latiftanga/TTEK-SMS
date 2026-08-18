"""
StudentBehaviourRecord integration tests for the additions made alongside the
term results lock: incident_date term-bounds validation, results_locked
freeze + override, and BehaviourAuditLog write-on-create/delete.

Run inside Docker: docker compose exec api pytest app/tests/test_behaviour_lock.py -v
"""
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import AcademicTerm, AcademicYear, Class, ClassTeacher
from app.models.assessments import BehaviourAuditLog
from app.models.auth import LoginType, PositionPermission, StaffPosition, User
from app.models.school import School
from app.models.students import Student, StudentClassAssignment
from app.tests.legacy_position_perms import LEGACY_POSITION_PERMISSIONS


async def _lock_term(client: AsyncClient, auth: dict, term_id) -> None:
    resp = await client.patch(f"/academic/terms/{term_id}", json={"results_locked": True}, headers=auth)
    assert resp.status_code == 200


async def _login_as_position(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, position_code: str,
) -> tuple[dict, str]:
    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == position_code))
    if pos is None and position_code in LEGACY_POSITION_PERMISSIONS:
        pos = StaffPosition(school_id=school.id, code=position_code, name=position_code.title(), is_template=False)
        db_session.add(pos)
        await db_session.flush()
        for module, action in LEGACY_POSITION_PERMISSIONS[position_code]:
            db_session.add(PositionPermission(position_id=pos.id, module=module, action=action, is_allowed=True))
        await db_session.flush()
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


async def _assign_class(
    db_session: AsyncSession, school: School, student: Student, cls: Class, year: AcademicYear,
) -> None:
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=cls.id,
        academic_year_id=year.id, is_active=True,
    ))
    await db_session.flush()


def _payload(student: Student, academic_term: AcademicTerm, **overrides) -> dict:
    base = {
        "student_id": str(student.id),
        "academic_term_id": str(academic_term.id),
        "incident_type": "Late to class",
        "description": "Student arrived 20 minutes late without excuse.",
        "severity": "LOW",
        "incident_date": "2024-10-15",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_incident_date_outside_term_rejected(
    client: AsyncClient, auth: dict, student: Student, academic_term: AcademicTerm,
):
    # academic_term runs 2024-09-01 to 2024-12-20
    resp = await client.post(
        "/behaviour", json=_payload(student, academic_term, incident_date="2025-03-01"), headers=auth
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_behaviour_record_writes_audit_log(
    client: AsyncClient, auth: dict, student: Student, academic_term: AcademicTerm, db_session: AsyncSession,
):
    resp = await client.post("/behaviour", json=_payload(student, academic_term), headers=auth)
    assert resp.status_code == 201
    record_id = resp.json()["id"]

    log = await db_session.scalar(
        select(BehaviourAuditLog).where(BehaviourAuditLog.behaviour_record_id == record_id)
    )
    assert log is not None
    assert log.action == "CREATE"
    assert log.reason is None


@pytest.mark.asyncio
async def test_create_behaviour_record_blocked_when_term_locked_without_reason(
    client: AsyncClient, auth: dict, student: Student, academic_term: AcademicTerm,
):
    await _lock_term(client, auth, academic_term.id)
    resp = await client.post("/behaviour", json=_payload(student, academic_term), headers=auth)
    assert resp.status_code == 423


@pytest.mark.asyncio
async def test_create_behaviour_record_allowed_when_locked_with_reason(
    client: AsyncClient, auth: dict, student: Student, academic_term: AcademicTerm, db_session: AsyncSession,
):
    await _lock_term(client, auth, academic_term.id)
    resp = await client.post("/behaviour", json=_payload(
        student, academic_term, override_reason="Late-filed incident, approved by HOD.",
    ), headers=auth)
    assert resp.status_code == 201
    record_id = resp.json()["id"]

    log = await db_session.scalar(
        select(BehaviourAuditLog).where(BehaviourAuditLog.behaviour_record_id == record_id)
    )
    assert log.reason == "Late-filed incident, approved by HOD."


@pytest.mark.asyncio
async def test_delete_behaviour_record_blocked_when_term_locked(
    client: AsyncClient, auth: dict, student: Student, academic_term: AcademicTerm,
):
    r = await client.post("/behaviour", json=_payload(student, academic_term), headers=auth)
    record_id = r.json()["id"]

    await _lock_term(client, auth, academic_term.id)
    resp = await client.delete(f"/behaviour/{record_id}", headers=auth)
    assert resp.status_code == 423


@pytest.mark.asyncio
async def test_delete_behaviour_record_allowed_when_locked_with_reason_writes_audit_log(
    client: AsyncClient, auth: dict, student: Student, academic_term: AcademicTerm, db_session: AsyncSession,
):
    r = await client.post("/behaviour", json=_payload(student, academic_term), headers=auth)
    record_id = r.json()["id"]

    await _lock_term(client, auth, academic_term.id)
    resp = await client.delete(
        f"/behaviour/{record_id}", params={"override_reason": "Filed in error"}, headers=auth
    )
    assert resp.status_code == 204

    log = await db_session.scalar(
        select(BehaviourAuditLog).where(
            BehaviourAuditLog.behaviour_record_id.is_(None),
            BehaviourAuditLog.action == "DELETE",
            BehaviourAuditLog.student_id == student.id,
        )
    )
    assert log is not None
    assert log.reason == "Filed in error"


# ── Current-term enforcement (distinct from results_locked) ────────────────────

@pytest.fixture
async def noncurrent_term(db_session: AsyncSession, school: School, academic_year: AcademicYear) -> AcademicTerm:
    term = AcademicTerm(
        school_id=school.id, academic_year_id=academic_year.id,
        term_number=2, name="Term 2 (not current)",
        start_date=date(2024, 12, 21), end_date=date(2025, 4, 15), is_current=False,
    )
    db_session.add(term)
    await db_session.flush()
    return term


@pytest.mark.asyncio
async def test_create_blocked_outside_current_term_without_approve_scores(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    student: Student, school_class: Class, academic_year: AcademicYear,
    noncurrent_term: AcademicTerm, redis_permissions: None,
):
    await _assign_class(db_session, school, student, school_class, academic_year)
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.post(
        "/behaviour",
        json=_payload(student, noncurrent_term, incident_date="2025-01-10"),
        headers=teacher_auth,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_allowed_outside_current_term_for_approve_scores_holder(
    client: AsyncClient, auth: dict, student: Student, noncurrent_term: AcademicTerm,
):
    resp = await client.post(
        "/behaviour",
        json=_payload(student, noncurrent_term, incident_date="2025-01-10"),
        headers=auth,
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_blocked_outside_current_term_without_approve_scores(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    student: Student, school_class: Class, academic_year: AcademicYear,
    noncurrent_term: AcademicTerm, redis_permissions: None,
):
    r = await client.post(
        "/behaviour",
        json=_payload(student, noncurrent_term, incident_date="2025-01-10"),
        headers=auth,
    )
    record_id = r.json()["id"]

    await _assign_class(db_session, school, student, school_class, academic_year)
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.delete(f"/behaviour/{record_id}", headers=teacher_auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_allowed_outside_current_term_for_approve_scores_holder(
    client: AsyncClient, auth: dict, student: Student, noncurrent_term: AcademicTerm,
):
    r = await client.post(
        "/behaviour",
        json=_payload(student, noncurrent_term, incident_date="2025-01-10"),
        headers=auth,
    )
    record_id = r.json()["id"]

    resp = await client.delete(f"/behaviour/{record_id}", headers=auth)
    assert resp.status_code == 204
