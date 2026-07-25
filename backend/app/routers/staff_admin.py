"""Staff register exports and personal permission overrides. Split out of
routers/staff.py to stay under the 300-line cap.

ACCESS CONTROL
--------------
GET  /staff/export/*                  staff.view
GET/POST/DELETE /staff/{id}/permissions  school.manage_users
"""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.auth import StaffPermissionRead, StaffPermissionUpsert
from app.services import staff_permissions as perms_svc

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("/export/excel")
async def export_staff_excel(
    category_id: uuid.UUID | None = Query(None),
    active_only: bool = Query(True),
    search: str | None = Query(None),
    gender: str | None = Query(None),
    ids=Depends(require_permission("staff", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Export the staff register as an Excel workbook (.xlsx)."""
    from app.services.staff_export import export_excel
    _, school_id = ids
    xlsx = await export_excel(school_id, db, category_id=category_id, active_only=active_only, search=search, gender=gender)
    return StreamingResponse(
        iter([xlsx]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="staff_register.xlsx"'},
    )


@router.get("/export/custom")
async def export_staff_custom(
    fields: str = Query(""),
    fmt: str = Query("csv", pattern="^(csv|excel)$"),
    active_only: bool = Query(True),
    category_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    gender: str | None = Query(None),
    ids=Depends(require_permission("staff", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Export staff with caller-selected fields as CSV or Excel."""
    from app.services.staff_custom_export import export_staff_custom as _export
    _, school_id = ids
    field_list = [f.strip() for f in fields.split(",") if f.strip()]
    data = await _export(
        school_id, db,
        fields=field_list, fmt=fmt,
        active_only=active_only, category_id=category_id,
        search=search, gender=gender,
    )
    if fmt == "excel":
        return StreamingResponse(
            iter([data]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="staff.xlsx"'},
        )
    return StreamingResponse(
        iter([data]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="staff.csv"'},
    )


@router.get("/export/pdf")
async def export_staff_pdf(
    category_id: uuid.UUID | None = Query(None),
    active_only: bool = Query(True),
    search: str | None = Query(None),
    gender: str | None = Query(None),
    ids=Depends(require_permission("staff", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Export the staff register as a PDF (A4 landscape)."""
    from app.services.staff_export import export_pdf
    _, school_id = ids
    pdf = await export_pdf(school_id, db, category_id=category_id, active_only=active_only, search=search, gender=gender)
    return StreamingResponse(
        iter([pdf]),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="staff_register.pdf"'},
    )


# ── Personal permission overrides ─────────────────────────────────────────────

@router.get("/{staff_id}/permissions", response_model=list[StaffPermissionRead])
async def list_staff_permissions(
    staff_id: uuid.UUID,
    ids=Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """Return all 29 permissions with resolved source for a staff member."""
    _, school_id = ids
    return await perms_svc.list_permissions(staff_id, school_id, db)


@router.post("/{staff_id}/permissions", response_model=list[StaffPermissionRead])
async def set_staff_permission(
    staff_id: uuid.UUID,
    req: StaffPermissionUpsert,
    ids=Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """Upsert a personal permission override for a staff member."""
    _, school_id = ids
    return await perms_svc.set_permission(staff_id, school_id, req, db)


@router.delete("/{staff_id}/permissions/{module}/{action}", response_model=list[StaffPermissionRead])
async def clear_staff_permission(
    staff_id: uuid.UUID,
    module: str,
    action: str,
    ids=Depends(require_permission("school", "manage_users")),
    db: AsyncSession = Depends(get_db),
):
    """Remove a personal permission override, reverting to the position default."""
    _, school_id = ids
    return await perms_svc.clear_permission(staff_id, school_id, module, action, db)
