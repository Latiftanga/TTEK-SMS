"""
Attendance trends + export — split out of routers/attendance.py to stay
under the 300-line cap.

Permission map: attendance.view (read-only, any authenticated staff).
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models.school import School
from app.schemas.attendance_trends import AttendanceTrendPoint
from app.services import attendance_trends as trends_svc
from app.services.export_utils import rows_to_bytes
from app.services.pdf import render_export_table

router = APIRouter(prefix="/attendance", tags=["attendance"])

_EXPORT_MEDIA_TYPES = {
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "csv": "text/csv",
}
_EXPORT_EXTENSIONS = {"excel": "xlsx", "pdf": "pdf", "csv": "csv"}


@router.get("/trends", response_model=list[AttendanceTrendPoint])
async def get_attendance_trend(
    term_id: uuid.UUID = Query(...),
    class_id: uuid.UUID | None = Query(None),
    ids=Depends(require_permission("attendance", "view")),
    db: AsyncSession = Depends(get_db),
):
    """Day-by-day attendance rate for a term — every visible class's
    students if class_id is omitted, scoped exactly like every other
    attendance read."""
    user_id, school_id = ids
    return await trends_svc.get_attendance_trend(term_id, school_id, user_id, db, class_id=class_id)


@router.get("/export")
async def export_attendance(
    term_id: uuid.UUID = Query(...),
    class_id: uuid.UUID | None = Query(None),
    fmt: str = Query("csv", pattern="^(csv|excel|pdf)$"),
    ids=Depends(require_permission("attendance", "view")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = ids
    headers, rows = await trends_svc.get_attendance_export_rows(term_id, school_id, user_id, db, class_id=class_id)
    if fmt == "pdf":
        school = await db.get(School, school_id)
        data = render_export_table(
            school, "Attendance Report", headers, rows,
            datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M"), len(rows),
        )
    else:
        data = rows_to_bytes(headers, rows, fmt, sheet_title="Attendance")
    return StreamingResponse(
        iter([data]),
        media_type=_EXPORT_MEDIA_TYPES[fmt],
        headers={"Content-Disposition": f'attachment; filename="attendance.{_EXPORT_EXTENSIONS[fmt]}"'},
    )
