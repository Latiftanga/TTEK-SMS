from __future__ import annotations
from decimal import Decimal
from typing import Literal, Annotated
from pydantic import BaseModel, Field
import uuid


class AbsentStudent(BaseModel):
    id: uuid.UUID
    name: str
    admission_number: str


class ClassSnapshot(BaseModel):
    id: uuid.UUID
    name: str
    student_count: int
    present_today: int
    absent_today: int
    attendance_marked_today: bool
    absent_students: list[AbsentStudent]


class TeacherDashboard(BaseModel):
    view: Literal["teacher"] = "teacher"
    greeting_name: str
    today_iso: str
    my_classes: list[ClassSnapshot]
    pending_score_assessments: int


class ClassAttendanceLine(BaseModel):
    class_id: uuid.UUID
    name: str
    total: int
    present: int
    pct: float


class AdminDashboard(BaseModel):
    view: Literal["admin"] = "admin"
    greeting_name: str
    school_name: str
    total_students: int
    today_present: int
    today_total: int
    attendance_pct: float
    term_collection_pct: float
    term_collected: Decimal
    term_expected: Decimal
    pending_approvals: int
    class_attendance: list[ClassAttendanceLine]


class ApproverDashboard(BaseModel):
    view: Literal["approver"] = "approver"
    greeting_name: str
    pending_approvals: int
    assessments_this_term: int


class FinanceDashboard(BaseModel):
    view: Literal["finance"] = "finance"
    greeting_name: str
    term_expected: Decimal
    term_collected: Decimal
    collection_pct: float
    payments_today: int
    outstanding_students: int


class HouseSnapshot(BaseModel):
    id: uuid.UUID
    name: str
    total_residents: int
    pending_exeats: int
    off_campus_count: int


class HousemasterDashboard(BaseModel):
    view: Literal["housemaster"] = "housemaster"
    greeting_name: str
    my_houses: list[HouseSnapshot] = []


DashboardData = Annotated[
    TeacherDashboard | ApproverDashboard | FinanceDashboard | AdminDashboard | HousemasterDashboard,
    Field(discriminator="view"),
]
