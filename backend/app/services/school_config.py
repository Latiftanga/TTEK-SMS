"""
School configuration and SMS provider services.

Separated from services/school.py to keep file sizes under 300 lines.

SCHOOL CONFIG
-------------
SchoolConfig is a simple key-value store for per-school settings.
Each (school_id, key) pair is unique — set_config() is an upsert.
Example keys: "academic_year_format", "report_card_template", "timezone".

SMS CONFIG
----------
SmsConfig holds provider credentials per school (API key, sender ID).
One row per provider per school.  upsert_sms_config() creates or updates.
Only one provider should have is_active=True at a time; the application
reads the active config when sending SMS via the SmsService driver.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import SchoolConfig, SmsConfig
from app.schemas.school import SchoolConfigSet, SmsConfigCreate, SmsConfigRead


async def set_config(
    school_id: uuid.UUID,
    req: SchoolConfigSet,
    db: AsyncSession,
) -> None:
    """
    Create or update a single config key for a school (upsert).

    Config keys are free-form strings — the application defines its own
    convention for key names.  There is no schema enforcement here.
    """
    existing = await db.scalar(
        select(SchoolConfig).where(
            SchoolConfig.school_id == school_id,
            SchoolConfig.key == req.key,
        )
    )
    if existing:
        existing.value = req.value
    else:
        db.add(SchoolConfig(school_id=school_id, key=req.key, value=req.value))
    await db.flush()


async def get_config(school_id: uuid.UUID, db: AsyncSession) -> dict[str, str]:
    """Return all config key-value pairs for a school as a plain dict."""
    rows = await db.scalars(
        select(SchoolConfig).where(SchoolConfig.school_id == school_id)
    )
    return {row.key: row.value for row in rows}


async def upsert_sms_config(
    school_id: uuid.UUID,
    req: SmsConfigCreate,
    db: AsyncSession,
) -> SmsConfigRead:
    """
    Create or update the SMS provider config for a school.

    One SmsConfig row exists per provider per school.  If a row for this
    provider already exists, its fields are updated.  Otherwise a new row
    is created.

    WARNING: api_key and api_secret are stored as plaintext in sms_config.
    Before going to production, encrypt these fields using the school's key
    or store them in a secrets manager (e.g. AWS Secrets Manager, HashiCorp Vault).
    A plaintext DB dump would expose all SMS provider credentials.
    """
    existing = await db.scalar(
        select(SmsConfig).where(
            SmsConfig.school_id == school_id,
            SmsConfig.provider == req.provider,
        )
    )
    if existing:
        for field, value in req.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        await db.flush()
        return SmsConfigRead.model_validate(existing)

    sms_config = SmsConfig(school_id=school_id, **req.model_dump())
    db.add(sms_config)
    await db.flush()
    return SmsConfigRead.model_validate(sms_config)
