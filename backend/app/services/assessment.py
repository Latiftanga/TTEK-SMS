"""
Assessment CRUD. AssessmentType (category) CRUD lives in
services/assessment_type.py — that stays the administrator's job; creating
the assessment itself (the actual assignment/test) is the subject teacher's,
scoped by _check_assessment_scope()/resolve_assessment_scope() to their own
SubjectTeacher class+subject, unless the caller holds
assessments.approve_scores (senior staff, unrestricted).

Assessment.is_published gates report card access (parent portal checks this).
Publishing itself — including the guardian notification fan-out — lives in
services/assessment_publish.py, split out to stay under the 300-line cap.

create_assessment requires subject_id to already be an active ClassSubject on
class_id (services/subject_roster.py) — an assessment can't be created for a
subject the class was never assigned, which is also what stops
subject_roster.py from silently treating every class member as eligible for
a subject that doesn't belong to their curriculum at all.

Every field edit in update_assessment (description/max_score/due_date) is
written to AssessmentAuditLog with an old/new value snapshot, mirroring
ScoreAuditLog and BehaviourAuditLog. recorded_date is never editable, so
never appears in that log. reason is only populated when the edit overrode a
locked term (see core/permissions.py::check_term_lock_override).
create_assessment enforces the same term lock (a locked term shouldn't grow
new assessments any more than it should let existing ones be edited) and logs
an AssessmentAuditLog entry when the caller had to override it.
"""
from __future__ import annotations
import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import check_term_lock_override
from app.core.teacher_scope import (
    enforce_current_term_for_scoring, resolve_assessment_scope, year_for_term,
)
from app.models.academic import AcademicTerm
from app.models.assessments import Assessment, AssessmentAuditLog, AssessmentType, Score
from app.schemas.assessments import AssessmentCreate, AssessmentRead, AssessmentUpdate
from app.services.academic_class import get_active_class
from app.services.subject_roster import class_subject_exists


# ── Assessment ────────────────────────────────────────────────────────────────

def _assessment_read(a: Assessment) -> AssessmentRead:
    return AssessmentRead.model_validate(a)


async def _check_assessment_scope(a: Assessment, user_id: uuid.UUID, db: AsyncSession) -> None:
    """Shared by get/update/delete — an assessment is only visible/editable
    to the subject teacher who owns its (class, subject) pair, unless the
    caller holds assessments.approve_scores."""
    year_id = await year_for_term(a.academic_term_id, db)
    if year_id is None:
        return
    scope = await resolve_assessment_scope(user_id, year_id, db)
    if scope is not None and (a.class_id, a.subject_id) not in scope:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment not found.")


async def create_assessment(
    req: AssessmentCreate, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> AssessmentRead:
    atype = await db.scalar(
        select(AssessmentType).where(
            AssessmentType.id == req.assessment_type_id,
            AssessmentType.school_id == school_id,
        )
    )
    if not atype:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment type not found.")
    if not atype.is_active:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{atype.name} is deactivated and can't be used for new assessments.",
        )
    term = await db.scalar(
        select(AcademicTerm).where(
            AcademicTerm.id == req.academic_term_id, AcademicTerm.school_id == school_id,
        )
    )
    if not term:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Academic term not found.")

    await get_active_class(req.class_id, school_id, db)

    # Creating an assessment is the subject teacher's own job, not the
    # administrator's — scoped the same way submit_scores/list_assessments
    # already are (unrestricted for an assessments.approve_scores holder).
    scope = await resolve_assessment_scope(user_id, term.academic_year_id, db)
    if scope is not None and (req.class_id, req.subject_id) not in scope:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "You are not assigned to teach this subject in this class.",
        )
    await enforce_current_term_for_scoring(user_id, req.academic_term_id, db)
    override_reason = await check_term_lock_override(req.academic_term_id, req.override_reason, user_id, db)

    if not await class_subject_exists(req.class_id, req.subject_id, school_id, db):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "This subject is not assigned to the selected class.",
        )
    if req.due_date and not (term.start_date <= req.due_date <= term.end_date):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"due_date {req.due_date} falls outside the term ({term.start_date} – {term.end_date}).",
        )
    # allow_multiple_entries=False means exactly one Assessment row of this
    # type may ever exist for this class+subject+term — keeps
    # resolve_type_score()'s NONE-strategy invariant ("exactly one recorded
    # entry") true by construction rather than just by convention, so it can
    # never raise at report-card time (services/aggregation.py).
    if not atype.allow_multiple_entries:
        existing_single = await db.scalar(
            select(Assessment).where(
                Assessment.school_id == school_id,
                Assessment.class_id == req.class_id,
                Assessment.subject_id == req.subject_id,
                Assessment.academic_term_id == req.academic_term_id,
                Assessment.assessment_type_id == req.assessment_type_id,
            )
        )
        if existing_single:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{atype.name} only allows one assessment per term for this subject "
                "(allow_multiple_entries is off).",
            )

    recorded_date = date.today()
    duplicate = await db.scalar(
        select(Assessment).where(
            Assessment.school_id == school_id,
            Assessment.class_id == req.class_id,
            Assessment.subject_id == req.subject_id,
            Assessment.academic_term_id == req.academic_term_id,
            Assessment.assessment_type_id == req.assessment_type_id,
            Assessment.recorded_date == recorded_date,
        )
    )
    if duplicate:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"A {atype.name} has already been recorded today for this subject.",
        )
    a = Assessment(
        school_id=school_id,
        class_id=req.class_id,
        subject_id=req.subject_id,
        assessment_type_id=req.assessment_type_id,
        academic_term_id=req.academic_term_id,
        description=(req.description.strip() if req.description else None),
        recorded_date=recorded_date,
        max_score=req.max_score,
        due_date=req.due_date,
    )
    db.add(a)
    await db.flush()
    if override_reason:
        db.add(AssessmentAuditLog(
            school_id=school_id, assessment_id=a.id, changed_by_id=user_id,
            old_values={}, new_values={"created": "true"}, reason=override_reason,
            changed_at=datetime.now(timezone.utc),
        ))
        await db.flush()
    return _assessment_read(a)


