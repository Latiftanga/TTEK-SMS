"""Grant and revoke student portal access.

Portal login uses ADMISSION_ID — the student's admission number is both
their username and the initial password. The guardian is notified by SMS.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.auth import LoginType, User
from app.models.students import Student, StudentGuardian, Guardian
from app.schemas.students import PortalAccessResult


async def grant_portal_access(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> PortalAccessResult:
    student = await db.get(Student, student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    existing = await db.scalar(
        select(User).where(User.student_id == student_id)
    )
    if existing:
        if existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Student already has portal access.",
            )
        # Re-activate if previously revoked
        existing.is_active = True
        existing.admission_id = student.admission_number
        existing.password_hash = hash_password(student.admission_number)
        await db.flush()
        sms_sent = await _notify_guardian(student, school_id, db)
        return PortalAccessResult(
            has_portal_access=True,
            admission_number=student.admission_number,
            sms_sent=sms_sent,
        )

    user = User(
        school_id=school_id,
        login_type=LoginType.ADMISSION_ID,
        admission_id=student.admission_number,
        password_hash=hash_password(student.admission_number),
        student_id=student_id,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    sms_sent = await _notify_guardian(student, school_id, db)
    return PortalAccessResult(
        has_portal_access=True,
        admission_number=student.admission_number,
        sms_sent=sms_sent,
    )


async def revoke_portal_access(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    student = await db.get(Student, student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    user = await db.scalar(
        select(User).where(User.student_id == student_id, User.is_active.is_(True))
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student does not have active portal access.",
        )
    user.is_active = False
    await db.flush()


async def _notify_guardian(student: Student, school_id: uuid.UUID, db: AsyncSession) -> bool:
    """
    NOTE: previously called sms_notifications.get_active_driver (never
    existed — the function is named _get_active_driver) and _log_result with
    the wrong argument order, so every call silently returned False via the
    broad except below regardless of SMS config. Fixed to go through the
    public notify_portal_access() helper instead of reaching into private
    module internals directly.
    """
    try:
        sg = await db.scalar(
            select(StudentGuardian)
            .where(StudentGuardian.student_id == student.id, StudentGuardian.is_primary.is_(True))
        )
        if not sg:
            return False
        guardian = await db.get(Guardian, sg.guardian_id)
        if not guardian or not guardian.phone:
            return False

        from app.models.school import School
        school = await db.get(School, school_id)
        school_name = school.name if school else "the school"

        msg = (
            f"Dear Parent/Guardian, {student.first_name} {student.last_name} "
            f"({student.admission_number}) now has access to the {school_name} student portal. "
            f"Login with admission number as username and password. "
            f"Please change the password after first login."
        )
        from app.services.sms_notifications import notify_portal_access
        return await notify_portal_access(guardian.phone, msg, school_id, "STUDENT_PORTAL", student.id, db)
    except Exception:
        return False
