"""Single-student endpoints — /{student_id}/... — mounted at the same
/students prefix as students.py.

MUST be registered (main.py) AFTER every sibling students_*.py router.
FastAPI/Starlette matches routes in registration order; a literal path like
/students/export has the same single-segment shape as /students/{student_id},
so if this router's GET /{student_id} were registered first it would swallow
requests meant for those literal routes. See students.py's module docstring
for the full file split.

ACCESS CONTROL
--------------
GET  /students/{id}                          students.view
PATCH /students/{id}                         students.edit
PUT  /students/{id}/medical                  students.edit
POST/DELETE /students/{id}/guardians          students.edit
POST/DELETE /students/{id}/guardians/{gid}/grant-portal-access|revoke-portal-access
                                               students.edit
POST /students/{id}/enroll                    students.edit
GET  /students/{id}/class-assignments         students.view
GET  /students/{id}/term-enrollments          students.view
POST/GET /students/{id}/transfers             students.edit / students.view
POST /students/{id}/grant-portal-access       students.edit
DELETE /students/{id}/revoke-portal-access    students.edit
POST/DELETE /students/{id}/photo              students.edit
"""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.students import (
    EnrollmentCreate, EnrollmentRead,
    GuardianCreate, GuardianPortalAccessResult, GuardianUpdate, StudentGuardianRead,
    MedicalRecordRead, MedicalRecordUpsert,
    PortalAccessResult,
    StudentClassAssignmentRead,
    StudentDetail, StudentUpdate,
    TermEnrollmentRead,
    TransferRequestCreate, TransferRequestRead,
)
from app.services import guardian_portal as guardian_portal_svc
from app.services import student as svc
from app.services import student_class_assignment as class_svc
from app.services import student_enrollment as enroll_svc
from app.services import student_guardian as guardian_svc
from app.services import student_portal as portal_svc
from app.services import student_transfer as transfer_svc

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/{student_id}", response_model=StudentDetail)
async def get_student(
    student_id: uuid.UUID,
    ids=Depends(require_permission("students", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await svc.get_student(student_id, school_id, db)


@router.patch("/{student_id}", response_model=StudentDetail)
async def update_student(
    student_id: uuid.UUID,
    req: StudentUpdate,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await svc.update_student(student_id, req, school_id, db)


@router.put("/{student_id}/medical", response_model=MedicalRecordRead)
async def upsert_medical_record(
    student_id: uuid.UUID,
    req: MedicalRecordUpsert,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await svc.upsert_medical_record(student_id, req, school_id, db)


@router.post("/{student_id}/guardians", response_model=StudentGuardianRead, status_code=201)
async def add_guardian(
    student_id: uuid.UUID,
    req: GuardianCreate,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await guardian_svc.add_guardian(student_id, req, school_id, db)


@router.patch("/{student_id}/guardians/{guardian_id}", response_model=StudentGuardianRead)
async def update_guardian(
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    req: GuardianUpdate,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await guardian_svc.update_guardian(student_id, guardian_id, req, school_id, db)


@router.delete("/{student_id}/guardians/{guardian_id}", status_code=204)
async def remove_guardian(
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    await guardian_svc.remove_guardian(student_id, guardian_id, school_id, db)


@router.post(
    "/{student_id}/guardians/{guardian_id}/grant-portal-access",
    response_model=GuardianPortalAccessResult, status_code=201,
)
async def grant_guardian_portal_access(
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await guardian_portal_svc.grant_portal_access(guardian_id, school_id, db)


@router.delete("/{student_id}/guardians/{guardian_id}/revoke-portal-access", status_code=204)
async def revoke_guardian_portal_access(
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    await guardian_portal_svc.revoke_portal_access(guardian_id, school_id, db)


@router.post("/{student_id}/enroll", response_model=EnrollmentRead, status_code=201)
async def create_enrollment(
    student_id: uuid.UUID,
    req: EnrollmentCreate,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await enroll_svc.create_enrollment(student_id, req, school_id, db)


@router.get("/{student_id}/class-assignments", response_model=list[StudentClassAssignmentRead])
async def list_class_assignments(
    student_id: uuid.UUID,
    ids=Depends(require_permission("students", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await class_svc.list_class_assignments(student_id, school_id, db)


@router.get("/{student_id}/term-enrollments", response_model=list[TermEnrollmentRead])
async def list_term_enrollments(
    student_id: uuid.UUID,
    ids=Depends(require_permission("students", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await enroll_svc.list_term_enrollments(student_id, school_id, db)


@router.post("/{student_id}/transfers", response_model=TransferRequestRead, status_code=201)
async def create_transfer_request(
    student_id: uuid.UUID,
    req: TransferRequestCreate,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await transfer_svc.create_transfer_request(student_id, req, school_id, db)


@router.get("/{student_id}/transfers", response_model=list[TransferRequestRead])
async def list_transfers_for_student(
    student_id: uuid.UUID,
    ids=Depends(require_permission("students", "view")),
    db: AsyncSession = Depends(get_db),
):
    """A student's own transfer request history/status — visible to anyone who can
    view the student, independent of the higher `students.delete` bar required to
    review the school-wide pending queue (see students_enrollment.py's /transfers/pending)."""
    _, school_id = ids
    return await transfer_svc.list_transfers_for_student(student_id, school_id, db)


@router.post("/{student_id}/grant-portal-access", response_model=PortalAccessResult, status_code=201)
async def grant_portal_access(
    student_id: uuid.UUID,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await portal_svc.grant_portal_access(student_id, school_id, db)


@router.delete("/{student_id}/revoke-portal-access", status_code=204)
async def revoke_portal_access(
    student_id: uuid.UUID,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    await portal_svc.revoke_portal_access(student_id, school_id, db)


@router.post("/{student_id}/photo", response_model=StudentDetail)
async def upload_photo(
    student_id: uuid.UUID,
    file: UploadFile = File(...),
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await svc.upload_student_photo(student_id, file, school_id, db)


@router.delete("/{student_id}/photo", status_code=204)
async def delete_photo(
    student_id: uuid.UUID,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    await svc.remove_student_photo(student_id, school_id, db)