async def list_assessments(
    class_id: uuid.UUID, term_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> list[AssessmentRead]:
    rows = list(await db.scalars(
        select(Assessment).where(
            Assessment.class_id == class_id,
            Assessment.academic_term_id == term_id,
            Assessment.school_id == school_id,
        ).order_by(Assessment.recorded_date, Assessment.due_date)
    ))

    year_id = await year_for_term(term_id, db)
    if year_id is not None:
        scope = await resolve_assessment_scope(user_id, year_id, db)
        if scope is not None:
            # Not all-or-nothing: a SubjectTeacher may only teach 1 of several
            # subjects in this class — filter to just those, don't 404 the
            # whole class unless the caller has zero pairs here at all.
            taught_subject_ids = {sid for cid, sid in scope if cid == class_id}
            if not taught_subject_ids:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Class not found.")
            rows = [a for a in rows if a.subject_id in taught_subject_ids]

    return [_assessment_read(a) for a in rows]


async def get_assessment(
    assessment_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> AssessmentRead:
    a = await db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.school_id == school_id
        )
    )
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment not found.")

    await _check_assessment_scope(a, user_id, db)

    return _assessment_read(a)


async def update_assessment(
    assessment_id: uuid.UUID, req: AssessmentUpdate, school_id: uuid.UUID,
    user_id: uuid.UUID, db: AsyncSession
) -> AssessmentRead:
    a = await db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.school_id == school_id
        )
    )
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment not found.")
    await _check_assessment_scope(a, user_id, db)
    if a.is_published:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Cannot edit a published assessment.")
    override_reason = await check_term_lock_override(a.academic_term_id, req.override_reason, user_id, db)
    if req.due_date is not None:
        term = await db.get(AcademicTerm, a.academic_term_id)
        if term and not (term.start_date <= req.due_date <= term.end_date):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"due_date {req.due_date} falls outside the term ({term.start_date} – {term.end_date}).",
            )
    if req.max_score is not None:
        max_entered = await db.scalar(
            select(func.max(Score.raw_score)).where(Score.assessment_id == assessment_id)
        )
        if max_entered is not None and max_entered > req.max_score:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Cannot reduce max score: existing score of {max_entered} would exceed it.",
            )
    old_values: dict[str, str | None] = {}
    new_values: dict[str, str | None] = {}
    for field, value in (("description", req.description), ("max_score", req.max_score), ("due_date", req.due_date)):
        if value is None:
            continue
        old_values[field] = str(getattr(a, field)) if getattr(a, field) is not None else None
        new_values[field] = str(value)
        setattr(a, field, value)

    if new_values:
        db.add(AssessmentAuditLog(
            school_id=school_id, assessment_id=a.id, changed_by_id=user_id,
            old_values=old_values, new_values=new_values, reason=override_reason,
            changed_at=datetime.now(timezone.utc),
        ))
    await db.flush()
    return _assessment_read(a)


async def delete_assessment(
    assessment_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> None:
    a = await db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.school_id == school_id
        )
    )
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment not found.")
    await _check_assessment_scope(a, user_id, db)
    if a.is_published:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Cannot delete a published assessment.")
    term = await db.get(AcademicTerm, a.academic_term_id)
    if term and term.results_locked:
        raise HTTPException(
            status.HTTP_423_LOCKED,
            "This term's results are locked. Unlock the term before deleting an assessment "
            "— deleting one permanently removes its scores.",
        )
    await db.delete(a)
    await db.flush()
