"""Schemas for SMS configuration management, manual send, and audit log."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator

from app.models.school import SmsProvider, SmsStatus


class SmsActivateRequest(BaseModel):
    provider: SmsProvider


class SmsSendRequest(BaseModel):
    phones: list[str]
    message: str

    @field_validator("message")
    @classmethod
    def message_length(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message must not be blank.")
        if len(v) > 160:
            raise ValueError("Message must not exceed 160 characters (one SMS segment).")
        return v

    @field_validator("phones")
    @classmethod
    def phones_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one phone number is required.")
        return v


class SmsSendResult(BaseModel):
    phone: str
    success: bool
    error: str | None = None


class SmsSendResponse(BaseModel):
    sent: int
    failed: int
    results: list[SmsSendResult]


class SmsLogRead(BaseModel):
    id: uuid.UUID
    provider: SmsProvider
    recipient: str
    message: str
    status: SmsStatus
    error_message: str | None
    entity_type: str | None
    entity_id: uuid.UUID | None
    sent_at: datetime
    model_config = {"from_attributes": True}
