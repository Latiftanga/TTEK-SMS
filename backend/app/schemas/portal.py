from __future__ import annotations
import uuid
from pydantic import BaseModel


class PortalProfile(BaseModel):
    student_id: uuid.UUID
    admission_number: str
    display_name: str
    current_class_name: str | None
    school_name: str


class PortalTermEnrollmentRead(BaseModel):
    id: uuid.UUID
    academic_term_id: uuid.UUID
    term_name: str
    academic_year_name: str
    is_current: bool
    is_published: bool
