"""
StudentBehaviourRecord integration tests for the additions made alongside the
term results lock: incident_date term-bounds validation, results_locked
freeze + override, and BehaviourAuditLog write-on-create/delete.

Run inside Docker: docker compose exec api pytest app/tests/test_behaviour_lock.py -v
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm
from app.models.assessments import BehaviourAuditLog
from app.models.students import Student


async def _lock_term(client: AsyncClient, auth: dict, term_id) -> None:
    resp = await client.patch(f"/academic/terms/{term_id}", json={"results_locked": True}, headers=auth)
    assert resp.status_code == 200


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
