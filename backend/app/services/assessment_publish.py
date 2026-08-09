"""
Assessment publishing — single, bulk, and unpublish. Split out of
services/assessment.py to stay under the 300-line cap.

Publishing stays assessments.approve_scores-gated (routers/assessments.py),
unlike create/update/delete: it's a guardian-facing, notification-firing
finalization step, not "creating an assignment".

unpublish_assessment() reverses a mistaken publish — reopens the assessment
for edits and, unless another assessment for the same class+term is still
published, hides the report from the parent portal again (is_report_published()
is a live query, not a cached flag, so this falls out for free — no extra
bookkeeping needed). It cannot recall a notification already sent; that's
real and unavoidable, not something the endpoint pretends to fix. Always
requires a reason (AssessmentUnpublishRequest), recorded in
AssessmentAuditLog — reversing a publish is itself worth an audit trail
regardless of whether the term happens to be locked.

Guardian notifications fire only on the FIRST assessment published for a
(class, term) — matching services/portal.py::is_report_published(), which
already unlocks the whole report the moment any one assessment is published
and stays unlocked regardless of how many more are published after. Without
this guard, a class with (typically) dozens of assessments across a term
would re-send the identical "report is ready" SMS/email to every guardian on
every subsequent publish — real SMS cost, and confusing/spammy either way.

The actual send loop lives in services/report_notify_job.py, run on the ARQ
background worker rather than inline — it's O(class size) sequential SMS
gateway/SMTP calls, which would otherwise block the publish request itself
for however long that takes. Enqueueing is best-effort (see _enqueue_notify)
so a Redis hiccup can never fail the publish that already succeeded in the DB.

Both single and bulk publish reject an assessment that still has an
unapproved score (422) rather than publishing it — bulk reports this as a
per-item skip (see bulk_publish_assessments' docstring below); single raises
directly, matching the "Cannot X a published assessment" convention already
used by update_assessment/delete_assessment/submit_scores/approve_scores for
every other is_published-gated action in this codebase.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_arq
from app.models.academic import AcademicTerm, Class
from app.models.assessments import Assessment, AssessmentAuditLog, Score
from app.schemas.assessments import AssessmentRead, BulkPublishResult


async def _class_term_already_unlocked(
    class_id: uuid.UUID, academic_term_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession,
    exclude_assessment_id: uuid.UUID | None = None,
) -> bool:
    """Whether some OTHER assessment for this class+term is already
    published — is_report_published() unlocks on the first one and stays
    unlocked, so a caller only needs to notify guardians once per class+term
    regardless of how many assessments get published after."""
    where = [
        Assessment.class_id == class_id,
        Assessment.academic_term_id == academic_term_id,
        Assessment.school_id == school_id,
        Assessment.is_published.is_(True),
    ]
    if exclude_assessment_id is not None:
        where.append(Assessment.id != exclude_assessment_id)
    return await db.scalar(select(Assessment.id).where(*where)) is not None


async def _enqueue_notify(
    class_id: uuid.UUID, academic_term_id: uuid.UUID, school_id: uuid.UUID, entity_id: uuid.UUID,
) -> None:
    """Best-effort — a Redis hiccup must never fail the publish itself,
    matching the same fire-and-forget guarantee the notify_* functions
    already document for an individual SMS/email send."""
    try:
        arq = await get_arq()
        try:
            await arq.enqueue_job(
                "notify_class_report_published",
                class_id=str(class_id),
                academic_term_id=str(academic_term_id),
                school_id=str(school_id),
                entity_id=str(entity_id),
            )
        finally:
            await arq.aclose()
    except Exception:
        pass


async def publish_assessment(
    assessment_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> AssessmentRead:
    a = await db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.school_id == school_id
        )
    )
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment not found.")
    if a.is_published:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Cannot publish a published assessment.")

    has_unapproved = await db.scalar(
        select(Score.id).where(Score.assessment_id == a.id, Score.is_approved.is_(False))
    ) is not None
    if has_unapproved:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Cannot publish — this assessment has unapproved scores. Approve them first.",
        )

    a.is_published = True
    await db.flush()

    already_unlocked = await _class_term_already_unlocked(
        a.class_id, a.academic_term_id, school_id, db, exclude_assessment_id=a.id
    )
    if not already_unlocked:
        await _enqueue_notify(a.class_id, a.academic_term_id, school_id, a.id)

    return AssessmentRead.model_validate(a)


async def unpublish_assessment(
    assessment_id: uuid.UUID, reason: str, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession,
) -> AssessmentRead:
    """Reverses a mistaken publish. See module docstring for what this does
    and does not undo."""
    a = await db.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.school_id == school_id
        )
    )
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment not found.")
    if not a.is_published:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Assessment is not published.")

    a.is_published = False
    db.add(AssessmentAuditLog(
        school_id=school_id, assessment_id=a.id, changed_by_id=user_id,
        old_values={"is_published": "True"}, new_values={"is_published": "False"},
        reason=reason, changed_at=datetime.now(timezone.utc),
    ))
    await db.flush()
    return AssessmentRead.model_validate(a)


async def bulk_publish_assessments(
    class_id: uuid.UUID, academic_term_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession,
) -> BulkPublishResult:
    """Publish every approved, not-yet-published assessment for a class+term.
    Unlike publish_assessment(), an assessment with an unapproved score is
    skipped (counted in skipped_unapproved) rather than failing the whole
    batch — a single deliberate publish click should reject loudly, but one
    bad item in a school-wide sweep shouldn't block every other assessment
    that's actually ready."""
    cls = await db.get(Class, class_id)
    if not cls or cls.school_id != school_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Class not found.")
    term = await db.get(AcademicTerm, academic_term_id)
    if not term or term.school_id != school_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Academic term not found.")

    # Checked once, before any write — publishing the whole batch can only
    # ever unlock the class+term one time, no matter how many assessments
    # in it are newly published below.
    already_unlocked = await _class_term_already_unlocked(class_id, academic_term_id, school_id, db)

    already_published = await db.scalar(
        select(func.count(Assessment.id)).where(
            Assessment.class_id == class_id,
            Assessment.academic_term_id == academic_term_id,
            Assessment.school_id == school_id,
            Assessment.is_published.is_(True),
        )
    ) or 0

    candidates = list(await db.scalars(
        select(Assessment).where(
            Assessment.class_id == class_id,
            Assessment.academic_term_id == academic_term_id,
            Assessment.school_id == school_id,
            Assessment.is_published.is_(False),
        )
    ))

    unapproved_assessment_ids: set[uuid.UUID] = set()
    if candidates:
        unapproved_assessment_ids = set(await db.scalars(
            select(Score.assessment_id).where(
                Score.assessment_id.in_([a.id for a in candidates]),
                Score.is_approved.is_(False),
            ).distinct()
        ))

    published = 0
    skipped_unapproved = 0
    newly_published_id: uuid.UUID | None = None
    for a in candidates:
        if a.id in unapproved_assessment_ids:
            skipped_unapproved += 1
            continue
        a.is_published = True
        published += 1
        if newly_published_id is None:
            newly_published_id = a.id

    await db.flush()

    if published and not already_unlocked:
        await _enqueue_notify(class_id, academic_term_id, school_id, newly_published_id)

    return BulkPublishResult(
        published=published, skipped_unapproved=skipped_unapproved, already_published=already_published,
    )
