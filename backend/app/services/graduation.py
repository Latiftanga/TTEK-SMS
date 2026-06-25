"""Year-end graduation processing — creates GraduationRecord rows."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import GraduationRecord
from app.models.students import Student, StudentClassAssignment
from app.schemas.students import (
    BulkGraduateRequest, BulkGraduateResult, GraduationRecordRead,
)


async def process_bulk_graduation(
    req: BulkGraduateRequest,
    user_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> BulkGraduateResult:
    """
    Create GraduationRecord rows for each entry in req.records.

    Idempotent: if a record for (student, academic_year) already exists
    it is skipped (counted in `skipped`, not `processed`).

    When req.deactivate_students is True:
      - student.is_active is set to False
      - The matching StudentClassAssignment row is deactivated
    """
    now = datetime.now(timezone.utc)
    records: list[GraduationRecord] = []
    skipped = 0

    for item in req.records:
        existing = await db.scalar(
            select(GraduationRecord).where(
                GraduationRecord.student_id == item.student_id,
                GraduationRecord.academic_year_id == req.academic_year_id,
                GraduationRecord.school_id == school_id,
            )
        )
        if existing:
            skipped += 1
            records.append(existing)
            continue

        record = GraduationRecord(
            school_id=school_id,
            student_id=item.student_id,
            academic_year_id=req.academic_year_id,
            graduation_type=item.graduation_type,
            notes=item.notes,
            processed_at=now,
            processed_by_id=user_id,
        )
        db.add(record)

        if req.deactivate_students:
            student = await db.get(Student, item.student_id)
            if student:
                student.is_active = False

            assignment = await db.scalar(
                select(StudentClassAssignment).where(
                    StudentClassAssignment.student_id == item.student_id,
                    StudentClassAssignment.academic_year_id == req.academic_year_id,
                    StudentClassAssignment.school_id == school_id,
                    StudentClassAssignment.is_active == True,  # noqa: E712
                )
            )
            if assignment:
                assignment.is_active = False

        await db.flush()
        records.append(record)

    return BulkGraduateResult(
        processed=len(records) - skipped,
        skipped=skipped,
        records=[GraduationRecordRead.model_validate(r) for r in records],
    )


async def list_graduation_records(
    school_id: uuid.UUID,
    db: AsyncSession,
    academic_year_id: uuid.UUID | None = None,
) -> list[GraduationRecordRead]:
    stmt = select(GraduationRecord).where(GraduationRecord.school_id == school_id)
    if academic_year_id:
        stmt = stmt.where(GraduationRecord.academic_year_id == academic_year_id)
    rows = await db.execute(stmt.order_by(GraduationRecord.processed_at.desc()))
    return [GraduationRecordRead.model_validate(r) for r in rows.scalars()]
