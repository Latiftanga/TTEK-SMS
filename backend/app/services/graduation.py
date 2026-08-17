"""Year-end graduation processing — creates GraduationRecord rows."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import GraduationRecord
from app.models.students import Student
from app.schemas.student_lifecycle import (
    BulkGraduateRequest, BulkGraduateResult, GraduationRecordRead,
)
from app.services.student_lifecycle import deactivate_student


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

    When req.deactivate_students is True, the student, their current-year class
    assignment/term enrollment, and their portal login are all deactivated
    (see student_lifecycle.deactivate_student).
    """
    # Validated up front, whole batch — a cross-school or bogus student_id
    # here is not a legitimate "already processed" case like the duplicate-
    # GraduationRecord skip below, it's illegitimate input (a bug or a
    # cross-tenant probe): GraduationRecord.student_id has no FK-level
    # guarantee of belonging to this school_id, and deactivate_student()
    # would otherwise silently deactivate another school's real student
    # and revoke their portal login. No partial writes on a mixed batch,
    # matching this codebase's promotion-validation precedent.
    student_ids = {item.student_id for item in req.records}
    valid_ids = set(await db.scalars(
        select(Student.id).where(Student.id.in_(student_ids), Student.school_id == school_id)
    ))
    invalid_ids = student_ids - valid_ids
    if invalid_ids:
        raise HTTPException(
            404, f"Student(s) not found in this school: {', '.join(str(i) for i in invalid_ids)}",
        )

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
        try:
            async with db.begin_nested():
                db.add(record)
                if req.deactivate_students:
                    await deactivate_student(
                        item.student_id, school_id, db, academic_year_id=req.academic_year_id,
                    )
                await db.flush()
        except IntegrityError:
            db.expunge(record)
            skipped += 1
            existing = await db.scalar(
                select(GraduationRecord).where(
                    GraduationRecord.student_id == item.student_id,
                    GraduationRecord.academic_year_id == req.academic_year_id,
                    GraduationRecord.school_id == school_id,
                )
            )
            if existing:
                records.append(existing)
            continue

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
    student_id: uuid.UUID | None = None,
) -> list[GraduationRecordRead]:
    stmt = select(GraduationRecord).where(GraduationRecord.school_id == school_id)
    if academic_year_id:
        stmt = stmt.where(GraduationRecord.academic_year_id == academic_year_id)
    if student_id:
        stmt = stmt.where(GraduationRecord.student_id == student_id)
    rows = await db.execute(stmt.order_by(GraduationRecord.processed_at.desc()))
    return [GraduationRecordRead.model_validate(r) for r in rows.scalars()]
