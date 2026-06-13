"""
SMS notification service — high-level notification triggers.

All public functions are fire-and-forget: they catch every exception so that
an SMS failure never rolls back or blocks the main database operation.

NOTIFICATION TYPES
------------------
  notify_fee_receipt       → guardian after a fee payment is recorded
  notify_attendance_absent → guardian when a student is marked ABSENT
  notify_report_published  → guardian when an assessment is published
  send_manual              → admin-initiated message to specified phones

RECIPIENT RESOLUTION
--------------------
All automatic notifications resolve recipients via the student's primary
guardian (StudentGuardian.is_primary=True → Guardian.phone).  If no primary
guardian is set, the notification is silently skipped (nothing to send to).

MESSAGE LENGTH
--------------
Compose messages under 160 GSM-7 characters.  If a message exceeds this,
most providers will concatenate segments and charge per segment.
Templates are kept short deliberately.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import SmsConfig, SmsLog, SmsStatus
from app.models.students import Guardian, Student, StudentGuardian
from app.services.sms_driver import SmsDriver, SmsResult, build_driver


async def _get_active_driver(school_id: uuid.UUID, db: AsyncSession) -> SmsDriver | None:
    config = await db.scalar(
        select(SmsConfig).where(
            SmsConfig.school_id == school_id,
            SmsConfig.is_active.is_(True),
        )
    )
    if not config:
        return None
    return build_driver(config.provider, config.api_key, config.api_secret, config.sender_id)


async def _primary_guardian_phone(
    student_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> str | None:
    link = await db.scalar(
        select(StudentGuardian).where(
            StudentGuardian.student_id == student_id,
            StudentGuardian.school_id == school_id,
            StudentGuardian.is_primary.is_(True),
        )
    )
    if not link:
        return None
    guardian = await db.get(Guardian, link.guardian_id)
    return guardian.phone if guardian else None


async def _log_result(
    result: SmsResult,
    recipient: str,
    message: str,
    school_id: uuid.UUID,
    entity_type: str | None,
    entity_id: uuid.UUID | None,
    db: AsyncSession,
) -> None:
    db.add(SmsLog(
        school_id=school_id,
        provider=result.provider,
        recipient=recipient,
        message=message,
        status=SmsStatus.SENT if result.success else SmsStatus.FAILED,
        error_message=result.error,
        entity_type=entity_type,
        entity_id=entity_id,
        sent_at=datetime.now(timezone.utc),
    ))
    await db.flush()


async def _deliver(
    driver: SmsDriver,
    to: str,
    message: str,
    school_id: uuid.UUID,
    entity_type: str | None,
    entity_id: uuid.UUID | None,
    db: AsyncSession,
) -> None:
    result = await driver.send(to, message)
    await _log_result(result, to, message, school_id, entity_type, entity_id, db)


# ── Notification triggers ─────────────────────────────────────────────────────

async def notify_fee_receipt(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    school_short: str,
    amount: Decimal,
    fee_type_name: str,
    balance: Decimal,
    entity_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """SMS to primary guardian after a fee payment is recorded."""
    try:
        driver = await _get_active_driver(school_id, db)
        if not driver:
            return
        phone = await _primary_guardian_phone(student_id, school_id, db)
        if not phone:
            return
        student = await db.get(Student, student_id)
        name = f"{student.first_name} {student.last_name}" if student else "Your ward"
        msg = (
            f"Fee receipt: {name} paid GHS{amount:.2f} ({fee_type_name}). "
            f"Balance: GHS{balance:.2f}. -{school_short}"
        )
        await _deliver(driver, phone, msg[:160], school_id, "FEE_PAYMENT", entity_id, db)
    except Exception:
        pass  # SMS failure must never affect the main transaction


async def notify_attendance_absent(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    school_short: str,
    absence_date: str,
    entity_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """SMS to primary guardian when student is marked ABSENT."""
    try:
        driver = await _get_active_driver(school_id, db)
        if not driver:
            return
        phone = await _primary_guardian_phone(student_id, school_id, db)
        if not phone:
            return
        student = await db.get(Student, student_id)
        name = f"{student.first_name} {student.last_name}" if student else "Your ward"
        msg = (
            f"{name} was absent from {school_short} on {absence_date}. "
            f"Contact the school if this is unexpected."
        )
        await _deliver(driver, phone, msg[:160], school_id, "ATTENDANCE", entity_id, db)
    except Exception:
        pass


async def notify_report_published(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    school_short: str,
    school_code: str,
    term_name: str,
    entity_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """SMS to primary guardian when a term assessment is published."""
    try:
        driver = await _get_active_driver(school_id, db)
        if not driver:
            return
        phone = await _primary_guardian_phone(student_id, school_id, db)
        if not phone:
            return
        student = await db.get(Student, student_id)
        name = f"{student.first_name} {student.last_name}" if student else "Your ward"
        msg = (
            f"{name}'s {term_name} report is ready. "
            f"Log in to view at {school_code.lower()}.ttek-sms.com. -{school_short}"
        )
        await _deliver(driver, phone, msg[:160], school_id, "REPORT_CARD", entity_id, db)
    except Exception:
        pass


async def send_manual(
    phones: list[str],
    message: str,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[SmsResult]:
    """
    Admin-initiated manual SMS to a list of phone numbers.

    Unlike the automatic notifications, this raises if no active provider
    is configured (caller should surface a 503 to the admin).
    """
    driver = await _get_active_driver(school_id, db)
    if not driver:
        raise ValueError("No active SMS provider configured for this school.")
    results: list[SmsResult] = []
    for phone in phones:
        result = await driver.send(phone, message)
        await _log_result(result, phone, message, school_id, "MANUAL", None, db)
        results.append(result)
    return results
