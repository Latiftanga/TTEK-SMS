from __future__ import annotations
from decimal import Decimal
from typing import Literal, Annotated
from pydantic import BaseModel, Field
import uuid

from app.schemas.timetable import ScheduleEntry


class RoleBadge(BaseModel):
    role: Literal["teacher", "subject_teacher", "housemaster", "approver", "finance"]
    label: str
    detail: str
    href: str


class DashboardExtras(BaseModel):
    # Present on every dashboard response regardless of which view ends up
    # primary — get_dashboard() picks exactly ONE full view by permission
    # seniority, but a staff member can genuinely hold several
    # responsibilities at once (e.g. Class Teacher + Housemaster). These
    # three booleans are computed independently of which view won, so the
    # sidebar nav's teachingOnly/classTeacherOnly/housemasterOnly gating
    # stays correct no matter which view is primary — the nav no longer
    # depends on the `view` string at all for these three roles. other_roles
    # is a compact "you also..." strip, only populated for the admin/
    # finance/approver primaries (the `staff` view already shows all three
    # directly as full sections, so a badge there would just repeat itself).
    is_class_teacher: bool = False
    is_subject_teacher: bool = False
    is_housemaster: bool = False
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


class SubjectSnapshot(BaseModel):
    class_id: uuid.UUID
    class_name: str
    subject_id: uuid.UUID
    subject_name: str
    pending_score_assessments: int


class ClassAttendanceLine(BaseModel):
    class_id: uuid.UUID
    name: str
    total: int
    present: int
    pct: float
    marked: bool


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
    capacity: int | None
    total_residents: int
    pending_exeats: int
    off_campus_count: int


class StaffDashboard(DashboardExtras):
    """The composed dashboard for anyone who isn't admin/finance/approver —
    replaces the old separate TeacherDashboard/HousemasterDashboard. Each
    section is populated independently from the caller's real assignment
    rows (ClassTeacher/SubjectTeacher/HouseMaster), not from a single
    "winning" role — a class teacher who's also a housemaster sees both
    my_classes and my_houses at once. See services/dashboard_staff.py."""
    view: Literal["staff"] = "staff"
    greeting_name: str
    today_iso: str
    my_classes: list[ClassSnapshot] = []
    pending_score_assessments: int = 0
    my_subjects: list[SubjectSnapshot] = []
    my_houses: list[HouseSnapshot] = []
    # "What do I teach tomorrow?" — tomorrow_schedule is always [] when
    # tomorrow_is_school_day is False (a real holiday/weekend), even if the
    # caller's recurring weekly timetable would otherwise have entries.
    tomorrow_schedule: list[ScheduleEntry] = []
    tomorrow_is_school_day: bool = True


DashboardData = Annotated[
    ApproverDashboard | FinanceDashboard | AdminDashboard | StaffDashboard,
    Field(discriminator="view"),
]
