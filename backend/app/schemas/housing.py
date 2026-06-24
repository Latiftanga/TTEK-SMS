from __future__ import annotations
import uuid
from datetime import date, datetime
from pydantic import BaseModel, field_validator
from app.models.housing import ExeatStatus, ExeatType, HouseGender


class HouseCreate(BaseModel):
    name: str
    code: str
    gender: HouseGender
    capacity: int | None = None
    color: str | None = None

    @field_validator("name", "code")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be blank")
        return v.strip()


class HouseUpdate(BaseModel):
    name: str | None = None
    capacity: int | None = None
    color: str | None = None
    is_active: bool | None = None


class HouseRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    name: str
    code: str
    gender: HouseGender
    capacity: int | None
    color: str | None
    is_active: bool
    model_config = {"from_attributes": True}


class HouseDetail(HouseRead):
    rooms: list[RoomRead] = []


class RoomCreate(BaseModel):
    room_number: str
    capacity: int | None = None
    room_type: str = "DORMITORY"

    @field_validator("room_number")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be blank")
        return v.strip()


class RoomUpdate(BaseModel):
    room_number: str | None = None
    capacity: int | None = None
    room_type: str | None = None


class RoomRead(BaseModel):
    id: uuid.UUID
    house_id: uuid.UUID
    room_number: str
    capacity: int | None
    room_type: str
    model_config = {"from_attributes": True}


class HouseMasterAssign(BaseModel):
    staff_member_id: uuid.UUID
    academic_year_id: uuid.UUID


class HouseMasterRead(BaseModel):
    id: uuid.UUID
    house_id: uuid.UUID
    staff_member_id: uuid.UUID
    academic_year_id: uuid.UUID
    is_active: bool
    model_config = {"from_attributes": True}


class AssignmentCreate(BaseModel):
    student_id: uuid.UUID
    house_id: uuid.UUID
    room_id: uuid.UUID | None = None
    academic_year_id: uuid.UUID
    assigned_at: date


class AssignmentVacate(BaseModel):
    vacated_at: date


class AssignmentRead(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    house_id: uuid.UUID
    room_id: uuid.UUID | None
    academic_year_id: uuid.UUID
    assigned_at: date
    vacated_at: date | None
    model_config = {"from_attributes": True}


class RollCallCreate(BaseModel):
    house_id: uuid.UUID
    school_calendar_id: uuid.UUID
    total_expected: int
    total_present: int
    notes: str | None = None

    @field_validator("total_expected", "total_present")
    @classmethod
    def non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Count must be 0 or greater")
        return v


class RollCallRead(BaseModel):
    id: uuid.UUID
    house_id: uuid.UUID
    school_calendar_id: uuid.UUID
    recorded_by_id: uuid.UUID
    recorded_at: datetime
    total_expected: int
    total_present: int
    notes: str | None
    model_config = {"from_attributes": True}


class ExeatCreate(BaseModel):
    student_id: uuid.UUID
    exeat_type: ExeatType = ExeatType.EXTERNAL
    reason: str
    destination: str
    departure_date: date
    return_date: date

    @field_validator("return_date")
    @classmethod
    def return_after_departure(cls, v: date, info) -> date:
        dep = info.data.get("departure_date")
        if dep and v < dep:
            raise ValueError("return_date must be on or after departure_date")
        return v


class ExeatApprove(BaseModel):
    status: ExeatStatus

    @field_validator("status")
    @classmethod
    def approve_or_reject_only(cls, v: ExeatStatus) -> ExeatStatus:
        if v not in (ExeatStatus.APPROVED, ExeatStatus.REJECTED):
            raise ValueError("status must be APPROVED or REJECTED")
        return v


class ExeatReturn(BaseModel):
    actual_return_date: date


class ExeatRead(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str | None = None
    admission_number: str | None = None
    exeat_type: ExeatType
    reason: str
    destination: str
    departure_date: date
    return_date: date
    status: ExeatStatus
    approved_by_id: uuid.UUID | None
    actual_return_date: date | None
    created_at: datetime
    model_config = {"from_attributes": True}


class StudentInHouseRead(BaseModel):
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    admission_number: str
    gender: str | None = None
    room_number: str | None = None
    assigned_at: date


HouseDetail.model_rebuild()
