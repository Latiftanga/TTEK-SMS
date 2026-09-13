from __future__ import annotations
import uuid
from datetime import time

from pydantic import BaseModel

from app.models.attendance import DayOfWeek


class TimetableSlotUpsert(BaseModel):
    subject_id: uuid.UUID
    # Omitted (None) means "keep whatever SubjectTeacher is already
    # assigned" — the bulk CSV import path and any other caller that never
    # sends a teacher relies on this. If omitted AND no active SubjectTeacher
    # exists yet for (class, subject, year), the slot upsert still 422s.
    staff_member_id: uuid.UUID | None = None


class TimetableSlotRead(BaseModel):
    period_id: uuid.UUID
    subject_id: uuid.UUID
    subject_name: str
    staff_member_id: uuid.UUID | None
    teacher_name: str | None


class ScheduleEntry(BaseModel):
    """One entry in a teacher's own weekly schedule — see
    services/timetable.py::get_my_schedule(). Powers both the full "My
    Timetable" page and the dashboard's "tomorrow" card (which filters this
    same list to tomorrow's weekday)."""
    day_of_week: DayOfWeek
    start_time: time
    end_time: time
    class_id: uuid.UUID
    class_name: str
    subject_id: uuid.UUID
    subject_name: str
