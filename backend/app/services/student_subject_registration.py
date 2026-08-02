"""
Subject registration — which subjects a student is taking against a given
TermEnrollment. Split out of student_enrollment.py (was over the 300-line
cap).

A student can only be registered for a subject actually offered to their
class (ClassSubject) — mirrors the same check on assessment creation
(services/subject_roster.py::class_subject_exists, added in 12q).

Class-wide, multi-student operations (bulk-register-core, per-subject
roster read/write) live in services/class_subject_registration.py, which
imports register_subjects/delete_subject_registration from here rather
than duplicating their insert/delete logic.

TERM LOCK
---------
Registering or removing a subject against a term that's already been
finalized (AcademicTerm.results_locked) doesn't make sense — the term's
report cards may already be generated, and a newly added subject would show
up with no scores. Gated by the same check_term_lock_override() used by
scoring/assessment edits; both routes here are gated at students.edit (a
weaker permission than assessments.approve_scores), so the override itself
still requires the caller to hold assessments.approve_scores, same shape as
submit_scores in scoring.py.

AUDIT LOG
---------
Every create/delete writes a SubjectRegistrationAuditLog row (mirroring
ScoreAuditLog/BehaviourAuditLog) — check_term_lock_override()'s return
value is captured and stored as `reason` (null unless it was actually a
locked-term override), not discarded.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import check_term_lock_override
from app.core.student_scope import resolve_class_teacher_scope, resolve_subject_teacher_scope
from app.core.teacher_scope import enforce_current_term_for_subject_registration
from app.models.academic import AcademicTerm, Subject
from app.models.students import (
    StudentClassAssignment,
    SubjectRegistration,
    SubjectRegistrationAuditLog,
    TermEnrollment,
)
from app.schemas.students import SubjectRegistrationItem, SubjectRegistrationRead
from app.services.subject_roster import class_subject_exists


async def _assert_can_register(
    class_id: uuid.UUID,
    subject_ids: list[uuid.UUID],
    academic_year_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Subject registration is Category B — a class teacher may manage the
    whole class's registrations, or a subject teacher may manage just their
    own (class, subject) pair. See core/student_scope.py."""
    class_scope = await resolve_class_teacher_scope(user_id, academic_year_id, db)
    if class_scope is None or class_id in class_scope:
        return
    subject_scope = await resolve_subject_teacher_scope(user_id, academic_year_id, db)
    if subject_scope is not None and any(
        (class_id, sid) not in subject_scope for sid in subject_ids
    ):
        raise HTTPException(status_code=404, detail="Term enrollment not found.")


async def register_subjects(
    te_id: uuid.UUID,
    items: list[SubjectRegistrationItem],
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
    override_reason: str | None = None,
) -> list[SubjectRegistrationRead]:
    te = await db.scalar(
        select(TermEnrollment).where(
            TermEnrollment.id == te_id, TermEnrollment.school_id == school_id,
            TermEnrollment.is_active.is_(True),
        )
    )
    if not te:
        raise HTTPException(status_code=404, detail="Term enrollment not found.")

    # Validate every item up front, before touching the DB.
    term = await db.get(AcademicTerm, te.academic_term_id)
    sca = await db.scalar(
        select(StudentClassAssignment).where(
            StudentClassAssignment.student_id == te.student_id,
            StudentClassAssignment.academic_year_id == term.academic_year_id,
            StudentClassAssignment.school_id == school_id,
            StudentClassAssignment.is_active.is_(True),
        )
    ) if term else None
    if not sca:
        raise HTTPException(
            status_code=422,
            detail="Student has no class assignment for this academic year — cannot register subjects.",
        )
    await _assert_can_register(
        sca.class_id, [item.subject_id for item in items], term.academic_year_id, user_id, db,
    )
    await enforce_current_term_for_subject_registration(user_id, term.id, db)
    resolved_reason = await check_term_lock_override(term.id, override_reason, user_id, db)
    for item in items:
        if not await class_subject_exists(sca.class_id, item.subject_id, school_id, db):
            subject = await db.get(Subject, item.subject_id)
            name = subject.name if subject else str(item.subject_id)
            raise HTTPException(
                status_code=422,
                detail=f"'{name}' is not assigned to this student's class.",
            )

    results: list[SubjectRegistration] = []
    for item in items:
        reg = SubjectRegistration(
            school_id=school_id,
            term_enrollment_id=te_id,
            subject_id=item.subject_id,
            registration_type=item.registration_type,
        )
        try:
            async with db.begin_nested():
                db.add(reg)
                await db.flush()
        except IntegrityError:
            try:
                db.expunge(reg)
            except Exception:
                pass  # already registered — skip silently, no audit entry for a no-op
            continue
        db.add(SubjectRegistrationAuditLog(
            school_id=school_id, registration_id=reg.id, term_enrollment_id=te_id,
            subject_id=item.subject_id, action="CREATE", registration_type=item.registration_type,
            changed_by_id=user_id, reason=resolved_reason, changed_at=datetime.now(timezone.utc),
        ))
        await db.flush()
        results.append(reg)

    return [SubjectRegistrationRead.model_validate(r) for r in results]


async def list_subject_registrations(
    te_id: uuid.UUID,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[SubjectRegistrationRead]:
    from app.core.student_scope import assert_can_view_student

    te = await db.scalar(
        select(TermEnrollment).where(
            TermEnrollment.id == te_id, TermEnrollment.school_id == school_id,
        )
    )
    if te:
        await assert_can_view_student(user_id, te.student_id, school_id, db)

    rows = await db.scalars(
        select(SubjectRegistration).where(
            SubjectRegistration.term_enrollment_id == te_id,
            SubjectRegistration.school_id == school_id,
        )
    )
    return [SubjectRegistrationRead.model_validate(r) for r in rows]


async def delete_subject_registration(
    te_id: uuid.UUID,
    reg_id: uuid.UUID,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
    override_reason: str | None = None,
) -> None:
    reg = await db.scalar(
        select(SubjectRegistration).where(
            SubjectRegistration.id == reg_id,
            SubjectRegistration.term_enrollment_id == te_id,
            SubjectRegistration.school_id == school_id,
        )
    )
    if not reg:
        raise HTTPException(status_code=404, detail="Subject registration not found.")
    te = await db.get(TermEnrollment, te_id)
    resolved_reason = None
    if te:
        term = await db.get(AcademicTerm, te.academic_term_id)
        sca = await db.scalar(
            select(StudentClassAssignment).where(
                StudentClassAssignment.student_id == te.student_id,
                StudentClassAssignment.academic_year_id == term.academic_year_id,
                StudentClassAssignment.school_id == school_id,
                StudentClassAssignment.is_active.is_(True),
            )
        ) if term else None
        if sca:
            await _assert_can_register(sca.class_id, [reg.subject_id], term.academic_year_id, user_id, db)
        else:
            # No active class assignment — a scoped caller has nothing to
            # match against, so deny rather than silently fall through.
            if await resolve_class_teacher_scope(user_id, term.academic_year_id, db) is not None:
                raise HTTPException(status_code=404, detail="Subject registration not found.")
        await enforce_current_term_for_subject_registration(user_id, te.academic_term_id, db)
        resolved_reason = await check_term_lock_override(te.academic_term_id, override_reason, user_id, db)
    db.add(SubjectRegistrationAuditLog(
        school_id=school_id, registration_id=reg.id, term_enrollment_id=te_id,
        subject_id=reg.subject_id, action="DELETE", registration_type=reg.registration_type,
        changed_by_id=user_id, reason=resolved_reason, changed_at=datetime.now(timezone.utc),
    ))
    await db.delete(reg)
    await db.flush()
