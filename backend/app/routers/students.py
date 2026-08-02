"""Students router — collection CRUD, list/export, bulk import.

Split across sibling files, all mounted at the same /students prefix:
  students.py             this file — collection + bulk import
  students_enrollment.py  class assignments, term enrollments, transfers
  students_lifecycle.py   year-end graduation/promotion
  students_detail.py      /{student_id}/... single-student endpoints (registered LAST)

ACCESS CONTROL
--------------
GET  /students                                    students.view
POST /students                                     students.create
GET  /students/export, /export/custom              students.view
GET  /students/import/template                     students.create
POST /students/import                              students.create

ROUTE ORDER NOTE
----------------
All literal-path routers must be registered (main.py) before students_detail's
/{student_id} — see students_detail.py for why.
"""
from __future__ import annotations
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.student_scope import resolve_student_view_scope
from app.schemas.documents import ImportBatchResult
from app.schemas.students import StudentCreate, StudentDetail, StudentSummary
from app.services import student as svc
from app.services import student_import as import_svc
from app.services import student_list as list_svc
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
    response: Response,
    active_only: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
    class_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    gender: str | None = Query(None),
    level: str | None = Query(None),
    year_group: int | None = Query(None),
    graduated: bool | None = Query(None),
    sort_by: Literal["name", "admission", "class"] = Query("name"),
    sort_dir: Literal["asc", "desc"] = Query("asc"),
    ids=Depends(require_permission("students", "view")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids

    # Staff whose only relevant permission is students.view (e.g. a subject teacher)
    # or students.edit (a class teacher editing their own students' records) see
    # only their own students — resolved via ClassTeacher/SubjectTeacher/HouseMaster
    # assignment (core/student_scope.py::resolve_student_view_scope). Staff with a
    # genuinely broader administrative permission — one that requires the full
    # roster to do their job (fee collection, housing assignment, score approval,
    # or students.delete) — are NOT scoped, since they legitimately need to find
    # students outside their own classes (e.g. a Bursar recording a payment, a
    # Housemaster assigning a new student to their house, an Exam Officer approving
    # another teacher's scores).
    scope = await resolve_student_view_scope(user_id, school_id, db)

    items, total = await list_svc.list_students(
        school_id, db,
        active_only=active_only, skip=skip, limit=limit,
        search=search, class_id=class_id, term_id=term_id,
        gender=gender, level=level, year_group=year_group,
        scope=scope, graduated=graduated,
        sort_by=sort_by, sort_dir=sort_dir,
    )
    response.headers["X-Total-Count"] = str(total)
    return items


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


# ── Bulk import (literal path, before /{student_id} — see students_detail.py) ─

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
