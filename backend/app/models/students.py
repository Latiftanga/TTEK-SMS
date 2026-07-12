"""
Group 5 — Student records, guardians, enrollment, and subject registration.

Tables in this group:
  student                  — the student's personal record (permanent, school-scoped)
  student_medical_record   — blood group, allergies, emergency medical notes
  guardian                 — parent or guardian contact
  student_guardian         — links students to their guardians (many-to-many)
  student_enrollment       — the moment a student was first enrolled (NEW or TRANSFER)
  student_class_assignment — which class a student belongs to for an academic year;
                             created by admin when assigning students to classes
  term_enrollment          — confirms the student physically arrived for a specific term;
                             created by the class teacher when the student reports
  subject_registration     — which subjects a student is taking in a given term enrollment
  transfer_request         — formal request to move a student to another school

CLASS MEMBERSHIP vs TERM ATTENDANCE
-------------------------------------
StudentClassAssignment = "Student X is in Form 2A for 2024/2025" (year-level, stable)
TermEnrollment         = "Student X physically reported for Term 2" (per-term confirmation)

These are deliberately separate. A student remains a class member even if they miss
a term. TermEnrollment gates report card generation and attendance marking but does
NOT define class membership.

TERM ENROLLMENT RULE
--------------------
A TermEnrollment is only created when the class teacher confirms the student
has physically arrived for the term. A StudentClassAssignment must already exist
for the student + academic year before a TermEnrollment can be created.
"""
from __future__ import annotations
import uuid
import enum
from datetime import date, datetime
from sqlalchemy import String, Boolean, Date, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin, UUIDPrimaryKey, SchoolScopedMixin
from app.models.staff import Gender


class EnrollmentType(str, enum.Enum):
    NEW = "NEW"
    TRANSFER = "TRANSFER"
    READMISSION = "READMISSION"


class TransferStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class Student(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    __tablename__ = "student"
    __table_args__ = (
        UniqueConstraint("school_id", "admission_number", name="uq_student_admission"),
    )

    admission_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(SAEnum(Gender, name="gender"), nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(50), nullable=True)
    religion: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hometown: Mapped[str | None] = mapped_column(String(100), nullable=True)
    residential_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    nhis_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ghana_card_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_boarding: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    orphan_status: Mapped[str] = mapped_column(String(20), default="NONE", nullable=False)
    disability: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    medical_record: Mapped[StudentMedicalRecord | None] = relationship(
        back_populates="student", uselist=False, cascade="all, delete-orphan"
    )
    guardians: Mapped[list[StudentGuardian]] = relationship(back_populates="student")
    enrollments: Mapped[list[StudentEnrollment]] = relationship(back_populates="student")
    class_assignments: Mapped[list[StudentClassAssignment]] = relationship(back_populates="student")
    term_enrollments: Mapped[list[TermEnrollment]] = relationship(back_populates="student")


class StudentMedicalRecord(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    __tablename__ = "student_medical_record"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    blood_group: Mapped[str | None] = mapped_column(String(10), nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    chronic_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    medications: Mapped[str | None] = mapped_column(Text, nullable=True)
    emergency_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    student: Mapped[Student] = relationship(back_populates="medical_record")


class Guardian(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    __tablename__ = "guardian"

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    student_links: Mapped[list[StudentGuardian]] = relationship(back_populates="guardian")


class StudentGuardian(Base, UUIDPrimaryKey, SchoolScopedMixin):
    __tablename__ = "student_guardian"
    __table_args__ = (
        UniqueConstraint("student_id", "guardian_id", name="uq_student_guardian"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    guardian_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guardian.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    student: Mapped[Student] = relationship(back_populates="guardians")
    guardian: Mapped[Guardian] = relationship(back_populates="student_links")


class StudentEnrollment(Base, UUIDPrimaryKey, SchoolScopedMixin):
    __tablename__ = "student_enrollment"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enrolled_at: Mapped[date] = mapped_column(Date, nullable=False)
    enrollment_type: Mapped[EnrollmentType] = mapped_column(
        SAEnum(EnrollmentType, name="enrollmenttype"), nullable=False
    )
    transfer_from_school: Mapped[str | None] = mapped_column(String(200), nullable=True)

    student: Mapped[Student] = relationship(back_populates="enrollments")


class StudentClassAssignment(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    __tablename__ = "student_class_assignment"
    __table_args__ = (
        UniqueConstraint("student_id", "academic_year_id", name="uq_student_class_year"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class.id"), nullable=False, index=True
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_year.id"), nullable=False
    )
    assigned_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    student: Mapped[Student] = relationship(back_populates="class_assignments")


class TermEnrollment(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    __tablename__ = "term_enrollment"
    __table_args__ = (
        UniqueConstraint("student_id", "academic_term_id", name="uq_term_enrollment"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_term.id"), nullable=False
    )
    enrolled_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Fee gate waiver — set only when AcademicTerm.block_owing_students was ON,
    # the student had an outstanding balance, and a caller with fees.manage
    # pushed the enrollment through anyway. See services/student_enrollment.py.
    fee_waived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fee_waived_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    fee_waiver_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    student: Mapped[Student] = relationship(back_populates="term_enrollments")
    subject_registrations: Mapped[list[SubjectRegistration]] = relationship(
        back_populates="term_enrollment", cascade="all, delete-orphan"
    )


class SubjectRegistration(Base, UUIDPrimaryKey, SchoolScopedMixin):
    __tablename__ = "subject_registration"
    __table_args__ = (
        UniqueConstraint("term_enrollment_id", "subject_id", name="uq_subject_registration"),
    )

    term_enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("term_enrollment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subject.id"), nullable=False
    )
    registration_type: Mapped[str] = mapped_column(String(20), nullable=False)  # CORE / ELECTIVE

    term_enrollment: Mapped[TermEnrollment] = relationship(back_populates="subject_registrations")


class TransferRequest(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    __tablename__ = "transfer_request"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requesting_school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school.id"), nullable=True
    )
    status: Mapped[TransferStatus] = mapped_column(
        SAEnum(TransferStatus, name="transferstatus"), default=TransferStatus.PENDING, nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
