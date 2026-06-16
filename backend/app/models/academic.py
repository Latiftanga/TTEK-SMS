"""
Group 4 — Academic structure: years, terms, subjects, classes, and teacher assignments.

Tables in this group:
  academic_year     — e.g. "2024/2025"; one is marked is_current per school
  academic_term     — Term 1/2/3 within a year; one is marked is_current per school
  shs_programme     — GES programmes (General Science, Business, etc.); nullable school_id
  subject_catalogue — GES national subject list; nullable school_id (system-wide defaults)
  subject           — school's instance of a subject (may reference catalogue or be custom)
  class             — a class group (e.g. SHS 2 Science A); name is NEVER stored
  class_subject     — which subjects are taught in a class
  class_teacher     — which staff member is the form teacher per term
  subject_teacher   — which staff member teaches a subject in a class per term

CLASS NAMING INVARIANT
----------------------
The display name of a class is NEVER stored in the database.
It is always computed at query time from four fields:
    level + year_group + programme + stream
    e.g. "SHS 2" + 2023 + "General Science" + "A" → "SHS 2 General Science A (2023)"

This means renaming a programme or changing the stream automatically updates
all class names everywhere, with no migration needed.
"""
from __future__ import annotations
import uuid
import enum
from datetime import date
from sqlalchemy import String, Boolean, Integer, Date, ForeignKey, UniqueConstraint, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin, UUIDPrimaryKey, SchoolScopedMixin


class SubjectType(str, enum.Enum):
    CORE = "CORE"
    ELECTIVE = "ELECTIVE"


class SchoolLevel(str, enum.Enum):
    BASIC = "BASIC"
    SHS = "SHS"


class AcademicYear(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    __tablename__ = "academic_year"
    __table_args__ = (
        UniqueConstraint("school_id", "name", name="uq_academic_year_school_name"),
    )

    name: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    terms: Mapped[list[AcademicTerm]] = relationship(back_populates="academic_year")


class AcademicTerm(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    __tablename__ = "academic_term"
    __table_args__ = (
        UniqueConstraint("school_id", "academic_year_id", "term_number", name="uq_term_year_number"),
    )

    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_year.id", ondelete="CASCADE"), nullable=False, index=True
    )
    term_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    academic_year: Mapped[AcademicYear] = relationship(back_populates="terms")


class SHSProgramme(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "shs_programme"

    # nullable — GES standard programmes are system-wide
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school.id", ondelete="CASCADE"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SubjectCatalogue(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "subject_catalogue"

    # nullable — GES national subjects are system-wide
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school.id", ondelete="CASCADE"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_type: Mapped[SubjectType] = mapped_column(SAEnum(SubjectType, name="subjecttype"), nullable=False)
    level: Mapped[SchoolLevel] = mapped_column(SAEnum(SchoolLevel, name="schoollevel"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Subject(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    __tablename__ = "subject"

    catalogue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subject_catalogue.id"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Class(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    __tablename__ = "class"
    # Class name is NEVER stored — computed: level + year_group + programme + stream

    level: Mapped[str] = mapped_column(String(20), nullable=False)
    year_group: Mapped[int] = mapped_column(Integer, nullable=False)
    programme_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shs_programme.id"), nullable=True
    )
    stream: Mapped[str | None] = mapped_column(String(10), nullable=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    class_subjects: Mapped[list[ClassSubject]] = relationship(back_populates="class_", cascade="all, delete-orphan")
    class_teachers: Mapped[list[ClassTeacher]] = relationship(back_populates="class_")


class ClassSubject(Base, UUIDPrimaryKey, SchoolScopedMixin):
    __tablename__ = "class_subject"
    __table_args__ = (
        UniqueConstraint("class_id", "subject_id", name="uq_class_subject"),
    )

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subject.id", ondelete="CASCADE"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    class_: Mapped[Class] = relationship(back_populates="class_subjects")


class ClassTeacher(Base, UUIDPrimaryKey, SchoolScopedMixin):
    __tablename__ = "class_teacher"
    __table_args__ = (
        UniqueConstraint("class_id", "academic_term_id", name="uq_class_teacher_term"),
    )

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class.id", ondelete="CASCADE"), nullable=False, index=True
    )
    staff_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_member.id", ondelete="CASCADE"), nullable=False
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_term.id", ondelete="CASCADE"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    class_: Mapped[Class] = relationship(back_populates="class_teachers")


class SubjectTeacher(Base, UUIDPrimaryKey, SchoolScopedMixin):
    __tablename__ = "subject_teacher"
    __table_args__ = (
        UniqueConstraint("class_id", "subject_id", "academic_term_id", name="uq_subject_teacher_term"),
    )

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subject.id", ondelete="CASCADE"), nullable=False
    )
    staff_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_member.id", ondelete="CASCADE"), nullable=False
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_term.id", ondelete="CASCADE"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
