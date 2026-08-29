import uuid

from pydantic import BaseModel

from app.models.attendance import AttendanceRiskTier


class AtRiskStudentRead(BaseModel):
    student_id: uuid.UUID
    name: str
    class_id: uuid.UUID | None
    class_name: str | None
    present: int
    total: int
    rate: float  # 0.0–100.0
    tier: AttendanceRiskTier
