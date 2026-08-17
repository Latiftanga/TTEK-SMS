"""
SMS notification service — high-level notification triggers.

All public functions are fire-and-forget: they catch every exception so that
an SMS failure never rolls back or blocks the main database operation.

NOTIFICATION TYPES
------------------
  notify_fee_receipt       → guardian after a fee payment is recorded
  notify_attendance_absent → guardian when a student is marked ABSENT
  notify_report_published  → guardian when an assessment is published
  notify_transfer_decision → guardian when a transfer request is approved/rejected
  notify_staff_invite      → staff member with their invitation link
  notify_portal_access     → student or guardian confirming their own new portal login
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

from app.core.config import settings
from app.models.school import SmsConfig, SmsLog, SmsStatus
from app.models.students import Guardian, Student, StudentGuardian
from app.services.sms_driver import SmsDriver, SmsResult, build_driver, _normalize_phone


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


_MAX_RECIPIENT_LEN = 20  # matches SmsLog.recipient's String(20) column


async def _deliver(
    driver: SmsDriver,
    to: str,
    message: str,
    school_id: uuid.UUID,
    entity_type: str | None,
    entity_id: uuid.UUID | None,
    db: AsyncSession,
) -> SmsResult:
    """Normalizes once, sends, and logs the normalized number — so SmsLog.recipient
    always reflects the number actually dialed, not whatever format it was typed in.

    _normalize_phone() is best-effort: anything that doesn't match a
    recognized Ghana pattern passes through unchanged, so garbage input
    (e.g. a malformed manual-send entry) could normalize to a string longer
    than the recipient column — a raw DataError on the flush below instead
    of a clean failed result. Caught before ever calling the driver, so a
    bad number never gets dialed at all and never crashes the caller."""
    normalized = _normalize_phone(to)
    if len(normalized) > _MAX_RECIPIENT_LEN:
        result = SmsResult(success=False, provider=driver.provider, error="Invalid phone number.")
        await _log_result(result, normalized[:_MAX_RECIPIENT_LEN], message, school_id, entity_type, entity_id, db)
        return result
    result = await driver.send(normalized, message)
    await _log_result(result, normalized, message, school_id, entity_type, entity_id, db)
    return result


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
        login_clause = (
            f"Log in to view at {school_code.lower()}.{settings.platform_domain}. "
            if settings.platform_domain
            else "Check with your school for how to view it. "
        )
        msg = (
            f"{name}'s {term_name} report is ready. "
            f"{login_clause}-{school_short}"
        )
        await _deliver(driver, phone, msg[:160], school_id, "REPORT_CARD", entity_id, db)
    except Exception:
        pass


async def notify_transfer_decision(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    school_short: str,
    approved: bool,
    entity_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """SMS to primary guardian when a transfer request is approved or rejected."""
    try:
        driver = await _get_active_driver(school_id, db)
        if not driver:
            return
        phone = await _primary_guardian_phone(student_id, school_id, db)
        if not phone:
            return
        student = await db.get(Student, student_id)
        name = f"{student.first_name} {student.last_name}" if student else "Your ward"
        outcome = "approved" if approved else "not approved"
        msg = f"The transfer request for {name} was {outcome}. -{school_short}"
        await _deliver(driver, phone, msg[:160], school_id, "TRANSFER", entity_id, db)
    except Exception:
        pass


async def notify_staff_invite(
    phone: str,
    staff_name: str,
    school_name: str,
    school_id: uuid.UUID,
    invite_link: str,
    invitation_id: uuid.UUID,
    db: AsyncSession,
) -> bool:
    """
    SMS to a staff member with their invitation link.
    Returns True if the SMS was sent successfully, False otherwise.
    Fire-and-forget: never raises.
    """
    try:
        driver = await _get_active_driver(school_id, db)
        if not driver:
            return False
        msg = (
            f"Hi {staff_name}, you've been invited to join {school_name} "
            f"on TTEK-SMS. Set your password here: {invite_link}"
        )
        result = await _deliver(driver, phone, msg, school_id, "STAFF_INVITE", invitation_id, db)
        return result.success
    except Exception:
        return False


async def notify_portal_access(
    phone: str,
    message: str,
    school_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    db: AsyncSession,
) -> bool:
    """
    SMS confirming a portal login was just granted — used for both the
    student ADMISSION_ID portal (message goes to the primary guardian) and
    the guardian PHONE portal (message goes to the guardian themselves).

    Unlike the other notify_* functions this doesn't build its own message
    template — the two callers have different content (admission number vs
    phone-as-username) but identical send/log mechanics, so only that shared
    part is centralised here.

    Returns True if the SMS was sent successfully, False otherwise.
    Fire-and-forget: never raises.
    """
    try:
        driver = await _get_active_driver(school_id, db)
        if not driver:
            return False
        result = await _deliver(driver, phone, message, school_id, entity_type, entity_id, db)
        return result.success
    except Exception:
        return False


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
    # Per-item savepoint, matching this codebase's established bulk-operation
    # convention (student_import/staff_import/bulk_promote/...): a DB-level
    # failure logging one phone must not roll back the whole session and
    # erase the audit trail of every message already sent — and already
    # dispatched — earlier in the same batch.
    for phone in phones:
        try:
            async with db.begin_nested():
                result = await _deliver(driver, phone, message, school_id, "MANUAL", None, db)
        except Exception as exc:
            result = SmsResult(success=False, provider=driver.provider, error=str(exc))
        results.append(result)
    return results
