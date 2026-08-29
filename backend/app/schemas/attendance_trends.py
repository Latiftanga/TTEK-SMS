from datetime import date as _date

from pydantic import BaseModel


class AttendanceTrendPoint(BaseModel):
    date: _date
    present: int
    total: int
    rate: float  # 0.0–100.0
