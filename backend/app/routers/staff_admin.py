"""Staff register export and personal permission overrides. Split out of
routers/staff.py to stay under the 300-line cap.

ACCESS CONTROL
--------------
GET  /staff/export/custom             staff.view
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

_MEDIA_TYPES = {
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "csv": "text/csv",
}
_EXTENSIONS = {"excel": "xlsx", "pdf": "pdf", "csv": "csv"}


@router.get("/export/custom")
async def export_staff_custom(
    fields: str = Query(""),
    fmt: str = Query("csv", pattern="^(csv|excel|pdf)$"),
    active_only: bool = Query(True),
    category_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    gender: str | None = Query(None),
    ids=Depends(require_permission("staff", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Export staff with caller-selected fields as CSV, Excel, or PDF —
    the single staff export path (a fixed-column Excel/PDF quick-export used
    to exist alongside this; it duplicated exactly what a default field
    selection here already produces, so it was removed in favour of this
    one endpoint)."""
    from app.services.staff_custom_export import export_staff_custom as _export
    _, school_id = ids
    field_list = [f.strip() for f in fields.split(",") if f.strip()]
    data = await _export(
        school_id, db,
        fields=field_list, fmt=fmt,
        active_only=active_only, category_id=category_id,
        search=search, gender=gender,
    )
    return StreamingResponse(
        iter([data]),
        media_type=_MEDIA_TYPES[fmt],
        headers={"Content-Disposition": f'attachment; filename="staff.{_EXTENSIONS[fmt]}"'},
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
