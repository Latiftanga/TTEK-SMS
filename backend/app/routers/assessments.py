"""
Assessments router — the assessment CRUD + publish/unpublish itself.
Grading scales (routers/grading.py), assessment types (routers/
assessment_types.py), and scores (routers/scoring.py) were split out to stay
under the 300-line cap — all four share the /assessments prefix and are
registered together in main.py.

Permission map:
  assessments.approve_scores → grading scale management, assessment type
                               (category) CRUD, assessment publish, score
                               approval — the administrator's/senior staff's
                               job, never the class-level detail.
  assessments.enter_scores   → assessment create/update/delete (scoped to the
                               caller's own SubjectTeacher class+subject) and
                               submit scores — the subject teacher's own job.
  assessments.view           → read-only access to everything

ROUTE ORDERING — main.py must register routers/grading.py and routers/
assessment_types.py (both literal path segments like /grading-scales,
/types) before this router, since /{assessment_id} is a typed UUID path
param but this codebase's convention (matching students_detail.py) treats
literal-vs-dynamic route ordering as load-bearing regardless. Within this
file, /my-subjects is registered before /{assessment_id} for the same
reason — a literal segment would otherwise be swallowed by the UUID path
param.
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.assessments import (
    AssessmentCreate, AssessmentRead, AssessmentRosterStudent, AssessmentUnpublishRequest, AssessmentUpdate,
    BulkPublishRequest, BulkPublishResult, MySubjectAssignment,
)
from app.services import assessment as assess_svc
from app.services import assessment_publish as publish_svc
from app.services.subject_roster import list_assessment_roster
from app.services.subject_roster import list_my_subjects as list_my_subjects_svc

router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.post("", response_model=AssessmentRead, status_code=201)
async def create_assessment(
    req: AssessmentCreate,
    ids=Depends(require_permission("assessments", "enter_scores")),
    db: AsyncSession = Depends(get_db),
):
    """Creating an assessment is the subject teacher's own job — scoped to
    their SubjectTeacher assignment(s) (services/assessment.py), not gated
    on assessments.approve_scores. Admins only manage assessment *types*
    (categories) and grading scales, see routers/grading.py and
    routers/assessment_types.py."""
    user_id, school_id = ids
    return await assess_svc.create_assessment(req, school_id, user_id, db)


@router.get("", response_model=list[AssessmentRead])
async def list_assessments(
    class_id: uuid.UUID = Query(...),
    term_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await assess_svc.list_assessments(class_id, term_id, school_id, user_id, db)


# Registered before /{assessment_id} — a literal path segment would otherwise
# be swallowed by the UUID path param and fail assessment_id parsing.
@router.get("/my-subjects", response_model=list[MySubjectAssignment])
async def list_my_subjects(
    term_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    """(class, subject) combos the caller can create assessments/enter scores
    for — scoped to their own SubjectTeacher assignment(s) unless they hold
    assessments.approve_scores."""
    user_id, school_id = ids
    return await list_my_subjects_svc(term_id, school_id, user_id, db)


@router.get("/{assessment_id}", response_model=AssessmentRead)
async def get_assessment(
    assessment_id: uuid.UUID,
    ids=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await assess_svc.get_assessment(assessment_id, school_id, user_id, db)


@router.get("/{assessment_id}/roster", response_model=list[AssessmentRosterStudent])
async def get_assessment_roster(
    assessment_id: uuid.UUID,
    ids=Depends(require_permission("assessments", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Students eligible to be scored for this assessment's subject — never
    "everyone in the class" once subject registration splits them (electives).
    See services/subject_roster.py."""
    user_id, school_id = ids
    assessment = await assess_svc.get_assessment(assessment_id, school_id, user_id, db)
    return await list_assessment_roster(
        assessment.class_id, assessment.subject_id, assessment.academic_term_id, school_id, db,
    )


@router.patch("/{assessment_id}", response_model=AssessmentRead)
async def update_assessment(
    assessment_id: uuid.UUID,
    req: AssessmentUpdate,
    ids=Depends(require_permission("assessments", "enter_scores")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await assess_svc.update_assessment(assessment_id, req, school_id, user_id, db)


@router.delete("/{assessment_id}", status_code=204)
async def delete_assessment(
    assessment_id: uuid.UUID,
    ids=Depends(require_permission("assessments", "enter_scores")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    await assess_svc.delete_assessment(assessment_id, school_id, user_id, db)


@router.post("/{assessment_id}/publish", response_model=AssessmentRead)
async def publish_assessment(
    assessment_id: uuid.UUID,
    ids=Depends(require_permission("assessments", "approve_scores")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await publish_svc.publish_assessment(assessment_id, school_id, db)


@router.post("/{assessment_id}/unpublish", response_model=AssessmentRead)
async def unpublish_assessment(
    assessment_id: uuid.UUID,
    req: AssessmentUnpublishRequest,
    ids=Depends(require_permission("assessments", "approve_scores")),
    db: AsyncSession = Depends(get_db),
):
    """Reverses a mistaken publish — reopens the assessment for edits and,
    unless another assessment for the same class+term is still published,
    hides the report from the parent portal again. Cannot recall a
    notification already sent. See services/assessment_publish.py."""
    user_id, school_id = ids
    return await publish_svc.unpublish_assessment(assessment_id, req.reason, school_id, user_id, db)


@router.post("/bulk-publish", response_model=BulkPublishResult)
async def bulk_publish_assessments(
    req: BulkPublishRequest,
    ids=Depends(require_permission("assessments", "approve_scores")),
    db: AsyncSession = Depends(get_db),
):
    """Publish every approved, not-yet-published assessment for a class+term
    in one action — skips any assessment that still has an unapproved score
    rather than publishing it. See services/assessment_publish.py."""
    _, school_id = ids
    return await publish_svc.bulk_publish_assessments(
        req.class_id, req.academic_term_id, school_id, db
    )
