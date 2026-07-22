from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator
from app.models.auth import LoginType


class LoginRequest(BaseModel):
    login_type: LoginType
    identifier: str    # email / phone / admission_id depending on login_type
    password: str
    school_code: str | None = None  # required for ADMISSION_ID login
    remember_me: bool = False       # extend refresh token to 30 days


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserRead(BaseModel):
    id: uuid.UUID
    login_type: LoginType
    email: str | None
    phone: str | None
    is_active: bool
    is_superadmin: bool
    school_id: uuid.UUID | None
    staff_member_id: uuid.UUID | None
    student_id: uuid.UUID | None
    guardian_id: uuid.UUID | None
    last_login_at: datetime | None
    display_name: str | None = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    """Used by superadmin to create a user directly (bypassing invitation)."""
    login_type: LoginType
    email: EmailStr | None = None
    phone: str | None = None
    password: str
    school_id: uuid.UUID | None = None
    is_superadmin: bool = False

    @field_validator("email", mode="before")
    @classmethod
    def email_lower(cls, v: str | None) -> str | None:
        return v.lower().strip() if v else v

    @field_validator("phone", mode="before")
    @classmethod
    def phone_strip(cls, v: str | None) -> str | None:
        return v.strip() if v else v


class InvitationCreate(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None
    position_id: uuid.UUID | None = None
    staff_member_id: uuid.UUID | None = None   # links resulting User to existing StaffMember


class StaffPermissionRead(BaseModel):
    module: str
    action: str
    effective: bool
    source: str      # "override" | "position" | "default_deny"
    override_is_allowed: bool | None = None


class StaffPermissionUpsert(BaseModel):
    module: str
    action: str
    is_allowed: bool


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class AcceptInvitationRequest(BaseModel):
    token: str
    password: str

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class InvitationInfo(BaseModel):
    """Read-only preview of an invitation — returned before the user accepts it."""
    school_name: str
    position_name: str | None
    email: str | None
    phone: str | None
    is_expired: bool
    is_accepted: bool


class ForgotPasswordRequest(BaseModel):
    login_type: LoginType
    identifier: str
    school_code: str | None = None  # required for ADMISSION_ID


class VerifyOtpRequest(BaseModel):
    login_type: LoginType
    identifier: str
    school_code: str | None = None
    otp: str  # 6-digit string

    @field_validator("otp")
    @classmethod
    def otp_format(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 6:
            raise ValueError("OTP must be exactly 6 digits")
        return v


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UpdateProfileRequest(BaseModel):
    phone: str | None = None
    address: str | None = None

    @field_validator("phone", mode="before")
    @classmethod
    def phone_strip(cls, v: str | None) -> str | None:
        return v.strip() if v else v
