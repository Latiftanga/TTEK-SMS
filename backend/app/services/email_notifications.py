"""
Email notification service — high-level notification triggers.

Mirrors sms_notifications.py's contract exactly: same guardian resolution
(primary guardian only), same fire-and-forget guarantee (every public
function catches all exceptions — an email failure never rolls back or
blocks the main database operation), same entity_type/entity_id audit
logging. The only differences are the recipient field (Guardian.email
instead of Guardian.phone) and the config/log tables (EmailConfig/EmailLog
instead of SmsConfig/SmsLog).

NOTIFICATION TYPES
------------------
  notify_fee_receipt_email       → guardian after a fee payment is recorded
  notify_attendance_absent_email → guardian when a student is marked ABSENT
  notify_report_published_email  → guardian when an assessment is published
  notify_transfer_decision_email → guardian when a transfer request is approved/rejected

RECIPIENT RESOLUTION
--------------------
Resolves the student's primary guardian (StudentGuardian.is_primary=True →
Guardian.email). If no primary guardian is set, or the guardian has no
email on file, the notification is silently skipped.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import EmailConfig, EmailLog, EmailStatus
from app.models.students import Guardian, Student, StudentGuardian
from app.services.email_driver import EmailDriver, EmailResult, build_driver


async def _get_active_driver(school_id: uuid.UUID, db: AsyncSession) -> EmailDriver | None:
    config = await db.scalar(
        select(EmailConfig).where(
            EmailConfig.school_id == school_id,
            EmailConfig.is_active.is_(True),
        )
    )
    if not config:
        return None
    return build_driver(
        config.provider, config.host, config.port, config.username,
        config.password, config.use_tls, config.from_name, config.from_address,
    )


async def _primary_guardian_email(
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
    return guardian.email if guardian else None


async def _log_result(
    result: EmailResult,
    recipient: str,
    subject: str,
    school_id: uuid.UUID,
    entity_type: str | None,
    entity_id: uuid.UUID | None,
    db: AsyncSession,
) -> None:
    db.add(EmailLog(
        school_id=school_id,
        provider=result.provider,
        recipient=recipient,
        subject=subject,
        status=EmailStatus.SENT if result.success else EmailStatus.FAILED,
        error_message=result.error,
        entity_type=entity_type,
        entity_id=entity_id,
        sent_at=datetime.now(timezone.utc),
    ))
    await db.flush()


async def _deliver(
    driver: EmailDriver,
    to: str,
    subject: str,
    body: str,
    school_id: uuid.UUID,
    entity_type: str | None,
    entity_id: uuid.UUID | None,
    db: AsyncSession,
) -> None:
    result = await driver.send(to, subject, body)
    await _log_result(result, to, subject, school_id, entity_type, entity_id, db)


# ── Notification triggers ─────────────────────────────────────────────────────

async def notify_fee_receipt_email(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    school_short: str,
    amount: Decimal,
    fee_type_name: str,
    balance: Decimal,
    entity_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Email to primary guardian after a fee payment is recorded."""
    try:
        driver = await _get_active_driver(school_id, db)
        if not driver:
            return
        email = await _primary_guardian_email(student_id, school_id, db)
        if not email:
            return
        student = await db.get(Student, student_id)
        name = f"{student.first_name} {student.last_name}" if student else "Your ward"
        subject = f"Fee receipt — {name}"
        body = (
            f"Dear Parent/Guardian,\n\n"
            f"{name} paid GHS{amount:.2f} ({fee_type_name}).\n"
            f"Remaining balance: GHS{balance:.2f}.\n\n"
            f"-{school_short}"
        )
        await _deliver(driver, email, subject, body, school_id, "FEE_PAYMENT", entity_id, db)
    except Exception:
        pass  # Email failure must never affect the main transaction


async def notify_attendance_absent_email(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    school_short: str,
    absence_date: str,
    entity_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Email to primary guardian when student is marked ABSENT."""
    try:
        driver = await _get_active_driver(school_id, db)
        if not driver:
            return
        email = await _primary_guardian_email(student_id, school_id, db)
        if not email:
            return
        student = await db.get(Student, student_id)
        name = f"{student.first_name} {student.last_name}" if student else "Your ward"
        subject = f"Absence notice — {name}"
        body = (
            f"Dear Parent/Guardian,\n\n"
            f"{name} was absent from {school_short} on {absence_date}.\n"
            f"Please contact the school if this is unexpected.\n\n"
            f"-{school_short}"
        )
        await _deliver(driver, email, subject, body, school_id, "ATTENDANCE", entity_id, db)
    except Exception:
        pass


async def notify_report_published_email(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    school_short: str,
    school_code: str,
    term_name: str,
    entity_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Email to primary guardian when a term assessment is published."""
    try:
        driver = await _get_active_driver(school_id, db)
        if not driver:
            return
        email = await _primary_guardian_email(student_id, school_id, db)
        if not email:
            return
        student = await db.get(Student, student_id)
        name = f"{student.first_name} {student.last_name}" if student else "Your ward"
        subject = f"{term_name} report ready — {name}"
        body = (
            f"Dear Parent/Guardian,\n\n"
            f"{name}'s {term_name} report is ready.\n"
            f"Log in at {school_code.lower()}.ttek-sms.com to view it.\n\n"
            f"-{school_short}"
        )
        await _deliver(driver, email, subject, body, school_id, "REPORT_CARD", entity_id, db)
    except Exception:
        pass


async def notify_transfer_decision_email(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    school_short: str,
    approved: bool,
    entity_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Email to primary guardian when a transfer request is approved or rejected."""
    try:
        driver = await _get_active_driver(school_id, db)
        if not driver:
            return
        email = await _primary_guardian_email(student_id, school_id, db)
        if not email:
            return
        student = await db.get(Student, student_id)
        name = f"{student.first_name} {student.last_name}" if student else "Your ward"
        outcome = "approved" if approved else "not approved"
        subject = f"Transfer request update — {name}"
        body = (
            f"Dear Parent/Guardian,\n\n"
            f"The transfer request for {name} was {outcome}.\n\n"
            f"-{school_short}"
        )
        await _deliver(driver, email, subject, body, school_id, "TRANSFER", entity_id, db)
    except Exception:
        pass
