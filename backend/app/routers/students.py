"""Students router — profiles, guardians, medical records, enrollment, transfers.

ACCESS CONTROL
--------------
GET  /students, /students/{id}                    students.view
POST /students                                    students.create
PATCH /students/{id}                              students.edit
PUT  /students/{id}/medical                       students.edit
POST/DELETE /students/{id}/guardians              students.edit
POST /students/{id}/enroll                        students.edit
POST /students/class-assignments                  students.edit
POST /students/class-assignments/bulk             students.edit
GET  /students/{id}/class-assignments             students.view
POST /students/term-enrollments                   students.edit
POST /students/term-enrollments/{id}/subjects     students.edit
POST /students/{id}/transfers                     students.edit
GET  /students/transfers/pending                  students.delete
PATCH /students/transfers/{id}/review             students.delete

ROUTE ORDER NOTE
----------------
Literal paths (/transfers/pending, /class-assignments, /term-enrollments) are
declared before the parametric /{student_id} to prevent path-capture by the UUID
parameter.
"""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.permissions import resolve_permissions
from fastapi import File, UploadFile
from fastapi.responses import StreamingResponse

from app.schemas.documents import ImportBatchResult
from app.schemas.students import (
    BulkEnrollResult, BulkGraduateRequest, BulkGraduateResult,
    BulkStudentClassAssignmentCreate, BulkTermEnrollmentCreate,
    EnrollmentCreate, EnrollmentRead,
    GraduationRecordRead,
    GuardianCreate, GuardianUpdate, StudentGuardianRead,
    MedicalRecordRead, MedicalRecordUpsert,
    PortalAccessResult,
    StudentClassAssignmentCreate, StudentClassAssignmentRead,
    StudentCreate, StudentDetail, StudentSummary, StudentUpdate,
    SubjectRegistrationItem, SubjectRegistrationRead,
    TermEnrollmentCreate, TermEnrollmentRead,
    TransferRequestCreate, TransferRequestRead, TransferRequestReview,
)
from app.services import graduation as graduation_svc
from app.services import student as svc
from app.services import student_class_assignment as class_svc
from app.services import student_enrollment as enroll_svc
from app.services import student_guardian as guardian_svc
from app.services import student_import as import_svc
from app.services import student_portal as portal_svc
from app.services import student_transfer as transfer_svc
from app.services.student_import_template import build_template

router = APIRouter(prefix="/students", tags=["students"])


# ── Collection endpoints ──────────────────────────────────────────────────────

