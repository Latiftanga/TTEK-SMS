"""CSV export of the student register."""
from __future__ import annotations
import csv
import io
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import Class, SHSProgramme
from app.models.students import Guardian, Student, StudentClassAssignment, StudentGuardian, TermEnrollment
from app.services.student import _class_display, _display_name


HEADERS = [
    "Admission No.", "Full Name", "Gender", "Date of Birth", "Nationality",
    "Religion", "Hometown", "Current Class", "Boarding", "NHIS No.",
    "Ghana Card No.", "Orphan Status", "Disability", "Guardian", "Guardian Phone",
    "Status",
]


async def export_students_csv(
    school_id: uuid.UUID,
    db: AsyncSession,
    *,
    active_only: bool = True,
    class_id: uuid.UUID | None = None,
    term_id: uuid.UUID | None = None,
    gender: str | None = None,
    level: str | None = None,
) -> bytes:
    q = select(Student).where(Student.school_id == school_id)
    if active_only:
        q = q.where(Student.is_active == True)  # noqa: E712
    if gender:
        q = q.where(Student.gender == gender)
    if class_id or level:
        q = q.join(StudentClassAssignment, StudentClassAssignment.student_id == Student.id).where(
            StudentClassAssignment.is_active == True,  # noqa: E712
        )
        if class_id:
            q = q.where(StudentClassAssignment.class_id == class_id)
        if level:
            q = q.join(Class, Class.id == StudentClassAssignment.class_id).where(Class.level == level)
    if term_id:
        q = q.join(TermEnrollment, TermEnrollment.student_id == Student.id).where(
            TermEnrollment.is_active == True,  # noqa: E712
            TermEnrollment.academic_term_id == term_id,
        )
    q = q.distinct().order_by(Student.last_name, Student.first_name)
    students = list(await db.scalars(q))

    # Class map
    sids = [s.id for s in students]
    class_map: dict[uuid.UUID, str] = {}
    if sids:
        rows = await db.execute(
            select(
                StudentClassAssignment.student_id,
                Class.level, Class.year_group, Class.stream,
                SHSProgramme.name.label("programme_name"),
            )
            .join(Class, Class.id == StudentClassAssignment.class_id)
            .outerjoin(SHSProgramme, SHSProgramme.id == Class.programme_id)
            .where(StudentClassAssignment.student_id.in_(sids), StudentClassAssignment.is_active == True)  # noqa: E712
        )
        for r in rows:
            if r.student_id not in class_map:
                class_map[r.student_id] = _class_display(r.level, r.year_group, r.programme_name, r.stream)

    # Primary guardian map
    guardian_map: dict[uuid.UUID, tuple[str, str]] = {}
    if sids:
        g_rows = await db.execute(
            select(StudentGuardian.student_id, Guardian.first_name, Guardian.last_name, Guardian.phone)
            .join(Guardian, Guardian.id == StudentGuardian.guardian_id)
            .where(StudentGuardian.student_id.in_(sids), StudentGuardian.is_primary == True)  # noqa: E712
        )
        for gr in g_rows:
            guardian_map[gr.student_id] = (
                f"{gr.first_name} {gr.last_name}",
                gr.phone,
            )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(HEADERS)
    for s in students:
        guardian_name, guardian_phone = guardian_map.get(s.id, ("", ""))
        writer.writerow([
            s.admission_number,
            _display_name(s.first_name, s.middle_name, s.last_name),
            s.gender.value if s.gender else "",
            str(s.date_of_birth) if s.date_of_birth else "",
            s.nationality or "",
            s.religion or "",
            s.hometown or "",
            class_map.get(s.id, ""),
            "Boarding" if s.is_boarding else "Day",
            s.nhis_number or "",
            s.ghana_card_number or "",
            s.orphan_status,
            s.disability or "",
            guardian_name,
            guardian_phone,
            "Active" if s.is_active else "Inactive",
        ])
    return buf.getvalue().encode("utf-8-sig")  # utf-8-sig adds BOM for Excel compatibility
