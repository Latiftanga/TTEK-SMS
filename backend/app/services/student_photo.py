"""
Student photo upload/delete — split out of student.py (was over the
300-line cap). Shares the image pipeline in services/storage.py with the
school logo upload.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.students import Student, StudentGuardian
from app.schemas.students import StudentDetail
from app.services.student import _portal_access, _to_detail


async def upload_student_photo(
    student_id: uuid.UUID,
    file: UploadFile,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> StudentDetail:
    student = await db.scalar(
        select(Student)
        .where(Student.id == student_id, Student.school_id == school_id)
        .options(
            selectinload(Student.medical_record),
            selectinload(Student.guardians).selectinload(StudentGuardian.guardian),
        )
    )
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    from app.services.storage import save_student_photo
    student.photo_path = await save_student_photo(file, student.id)
    await db.flush()
    portal = await _portal_access(student_id, db)
    return _to_detail(student, has_portal_access=portal)


async def remove_student_photo(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    student = await db.get(Student, student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    from app.services.storage import delete_student_photo
    delete_student_photo(student.id)
    student.photo_path = None
    await db.flush()