@router.post("", response_model=StudentDetail, status_code=201)
async def create_student(
    req: StudentCreate,
    ids=Depends(require_permission("students", "create")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await svc.create_student(req, school_id, db)


@router.get("", response_model=list[StudentSummary])
async def list_students(
    active_only: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
    class_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    gender: str | None = Query(None),
    level: str | None = Query(None),
    year_group: int | None = Query(None),
    ids=Depends(require_permission("students", "view")),
    db: AsyncSession = Depends(get_db),
):
    from app.models.auth import User
    user_id, school_id = ids

    # Admins (students.edit) see everyone; view-only staff see only their own students.
    staff_member_id = None
    user = await db.get(User, user_id)
    if user and not user.is_superadmin and user.staff_member_id:
        perms = await resolve_permissions(user.staff_member_id, db)
        if not perms.get("students.edit", False):
            staff_member_id = user.staff_member_id

    return await svc.list_students(
        school_id, db,
        active_only=active_only, skip=skip, limit=limit,
        search=search, class_id=class_id, term_id=term_id,
        gender=gender, level=level, year_group=year_group,
        staff_member_id=staff_member_id,
    )


@router.get("/export")
async def export_students(
    active_only: bool = Query(True),
    class_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    gender: str | None = Query(None),
    level: str | None = Query(None),
    year_group: int | None = Query(None),
    search: str | None = Query(None),
    ids=Depends(require_permission("students", "view")),
    db: AsyncSession = Depends(get_db),
):
    from app.services.student_export import export_students_csv
    from fastapi.responses import StreamingResponse
    _, school_id = ids
    csv_bytes = await export_students_csv(
        school_id, db,
        active_only=active_only, class_id=class_id, term_id=term_id,
        gender=gender, level=level, year_group=year_group, search=search,
    )
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="students.csv"'},
    )


@router.get("/export/custom")
async def export_students_custom(
    fields: str = Query(""),
    fmt: str = Query("csv", pattern="^(csv|excel)$"),
    active_only: bool = Query(True),
    class_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    gender: str | None = Query(None),
    level: str | None = Query(None),
    year_group: int | None = Query(None),
    search: str | None = Query(None),
    ids=Depends(require_permission("students", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Export students with caller-selected fields as CSV or Excel."""
    from app.services.student_custom_export import export_students_custom as _export
    _, school_id = ids
    field_list = [f.strip() for f in fields.split(",") if f.strip()]
    data = await _export(
        school_id, db,
        fields=field_list, fmt=fmt,
        active_only=active_only, class_id=class_id, term_id=term_id,
        gender=gender, level=level, year_group=year_group, search=search,
    )
    if fmt == "excel":
        return StreamingResponse(
            iter([data]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="students.xlsx"'},
        )
    return StreamingResponse(
        iter([data]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="students.csv"'},
    )


# ── Bulk import (declared before /{student_id} to avoid path capture) ────────

@router.get("/import/template")
async def download_import_template(
    ids=Depends(require_permission("students", "create")),
    db: AsyncSession = Depends(get_db),
):
    """Return a branded .xlsx student import template for this school."""
    from app.models.school import School
    _, school_id = ids
    school = await db.get(School, school_id)
    xlsx_bytes = build_template(
        school_name=school.name if school else "School",
        school_code=school.school_code if school else "SCHOOL",
        brand_color=school.brand_color if school else "#1e40af",
    )
    filename = f"student_import_{school.school_code if school else 'template'}.xlsx"
    return StreamingResponse(
        iter([xlsx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", response_model=ImportBatchResult, status_code=200)
async def bulk_import_students(
    file: UploadFile = File(...),
    ids=Depends(require_permission("students", "create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a student import .xlsx (must be the official template).
    Best-effort: valid rows are created, failed rows are reported with reasons.
    """
    if not file.filename or not file.filename.endswith(".xlsx"):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Only .xlsx files are accepted.")
    user_id, school_id = ids
    from app.models.school import School
    school = await db.get(School, school_id)
    school_code = school.school_code if school else "SCHOOL"
    file_bytes = await file.read()
    return await import_svc.process_import(file_bytes, school_id, school_code, user_id, db)


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
    items: list[SubjectRegistrationItem],
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await enroll_svc.register_subjects(te_id, items, school_id, db)


@router.get("/term-enrollments/{te_id}/subjects", response_model=list[SubjectRegistrationRead])
async def list_subjects(
    te_id: uuid.UUID,
    ids=Depends(require_permission("students", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    return await enroll_svc.list_subject_registrations(te_id, school_id, db)


@router.delete("/term-enrollments/{te_id}/subjects/{reg_id}", status_code=204)
async def delete_subject(
    te_id: uuid.UUID,
    reg_id: uuid.UUID,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = ids
    await enroll_svc.delete_subject_registration(te_id, reg_id, school_id, db)


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


# ── Year-end graduation (must be before /{student_id} to avoid UUID capture) ─

@router.get("/graduation", response_model=list[GraduationRecordRead])
async def list_graduation_records(
    academic_year_id: uuid.UUID | None = Query(None),
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    """List graduation records, optionally filtered by academic year."""
    _, school_id = ids
    return await graduation_svc.list_graduation_records(school_id, db, academic_year_id=academic_year_id)


@router.post("/graduation/bulk", response_model=BulkGraduateResult, status_code=201)
async def bulk_graduate(
    req: BulkGraduateRequest,
    ids=Depends(require_permission("students", "edit")),
    db: AsyncSession = Depends(get_db),
):
    """Process year-end outcomes for a batch of students."""
    user_id, school_id = ids
    return await graduation_svc.process_bulk_graduation(req, user_id, school_id, db)


# ── Single-student endpoints ──────────────────────────────────────────────────

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
