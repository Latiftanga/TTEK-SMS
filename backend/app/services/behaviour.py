"""
Student behaviour record CRUD.

TERM LOCK
---------
Like scoring, AcademicTerm.results_locked freezes behaviour record create/
delete for that term. Both endpoints already require assessments.approve_scores
(see routers/report_cards.py), so an override here only needs a non-blank
override_reason — the permission is already guaranteed by the route.

Every create/delete is written to BehaviourAuditLog, independent of whether
the term was locked (reason is only populated on a locked-term override).
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm
from app.models.assessments import BehaviourAuditLog, StudentBehaviourRecord
from app.models.students import Student
from app.schemas.assessments import BehaviourRecordCreate, BehaviourRecordRead


def _to_read(r: StudentBehaviourRecord) -> BehaviourRecordRead:
    return BehaviourRecordRead.model_validate(r)


def _check_term_lock(term: AcademicTerm, requested_reason: str | None) -> str | None:
    if not term.results_locked:
        return None
    reason = (requested_reason or "").strip()
    if not reason:
        raise HTTPException(
            status.HTTP_423_LOCKED,
            "This term's results are locked. Supply an override_reason to push this through.",
        )
    return reason


async def create_behaviour_record(
    req: BehaviourRecordCreate, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> BehaviourRecordRead:
    student = await db.scalar(
        select(Student).where(Student.id == req.student_id, Student.school_id == school_id)
    )
    if not student:
        raise HTTPException(404, "Student not found.")
    term = await db.scalar(
        select(AcademicTerm).where(
            AcademicTerm.id == req.academic_term_id, AcademicTerm.school_id == school_id
        )
    )
    if not term:
        raise HTTPException(404, "Academic term not found.")
    if not (term.start_date <= req.incident_date <= term.end_date):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"incident_date {req.incident_date} falls outside the term ({term.start_date} – {term.end_date}).",
        )
    override_reason = _check_term_lock(term, req.override_reason)

    rec = StudentBehaviourRecord(
        school_id=school_id,
        student_id=req.student_id,
        academic_term_id=req.academic_term_id,
        incident_type=req.incident_type,
        description=req.description,
        severity=req.severity,
        action_taken=req.action_taken,
        incident_date=req.incident_date,
        recorded_by_id=user_id,
    )
    db.add(rec)
    await db.flush()
    db.add(BehaviourAuditLog(
        school_id=school_id, behaviour_record_id=rec.id, student_id=req.student_id,
        action="CREATE", incident_type=req.incident_type, incident_date=req.incident_date,
        changed_by_id=user_id, reason=override_reason, changed_at=datetime.now(timezone.utc),
    ))
    await db.flush()
    return _to_read(rec)


async def list_behaviour_records(
    student_id: uuid.UUID, term_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> list[BehaviourRecordRead]:
    student = await db.scalar(
        select(Student).where(Student.id == student_id, Student.school_id == school_id)
    )
    if not student:
        raise HTTPException(404, "Student not found.")
    rows = (await db.scalars(
        select(StudentBehaviourRecord)
        .where(
            StudentBehaviourRecord.student_id == student_id,
            StudentBehaviourRecord.academic_term_id == term_id,
            StudentBehaviourRecord.school_id == school_id,
        )
        .order_by(StudentBehaviourRecord.incident_date)
    )).all()
    return [_to_read(r) for r in rows]


async def delete_behaviour_record(
    record_id: uuid.UUID,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
    override_reason: str | None = None,
) -> None:
    rec = await db.scalar(
        select(StudentBehaviourRecord).where(
            StudentBehaviourRecord.id == record_id,
            StudentBehaviourRecord.school_id == school_id,
        )
    )
    if not rec:
        raise HTTPException(404, "Behaviour record not found.")
    term = await db.get(AcademicTerm, rec.academic_term_id)
    resolved_reason = _check_term_lock(term, override_reason) if term else None

    db.add(BehaviourAuditLog(
        school_id=school_id, behaviour_record_id=rec.id, student_id=rec.student_id,
        action="DELETE", incident_type=rec.incident_type, incident_date=rec.incident_date,
        changed_by_id=user_id, reason=resolved_reason, changed_at=datetime.now(timezone.utc),
    ))
    await db.delete(rec)
    await db.flush()
