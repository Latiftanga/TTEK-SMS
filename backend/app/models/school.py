"""
Group 1 — School identity and configuration models.

Tables in this group:
  ghana_region    — the 16 administrative regions of Ghana (seeded, read-only)
  ghana_district  — Ghana's districts per region (~260, seeded, read-only)
  school          — the top-level school entity; every other table links to this
  school_config   — key-value settings store per school (e.g. report card template)
  sms_config      — SMS provider credentials per school (AfricasTalking, Hubtel, etc.)

MULTI-TENANCY
-------------
Every school-scoped table includes school_id as a non-nullable FK to school.id.
This is enforced via SchoolScopedMixin in models/base.py.
The GhanaRegion, GhanaDistrict tables are system-wide and do NOT have school_id.

SCHOOL TYPES
------------
A school is either BASIC (primary + JHS) or SHS (senior high school).
One organisation = one record.  A school cannot be both types simultaneously.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, SchoolScopedMixin, TimestampMixin, UUIDPrimaryKey


class SchoolType(str, enum.Enum):
    BASIC = "BASIC"
    SHS = "SHS"


class SchoolOwnership(str, enum.Enum):
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"


class AiProvider(str, enum.Enum):
    GEMINI = "GEMINI"           # Google Gemini — free tier: 1 500 req/day
    GROQ = "GROQ"               # Groq — free tier: fast Llama 3 models
    ANTHROPIC = "ANTHROPIC"     # Anthropic Claude
    OPENAI = "OPENAI"           # OpenAI GPT


class SmsProvider(str, enum.Enum):
    AFRICAS_TALKING = "AFRICAS_TALKING"
    HUBTEL = "HUBTEL"
    ARKESEL = "ARKESEL"
    WIGAL = "WIGAL"
    TWILIO = "TWILIO"


class SmsStatus(str, enum.Enum):
    SENT = "SENT"
    FAILED = "FAILED"


class EmailProvider(str, enum.Enum):
    SMTP = "SMTP"
    SENDGRID = "SENDGRID"
    MAILGUN = "MAILGUN"
    BREVO = "BREVO"


class EmailStatus(str, enum.Enum):
    SENT = "SENT"
    FAILED = "FAILED"


class GhanaRegion(Base, UUIDPrimaryKey):
    __tablename__ = "ghana_region"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)

    districts: Mapped[list[GhanaDistrict]] = relationship(back_populates="region")
    schools: Mapped[list[School]] = relationship(back_populates="region")


class GhanaDistrict(Base, UUIDPrimaryKey):
    __tablename__ = "ghana_district"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    region_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ghana_region.id"), nullable=False, index=True
    )

    region: Mapped[GhanaRegion] = relationship(back_populates="districts")
    schools: Mapped[list[School]] = relationship(back_populates="district")


class School(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "school"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    school_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    school_type: Mapped[SchoolType] = mapped_column(SAEnum(SchoolType, name="schooltype"), nullable=False)
    ownership: Mapped[SchoolOwnership] = mapped_column(
        SAEnum(SchoolOwnership, name="schoolownership"), nullable=False, default=SchoolOwnership.PUBLIC
    )
    region_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ghana_region.id"), nullable=False
    )
    district_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ghana_district.id"), nullable=False
    )
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    motto: Mapped[str | None] = mapped_column(String(200), nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    established_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    has_boarding: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Branding ──────────────────────────────────────────────────────────────
    # subdomain: URL-safe slug used for per-school routing, e.g. "presec" →
    #   presec.ttek-sms.com.  Must be lowercase, hyphens allowed, 3-50 chars.
    subdomain: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)
    # custom_domain: a school-owned domain pointing to this platform, e.g.
    #   portal.presec.com.  School sets a CNAME to the platform; superadmin
    #   registers it here.  Must be globally unique.
    custom_domain: Mapped[str | None] = mapped_column(String(253), unique=True, nullable=True, index=True)
    # brand_color: single hex colour the school admin picks.  The frontend
    #   derives the full light/dark palette from this value — admins can't
    #   break the UI by choosing a bad colour combination.
    brand_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#1e40af")

    region: Mapped[GhanaRegion] = relationship(back_populates="schools", foreign_keys=[region_id])
    district: Mapped[GhanaDistrict] = relationship(back_populates="schools", foreign_keys=[district_id])
    configs: Mapped[list[SchoolConfig]] = relationship(back_populates="school")
    sms_configs: Mapped[list[SmsConfig]] = relationship(back_populates="school")
    email_configs: Mapped[list[EmailConfig]] = relationship(back_populates="school")
    ai_configs: Mapped[list[AiConfig]] = relationship(back_populates="school")


class SchoolConfig(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    __tablename__ = "school_config"
    __table_args__ = (UniqueConstraint("school_id", "key", name="uq_school_config_key"),)

    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(2000), nullable=False)

    school: Mapped[School] = relationship(back_populates="configs")


class SmsConfig(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    __tablename__ = "sms_config"

    provider: Mapped[SmsProvider] = mapped_column(SAEnum(SmsProvider, name="smsprovider"), nullable=False)
    api_key: Mapped[str] = mapped_column(String(500), nullable=False)
    api_secret: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sender_id: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    school: Mapped[School] = relationship(back_populates="sms_configs")


class EmailConfig(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    """Email provider credentials per school. Only one is active at a time."""
    __tablename__ = "email_config"

    provider: Mapped[EmailProvider] = mapped_column(SAEnum(EmailProvider, name="emailprovider"), nullable=False)
    host: Mapped[str | None] = mapped_column(String(253), nullable=True)       # SMTP host
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)            # SMTP port
    username: Mapped[str] = mapped_column(String(500), nullable=False)          # SMTP user / API key
    password: Mapped[str | None] = mapped_column(String(500), nullable=True)   # SMTP pass / API secret
    from_name: Mapped[str] = mapped_column(String(100), nullable=False)
    from_address: Mapped[str] = mapped_column(String(200), nullable=False)
    use_tls: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    school: Mapped[School] = relationship(back_populates="email_configs")


class EmailLog(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """Audit record for every email attempted by the system."""
    __tablename__ = "email_log"

    provider: Mapped[EmailProvider] = mapped_column(SAEnum(EmailProvider, name="emailprovider"), nullable=False)
    recipient: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[EmailStatus] = mapped_column(SAEnum(EmailStatus, name="emailstatus"), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SmsLog(Base, UUIDPrimaryKey, SchoolScopedMixin):
    """
    Audit record for every SMS attempted by the system.

    Written whether the SMS succeeded or failed — the error_message column
    explains failures so admins can diagnose provider issues without needing
    to look at server logs.

    entity_type + entity_id link back to what triggered the message
    (e.g. entity_type="FEE_PAYMENT", entity_id=<payment UUID>).
    """
    __tablename__ = "sms_log"

    provider: Mapped[SmsProvider] = mapped_column(
        SAEnum(SmsProvider, name="smsprovider"), nullable=False
    )
    recipient: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SmsStatus] = mapped_column(
        SAEnum(SmsStatus, name="smsstatus", create_type=True), nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AiConfig(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    """
    AI provider credentials per school. Only one provider is active at a time.

    api_key is stored but NEVER returned by any GET endpoint.
    model is optional — if None, the driver uses the best default for the provider.
    daily_limit_per_teacher caps how many generations a single teacher can
    trigger per day (enforced via Redis). Default is 10.
    """
    __tablename__ = "ai_config"

    provider: Mapped[AiProvider] = mapped_column(
        SAEnum(AiProvider, name="aiprovider"), nullable=False
    )
    api_key: Mapped[str] = mapped_column(String(500), nullable=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    daily_limit_per_teacher: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    school: Mapped[School] = relationship(back_populates="ai_configs")
