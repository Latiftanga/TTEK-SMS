from __future__ import annotations
import uuid
from datetime import time

from pydantic import BaseModel

from app.models.attendance import DayOfWeek


class TimetableSlotUpsert(BaseModel):
    subject_id: uuid.UUID


class TimetableSlotRead(BaseModel):
    period_id: uuid.UUID
    subject_id: uuid.UUID
    subject_name: str
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
