"""
Lesson planner router — CRUD + AI-assist for a subject teacher's own weekly
lesson plans.

Permission map:
  lesson_plans.manage → create/update/delete (scoped to the caller's own
                         SubjectTeacher class+subject unless they hold
                         assessments.approve_scores)
  lesson_plans.view   → read-only (list/get) — same scope

No new picker endpoint — the frontend reuses GET /assessments/my-subjects
directly for the class+subject picker, since it's the identical data.
"""
from __future__ import annotations
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models.auth import User
from app.schemas.lesson_plans import (
    LessonPlanAiDraftRequest, LessonPlanAiDraftResponse,
    LessonPlanCreate, LessonPlanRead, LessonPlanUpdate,
)
from app.services import lesson_plans as lp_svc

router = APIRouter(prefix="/lesson-plans", tags=["lesson-plans"])


async def _staff_id_for(user_id: uuid.UUID, db: AsyncSession) -> uuid.UUID:
    user = await db.get(User, user_id)
    if not user or not user.staff_member_id:
        from fastapi import HTTPException
        raise HTTPException(403, "This action requires a staff account.")
    return user.staff_member_id


@router.post("", response_model=LessonPlanRead, status_code=201)
async def create_lesson_plan(
    req: LessonPlanCreate,
    ids=Depends(require_permission("lesson_plans", "manage")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    staff_id = await _staff_id_for(user_id, db)
    return await lp_svc.create_lesson_plan(req, school_id, user_id, staff_id, db)


@router.get("", response_model=list[LessonPlanRead])
async def list_lesson_plans(
    class_id: uuid.UUID = Query(...),
    subject_id: uuid.UUID = Query(...),
    academic_term_id: uuid.UUID = Query(...),
    week_start_date: date | None = Query(default=None),
    ids=Depends(require_permission("lesson_plans", "view")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await lp_svc.list_lesson_plans(
        class_id, subject_id, academic_term_id, school_id, user_id, db, week_start_date=week_start_date,
    )


@router.post("/ai-draft", response_model=LessonPlanAiDraftResponse)
async def ai_draft(
    req: LessonPlanAiDraftRequest,
    ids=Depends(require_permission("lesson_plans", "manage")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    draft_text = await lp_svc.draft_with_ai(
        req.class_id, req.subject_id, req.topic.strip(), school_id, user_id, db,
    )
    return LessonPlanAiDraftResponse(draft_text=draft_text)


@router.get("/{lesson_plan_id}", response_model=LessonPlanRead)
async def get_lesson_plan(
    lesson_plan_id: uuid.UUID,
    ids=Depends(require_permission("lesson_plans", "view")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    lp = await lp_svc.get_lesson_plan(lesson_plan_id, school_id, user_id, db)
    return LessonPlanRead.model_validate(lp)


@router.patch("/{lesson_plan_id}", response_model=LessonPlanRead)
async def update_lesson_plan(
    lesson_plan_id: uuid.UUID,
    req: LessonPlanUpdate,
    ids=Depends(require_permission("lesson_plans", "manage")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await lp_svc.update_lesson_plan(lesson_plan_id, req, school_id, user_id, db)


@router.delete("/{lesson_plan_id}", status_code=204)
async def delete_lesson_plan(
    lesson_plan_id: uuid.UUID,
    ids=Depends(require_permission("lesson_plans", "manage")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    await lp_svc.delete_lesson_plan(lesson_plan_id, school_id, user_id, db)
