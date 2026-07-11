"""
Year-end promotion / repetition / demotion processing.

A student who is continuing at the school (as opposed to graduating, withdrawing,
or transferring — see graduation.py) gets one GraduationRecord for the outcome
(PROMOTED/REPEATED/DEMOTED) plus a new StudentClassAssignment for the destination
class/year, and optionally a TermEnrollment for the first term.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import GraduationRecord
from app.schemas.student_lifecycle import (
    BulkPromoteRequest, BulkPromoteResult, GraduationRecordRead,
)
from app.schemas.students import StudentClassAssignmentCreate, TermEnrollmentCreate
from app.services.student_class_assignment import create_class_assignment
from app.services.student_enrollment import create_term_enrollment


async def process_bulk_promotion(
    req: BulkPromoteRequest,
    user_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> BulkPromoteResult:
    """
    Idempotent: if a GraduationRecord for (student, academic_year) already exists
    it is skipped (counted in `skipped`, not `processed`) — the student keeps
    whatever class assignment resulted from the original processing.
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
        try:
            async with db.begin_nested():
                db.add(record)
                await db.flush()
                await create_class_assignment(
                    StudentClassAssignmentCreate(
                        student_id=item.student_id,
                        class_id=item.class_id,
                        academic_year_id=req.academic_year_id,
                    ),
                    school_id, user_id, db,
                )
                if req.academic_term_id:
                    await create_term_enrollment(
                        TermEnrollmentCreate(
                            student_id=item.student_id,
                            academic_term_id=req.academic_term_id,
                        ),
                        school_id, user_id, db,
                    )
        except HTTPException as e:
            if e.status_code != 409:
                raise
        except IntegrityError:
            pass
        else:
            records.append(record)
            continue

        # Duplicate (409 or IntegrityError) — someone already processed this
        # student/year; count as skipped and surface the existing record.
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

    return BulkPromoteResult(
        processed=len(records) - skipped,
        skipped=skipped,
        records=[GraduationRecordRead.model_validate(r) for r in records],
    )
