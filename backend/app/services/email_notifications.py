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
  notify_attendance_risk_email   → guardian when a student crosses into AT_RISK/SEVERE
  notify_consecutive_absence_email → guardian after 3 consecutive ABSENT school days
  notify_report_published_email  → guardian when an assessment is published
  notify_transfer_decision_email → guardian when a transfer request is approved/rejected
  notify_excuse_decision_email   → guardian when an absence excuse request is approved/rejected

RECIPIENT RESOLUTION
--------------------
Resolves the student's primary guardian (StudentGuardian.is_primary=True →
Guardian.email). If no primary guardian is set, or the guardian has no
email on file, the notification is silently skipped.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.school import EmailConfig, EmailLog, EmailStatus
from app.models.students import Guardian, Student, StudentGuardian
from app.services.email_driver import EmailDriver, EmailResult, build_driver

logger = logging.getLogger(__name__)


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
        logger.exception("notify_attendance_absent_email failed for student %s", student_id)


async def notify_attendance_risk_email(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    school_short: str,
    tier: str,
    rate: float,
    entity_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Email to primary guardian when a student's term-to-date attendance
    crosses into AT_RISK (<90%) or SEVERE (<80%)."""
    try:
        driver = await _get_active_driver(school_id, db)
        if not driver:
            return
        email = await _primary_guardian_email(student_id, school_id, db)
        if not email:
            return
        student = await db.get(Student, student_id)
        name = f"{student.first_name} {student.last_name}" if student else "Your ward"
        urgency = "urgently " if tier == "SEVERE" else ""
        subject = f"Attendance concern — {name}"
        body = (
            f"Dear Parent/Guardian,\n\n"
            f"{name}'s attendance at {school_short} this term is {rate:.0f}%, below the "
            f"recommended level.\n"
            f"Please {urgency}contact the school to discuss.\n\n"
            f"-{school_short}"
        )
        await _deliver(driver, email, subject, body, school_id, "ATTENDANCE_RISK", entity_id, db)
    except Exception:
        logger.exception("notify_attendance_risk_email failed for student %s", student_id)


async def notify_consecutive_absence_email(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    school_short: str,
    entity_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Email to primary guardian after 3 consecutive markable school days
    all marked ABSENT."""
    try:
        driver = await _get_active_driver(school_id, db)
        if not driver:
            return
        email = await _primary_guardian_email(student_id, school_id, db)
        if not email:
            return
        student = await db.get(Student, student_id)
        name = f"{student.first_name} {student.last_name}" if student else "Your ward"
        subject = f"3 consecutive absences — {name}"
        body = (
            f"Dear Parent/Guardian,\n\n"
            f"{name} has now been absent from {school_short} for 3 school days in a row.\n"
            f"Please contact the school.\n\n"
            f"-{school_short}"
        )
        await _deliver(driver, email, subject, body, school_id, "ATTENDANCE_CONSECUTIVE", entity_id, db)
    except Exception:
        logger.exception("notify_consecutive_absence_email failed for student %s", student_id)


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
        login_line = (
            f"Log in at {school_code.lower()}.{settings.platform_domain} to view it.\n\n"
            if settings.platform_domain
            else "Check with your school for how to view it.\n\n"
        )
        body = (
            f"Dear Parent/Guardian,\n\n"
            f"{name}'s {term_name} report is ready.\n"
            f"{login_line}"
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


async def notify_excuse_decision_email(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    school_short: str,
    approved: bool,
    entity_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Email to primary guardian when an absence excuse request is approved or rejected."""
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
        subject = f"Absence excuse request update — {name}"
        body = (
            f"Dear Parent/Guardian,\n\n"
            f"The absence excuse request for {name} was {outcome}.\n\n"
            f"-{school_short}"
        )
        await _deliver(driver, email, subject, body, school_id, "EXCUSE_REQUEST", entity_id, db)
    except Exception:
        logger.exception("notify_excuse_decision_email failed for student %s", student_id)
