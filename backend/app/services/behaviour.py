"""
Student behaviour record CRUD.

SCOPING
-------
Recording behaviour is a Class Teacher duty (per the staff-roles spec), gated
on the narrow assessments.record_behaviour permission and scoped to the
caller's own ClassTeacher assignment via the shared
core/teacher_scope.py::resolve_report_card_scope() resolver — identical
"class_ids I'm ClassTeacher of this year, bypassed for assessments.
approve_scores holders" semantics report cards already use, reused rather
than duplicated. A caller with zero ClassTeacher assignments gets 404 on
every scoped call, never a silent fallback. list_behaviour_records is scoped
the same way (assessments.view holders otherwise see every student's
behaviour school-wide, the same gap closed for Students last session).

TERM LOCK
---------
Like scoring, AcademicTerm.results_locked freezes behaviour record create/
delete for that term. Both endpoints require assessments.record_behaviour
(see routers/report_cards.py) as the base action; overriding a locked term
still needs the caller to separately hold assessments.approve_scores, same
as scoring/subject-registration.

Every create/delete is written to BehaviourAuditLog, independent of whether
the term was locked (reason is only populated on a locked-term override).
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import check_term_lock_override, user_has_permission
from app.core.student_scope import current_class_assignment
from app.core.teacher_scope import resolve_report_card_scope
from app.models.academic import AcademicTerm
from app.models.assessments import BehaviourAuditLog, StudentBehaviourRecord
from app.models.students import Student
from app.schemas.behaviour import BehaviourRecordCreate, BehaviourRecordRead


def _to_read(r: StudentBehaviourRecord) -> BehaviourRecordRead:
    return BehaviourRecordRead.model_validate(r)


async def _assert_in_scope(user_id: uuid.UUID, student_id: uuid.UUID, db: AsyncSession) -> None:
    if await user_has_permission(user_id, "assessments", "approve_scores", db):
        return
    assignment = await current_class_assignment(student_id, db)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found.")
    class_id, academic_year_id = assignment
    scope = await resolve_report_card_scope(user_id, academic_year_id, db)
    if scope is not None and class_id not in scope:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found.")


async def create_behaviour_record(
    req: BehaviourRecordCreate, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> BehaviourRecordRead:
    student = await db.scalar(
        select(Student).where(Student.id == req.student_id, Student.school_id == school_id)
    )
    if not student:
        raise HTTPException(404, "Student not found.")
    await _assert_in_scope(user_id, req.student_id, db)
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
    override_reason = await check_term_lock_override(term.id, req.override_reason, user_id, db)

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
    student_id: uuid.UUID, term_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> list[BehaviourRecordRead]:
    student = await db.scalar(
        select(Student).where(Student.id == student_id, Student.school_id == school_id)
    )
    if not student:
        raise HTTPException(404, "Student not found.")
    await _assert_in_scope(user_id, student_id, db)
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
    await _assert_in_scope(user_id, rec.student_id, db)
    resolved_reason = await check_term_lock_override(rec.academic_term_id, override_reason, user_id, db)

    db.add(BehaviourAuditLog(
        school_id=school_id, behaviour_record_id=rec.id, student_id=rec.student_id,
        action="DELETE", incident_type=rec.incident_type, incident_date=rec.incident_date,
        changed_by_id=user_id, reason=resolved_reason, changed_at=datetime.now(timezone.utc),
    ))
    await db.delete(rec)
    await db.flush()
