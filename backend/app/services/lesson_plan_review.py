"""
Lesson plan review/approval workflow — split out of services/
lesson_plan_generation.py to stay under the 300-line cap. See
models/lesson_plans.py's own module docstring for the approval-workflow
design (lesson_plans.approve permission, unrestricted school-wide).
"""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.teacher_scope import year_for_term
from app.models.lesson_plans import LessonPlan, LessonPlanStatus
from app.schemas.lesson_plans import LessonPlanRead, LessonPlanReviewRequest
from app.services.lesson_plan_occurrences import resolve_week_occurrences
from app.services.lesson_plan_prompt import get_content
from app.services.lesson_plans import _to_read


async def review_lesson_plan(
    lesson_plan_id: uuid.UUID, req: LessonPlanReviewRequest,
    school_id: uuid.UUID, reviewer_staff_id: uuid.UUID, db: AsyncSession,
) -> LessonPlanRead:
    """No _check_scope call, deliberately: the router already gated this on
    the narrow lesson_plans.approve permission, which is itself the
    authorization to act on ANY plan school-wide — re-applying the
    plan-owner's own SubjectTeacher scope on top would defeat the point of
    granting review rights to someone who isn't also that class's subject
    teacher."""
    lp = await db.scalar(select(LessonPlan).where(LessonPlan.id == lesson_plan_id, LessonPlan.school_id == school_id))
    if not lp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lesson plan not found.")

    if req.status == LessonPlanStatus.APPROVED and lp.generated_content:
        content = get_content(lp)
        # A teacher-declared (no-timetable) plan has no real calendar/period
        # identity to diff against at all — nothing to detect drift in.
        if content.lessons and content.lessons[0].school_calendar_id is not None:
            year_id = await year_for_term(lp.academic_term_id, db)
            fresh = await resolve_week_occurrences(
                lp.class_id, lp.subject_id, year_id, lp.week_start_date,
                lp.week_start_date + timedelta(days=6), school_id, db,
            ) if year_id else []
            fresh_ids = {(o.school_calendar_id, o.period_id) for o in fresh}
            stored_ids = {(l.school_calendar_id, l.period_id) for l in content.lessons}
            if fresh_ids != stored_ids:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "The scheduled occurrences for this plan have changed since it was "
                    "generated (timetable or calendar changed) — regenerate lessons before approving.",
                )

    lp.status = req.status
    lp.reviewed_by_staff_id = reviewer_staff_id
    lp.review_notes = req.review_notes
    lp.reviewed_at = datetime.now(timezone.utc)
    await db.flush()
    return _to_read(lp)
