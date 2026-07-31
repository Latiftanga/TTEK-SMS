"""Class assignments, term enrollments, subject registration, and transfer
review — literal-path endpoints, mounted at the same /students prefix as
students.py. See students.py's module docstring for the full file split.

ACCESS CONTROL
--------------
POST /students/class-assignments                  students.edit
POST /students/class-assignments/bulk              students.edit
POST /students/bulk-term-enrollments                students.edit
POST /students/term-enrollments                     students.edit
POST /students/term-enrollments/{id}/subjects        students.edit (+ assessments.approve_scores to override a locked term)
GET  /students/term-enrollments/{id}/subjects        students.view
DELETE /students/term-enrollments/{id}/subjects/{id} students.edit (+ assessments.approve_scores to override a locked term)
POST /students/classes/{id}/subjects/bulk-register-core students.edit (+ assessments.approve_scores to override a locked term)
GET  /students/classes/{id}/subjects/{id}/roster     students.view
POST /students/classes/{id}/subjects/{id}/roster     students.edit (+ assessments.approve_scores to override a locked term)
GET  /students/transfers/pending                    students.delete
PATCH /students/transfers/{id}/review                students.delete
"""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.students import (
    BulkEnrollResult, BulkRegisterCoreSubjectsRequest, BulkRegisterCoreSubjectsResult,
    BulkStudentClassAssignmentCreate, BulkTermEnrollmentCreate,
    SetSubjectRosterRequest, SetSubjectRosterResult,
    StudentClassAssignmentCreate, StudentClassAssignmentRead,
    SubjectRegistrationBulkCreate, SubjectRegistrationRead, SubjectRosterStudent,
    TermEnrollmentCreate, TermEnrollmentRead,
    TransferRequestRead, TransferRequestReview,
)
from app.services import class_subject_registration as class_subject_reg_svc
from app.services import student_class_assignment as class_svc
from app.services import student_enrollment as enroll_svc
from app.services import student_subject_registration as subject_reg_svc
from app.services import student_transfer as transfer_svc

router = APIRouter(prefix="/students", tags=["students"])


# ── Class assignment (declared before /{student_id} to avoid path capture) ───

@router.post("/class-assignments", response_model=StudentClassAssignmentRead, status_code=201)
async def create_class_assignment(
    req: StudentClassAssignmentCreate,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await class_svc.create_class_assignment(req, school_id, user_id, db)


@router.post("/class-assignments/bulk", response_model=BulkEnrollResult)
async def bulk_class_assignment(
    req: BulkStudentClassAssignmentCreate,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await class_svc.bulk_class_assignment(req.items, school_id, user_id, db)


# ── Term enrollment (declared before /{student_id} to avoid path capture) ────

@router.post("/bulk-term-enrollments", response_model=BulkEnrollResult)
async def bulk_term_enrollment(
    req: BulkTermEnrollmentCreate,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    result = await enroll_svc.bulk_term_enrollment(req.items, school_id, user_id, db)
    return result


@router.post("/term-enrollments", response_model=TermEnrollmentRead, status_code=201)
async def create_term_enrollment(
    req: TermEnrollmentCreate,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await enroll_svc.create_term_enrollment(req, school_id, user_id, db)


@router.post("/term-enrollments/{te_id}/subjects", response_model=list[SubjectRegistrationRead], status_code=201)
async def register_subjects(
    te_id: uuid.UUID,
    req: SubjectRegistrationBulkCreate,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await subject_reg_svc.register_subjects(
        te_id, req.items, school_id, user_id, db, override_reason=req.override_reason,
    )


@router.get("/term-enrollments/{te_id}/subjects", response_model=list[SubjectRegistrationRead])
async def list_subjects(
    te_id: uuid.UUID,
    ids=Depends(require_permission("students", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await subject_reg_svc.list_subject_registrations(te_id, school_id, db)


@router.delete("/term-enrollments/{te_id}/subjects/{reg_id}", status_code=204)
async def delete_subject(
    te_id: uuid.UUID,
    reg_id: uuid.UUID,
    override_reason: str | None = Query(None),
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    await subject_reg_svc.delete_subject_registration(te_id, reg_id, school_id, user_id, db, override_reason)


@router.post("/classes/{class_id}/subjects/bulk-register-core", response_model=BulkRegisterCoreSubjectsResult)
async def bulk_register_core_subjects(
    class_id: uuid.UUID,
    req: BulkRegisterCoreSubjectsRequest,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await class_subject_reg_svc.bulk_register_core_subjects(class_id, req, school_id, user_id, db)


@router.get("/classes/{class_id}/subjects/{subject_id}/roster", response_model=list[SubjectRosterStudent])
async def get_subject_roster(
    class_id: uuid.UUID,
    subject_id: uuid.UUID,
    academic_term_id: uuid.UUID = Query(...),
    ids=Depends(require_permission("students", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await class_subject_reg_svc.get_subject_roster(class_id, subject_id, academic_term_id, school_id, db)


@router.post("/classes/{class_id}/subjects/{subject_id}/roster", response_model=SetSubjectRosterResult)
async def set_subject_roster(
    class_id: uuid.UUID,
    subject_id: uuid.UUID,
    req: SetSubjectRosterRequest,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await class_subject_reg_svc.set_subject_roster(class_id, subject_id, req, school_id, user_id, db)


# ── Transfer management (declared before /{student_id}) ──────────────────────

@router.get("/transfers/pending", response_model=list[TransferRequestRead])
async def list_pending_transfers(
    ids=Depends(require_permission("students", "delete")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await transfer_svc.list_pending_transfers(school_id, db)


@router.patch("/transfers/{tr_id}/review", response_model=TransferRequestRead)
async def review_transfer(
    tr_id: uuid.UUID,
    req: TransferRequestReview,
    ids=Depends(require_permission("students", "delete")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    return await transfer_svc.review_transfer(tr_id, req, school_id, user_id, db)
