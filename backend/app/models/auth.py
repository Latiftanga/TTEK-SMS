"""
Group 2 — Identity, authentication, and authorization models.

Tables in this group:
  user              — every person who can log into the system
  user_session      — active refresh token records (one per device/login)
  user_invitation   — pending invitations to join a school
  staff_position    — role templates (e.g. HEAD, BURSAR); also per-school customs
  position_permission — default permissions assigned to a position template
  staff_permission  — personal permission overrides for a specific staff member
  audit_log         — immutable record of every write action

PERMISSION RESOLUTION (3 layers — see core/permissions.py for full explanation)
  Layer 1 (highest): staff_permission rows override everything
  Layer 2:           position_permission rows from the staff member's position
  Layer 3 (default): deny if no rule matches
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class LoginType(str, enum.Enum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    ADMISSION_ID = "ADMISSION_ID"


class User(Base, UUIDPrimaryKey, TimestampMixin):
    """
    A person who can authenticate with the system.

    THREE LOGIN TYPES
    -----------------
    EMAIL        Staff / admins who log in with email + password.
                 Unique globally — one email can only belong to one user.

    PHONE        Staff or parents who log in with phone + password.
                 Unique globally — one phone can only belong to one user.

    ADMISSION_ID Students who log in with their admission number + password.
                 Admission numbers are unique per school, not globally.
                 school_code must be sent with the login request to scope the lookup.

    SUPERADMIN
    ----------
    The platform superadmin has is_superadmin=True and school_id=None.
    There is only one superadmin in the system (seeded via create_superadmin.py).
    Superadmin bypasses all permission checks.

    LINK TO PEOPLE
    --------------
    staff_member_id → links the user account to a StaffMember record (staff/admin)
    student_id      → links the user account to a Student record (student login)
    Both are nullable; a user can be linked to at most one of these — never both.

    INVARIANTS (enforced by DB check constraints)
    ---------------------------------------------
    - admission_id is non-null if and only if login_type = ADMISSION_ID
    - A user cannot be both a staff member and a student simultaneously
    """
    __tablename__ = "user"
    __table_args__ = (
        UniqueConstraint("school_id", "admission_id", name="uq_user_school_admission"),
        CheckConstraint(
            "(login_type = 'ADMISSION_ID' AND admission_id IS NOT NULL)"
            " OR (login_type != 'ADMISSION_ID' AND admission_id IS NULL)",
            name="ck_user_admission_id_matches_login_type",
        ),
        CheckConstraint(
            "NOT (staff_member_id IS NOT NULL AND student_id IS NOT NULL)",
            name="ck_user_single_identity",
        ),
    )

    # school_id is nullable — superadmin has no school
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school.id", ondelete="CASCADE"), nullable=True, index=True
    )
    login_type: Mapped[LoginType] = mapped_column(SAEnum(LoginType, name="logintype"), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)
    admission_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    staff_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_member.id", ondelete="SET NULL"), nullable=True
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="SET NULL"), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sessions: Mapped[list[UserSession]] = relationship(back_populates="user", cascade="all, delete-orphan")
    invitations_sent: Mapped[list[UserInvitation]] = relationship(
        back_populates="invited_by", foreign_keys="UserInvitation.invited_by_id"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="user")


class UserSession(Base, UUIDPrimaryKey):
    """
    A single authenticated device session.

    One row is created per successful login.  The refresh_token_hash uniquely
    identifies the session.  On logout or token rotation the row is revoked
    (revoked_at set) rather than deleted, preserving audit history.
    Expired sessions are cleaned up by a background job.
    """
    __tablename__ = "user_session"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school.id", ondelete="CASCADE"), nullable=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    device_info: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class UserInvitation(Base, UUIDPrimaryKey, TimestampMixin):
    """
    A one-time invitation token sent to a prospective staff member.

    The invitee follows a link containing the raw token, which is verified
    against token_hash.  On redemption, accepted_at is set and a User row
    is created.  Expired or already-accepted invitations are rejected.
    """
    __tablename__ = "user_invitation"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    position_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_position.id"), nullable=True
    )
    # When inviting an existing StaffMember, set this so accept_invitation can
    # link the resulting User back to their professional profile automatically.
    staff_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_member.id", ondelete="SET NULL"), nullable=True
    )
    token_hash: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invited_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )

    invited_by: Mapped[User] = relationship(back_populates="invitations_sent", foreign_keys=[invited_by_id])


class StaffPosition(Base, UUIDPrimaryKey, TimestampMixin):
    """
    A named role that determines a staff member's default permissions.

    System-wide template positions (is_template=True) have school_id=NULL and
    are seeded by seed_reference_data.py.  Schools may create their own custom
    positions (is_template=False, school_id set) that inherit from no template.

    The 6 seeded templates are: HEAD, DEPUTY, TEACHER, BURSAR, HOUSEMASTER, SECRETARY.
    """
    __tablename__ = "staff_position"

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    permissions: Mapped[list[PositionPermission]] = relationship(
        back_populates="position", cascade="all, delete-orphan"
    )


class PositionPermission(Base, UUIDPrimaryKey):
    """
    Default module/action permission granted to all holders of a StaffPosition.

    These are the Layer 2 defaults in the 3-layer resolution.  A StaffPermission
    row for the same (staff_member, module, action) always takes precedence.
    """
    __tablename__ = "position_permission"
    __table_args__ = (
        UniqueConstraint("position_id", "module", "action", name="uq_position_permission"),
    )

    position_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_position.id", ondelete="CASCADE"), nullable=False, index=True
    )
    module: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    position: Mapped[StaffPosition] = relationship(back_populates="permissions")


class StaffPermission(Base, UUIDPrimaryKey, TimestampMixin):
    """
    Personal permission override for a specific staff member.

    Layer 1 in the 3-layer resolution — always beats PositionPermission.
    Use sparingly: prefer assigning the correct position over adding personal overrides.
    Call core.permissions.invalidate_permissions(staff_member_id) after any change.
    """
    __tablename__ = "staff_permission"
    __table_args__ = (
        UniqueConstraint("staff_member_id", "module", "action", name="uq_staff_permission"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school.id", ondelete="CASCADE"), nullable=False, index=True
    )
    staff_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_member.id", ondelete="CASCADE"), nullable=False, index=True
    )
    module: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    is_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)


class AuditLog(Base, UUIDPrimaryKey):
    """
    Immutable record of every write action performed in the system.

    Never deleted or updated — append-only.  user_id and school_id use
    SET NULL on delete so log rows survive user/school removal.
    old_values and new_values hold a JSON snapshot of changed fields.
    """
    __tablename__ = "audit_log"

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    old_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User | None] = relationship(back_populates="audit_logs")
