from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, field_validator

from app.models.academic import SchoolLevel, SubjectType


class AcademicYearCreate(BaseModel):
    name: str  # "2024/2025"
    start_date: date
    end_date: date


class AcademicYearUpdate(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class TermRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    academic_year_id: uuid.UUID
    term_number: int
    name: str
    start_date: date
    end_date: date
    is_current: bool
    block_owing_students: bool
    block_owing_students_set_by: uuid.UUID | None = None
    block_owing_students_set_at: datetime | None = None

    model_config = {"from_attributes": True}


class AcademicYearRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    name: str
    start_date: date
    end_date: date
    is_current: bool
    terms: list[TermRead] = []

    model_config = {"from_attributes": True}


class AcademicTermCreate(BaseModel):
    term_number: int  # 1, 2, or 3
    name: str         # "First Term", "Second Term", "Third Term"
    start_date: date
    end_date: date

    @field_validator("term_number")
    @classmethod
    def valid_term_number(cls, v: int) -> int:
        if v not in (1, 2, 3):
            raise ValueError("term_number must be 1, 2, or 3")
        return v


class AcademicTermUpdate(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    block_owing_students: bool | None = None


class ProgrammeRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID | None   # None = system-wide GES programme
    code: str
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


class ProgrammeCreate(BaseModel):
    code: str
    name: str


class ProgrammeUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    is_active: bool | None = None


class CatalogueRead(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    subject_type: SubjectType
    level: SchoolLevel
    is_active: bool

    model_config = {"from_attributes": True}


class SubjectCreate(BaseModel):
    catalogue_id: uuid.UUID | None = None   # link to national catalogue or None for custom
    code: str
    name: str


class SubjectUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    is_active: bool | None = None


class SubjectRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    catalogue_id: uuid.UUID | None
    code: str
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


class ClassCreate(BaseModel):
    level: str          # "SHS 1", "SHS 2", "JHS 1", "Primary 6" etc.
    year_group: int     # 1, 2, 3 within the level
    programme_id: uuid.UUID | None = None
    stream: str | None = None   # "A", "B", "Gold", "Blue" etc.
    capacity: int | None = None


class ClassUpdate(BaseModel):
    stream: str | None = None
    capacity: int | None = None
    is_active: bool | None = None
    programme_id: uuid.UUID | None = None  # None = leave unchanged


class ClassRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    level: str
    year_group: int
    programme_id: uuid.UUID | None
    programme_name: str | None    # denormalized for display, not stored in DB
    stream: str | None
    capacity: int | None
    is_active: bool
    display_name: str             # computed: never stored, assembled on read


class ClassSubjectAssign(BaseModel):
    subject_ids: list[uuid.UUID]


class ClassSubjectRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID
    is_active: bool

    model_config = {"from_attributes": True}


class ClassTeacherAssign(BaseModel):
    staff_member_id: uuid.UUID
    academic_year_id: uuid.UUID


class ClassTeacherRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    class_id: uuid.UUID
    staff_member_id: uuid.UUID
    academic_year_id: uuid.UUID
    is_active: bool

    model_config = {"from_attributes": True}


class SubjectTeacherAssign(BaseModel):
    subject_id: uuid.UUID
    staff_member_id: uuid.UUID
    academic_term_id: uuid.UUID


class SubjectTeacherRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID
    staff_member_id: uuid.UUID
    academic_term_id: uuid.UUID
    is_active: bool

    model_config = {"from_attributes": True}
