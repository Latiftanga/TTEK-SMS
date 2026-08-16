from __future__ import annotations
from decimal import Decimal
from typing import Literal, Annotated
from pydantic import BaseModel, Field
import uuid


class RoleBadge(BaseModel):
    role: Literal["teacher", "subject_teacher", "housemaster", "approver", "finance"]
    label: str
    detail: str
    href: str


class DashboardExtras(BaseModel):
    # Present on every dashboard response regardless of which view ends up
    # primary — get_dashboard() picks exactly ONE full view by permission
    # seniority, but a staff member can genuinely hold several
    # responsibilities at once (e.g. Class Teacher + Housemaster).
    # is_class_teacher is computed independently of which view won, so the
    # sidebar nav's classTeacherOnly gating stays correct even when
    # 'teacher' isn't the primary view; other_roles is a compact "you
    # also..." strip covering every other responsibility the primary view
    # doesn't already surface.
    is_class_teacher: bool = False
    other_roles: list[RoleBadge] = []


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


class TeacherDashboard(DashboardExtras):
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


class AdminDashboard(DashboardExtras):
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


class ApproverDashboard(DashboardExtras):
    view: Literal["approver"] = "approver"
    greeting_name: str
    pending_approvals: int
    assessments_this_term: int


class FinanceDashboard(DashboardExtras):
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


class HousemasterDashboard(DashboardExtras):
    view: Literal["housemaster"] = "housemaster"
    greeting_name: str
    my_houses: list[HouseSnapshot] = []


DashboardData = Annotated[
    TeacherDashboard | ApproverDashboard | FinanceDashboard | AdminDashboard | HousemasterDashboard,
    Field(discriminator="view"),
]
