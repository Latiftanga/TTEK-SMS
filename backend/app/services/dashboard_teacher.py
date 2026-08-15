"""
Teacher dashboard view.

A staff member can be ClassTeacher for more than one class in the same year
(the DB only forbids two class teachers on the *same* class/year, nothing
stops one staff member holding several) — my_classes is therefore a list,
not a single snapshot.
"""
from __future__ import annotations
import uuid
from datetime import date
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class, ClassTeacher, SHSProgramme
from app.models.assessments import Assessment
from app.models.attendance import AttendanceRecord, AttendanceStatus, SchoolCalendar
from app.models.students import Student, StudentClassAssignment
from app.schemas.dashboard import AbsentStudent, ClassSnapshot, TeacherDashboard
from app.services.academic_year import get_current_term
from app.services.student_display import _class_display_name


def _class_label(cls: Class, prog_name: str | None) -> str:
    return _class_display_name(cls.level, cls.year_group, prog_name, cls.stream)


async def _class_snapshot(
    cls: Class, school_id: uuid.UUID, term: AcademicTerm, db: AsyncSession,
) -> ClassSnapshot:
    prog_name: str | None = None
    if cls.programme_id:
        prog = await db.get(SHSProgramme, cls.programme_id)
        prog_name = prog.name if prog else None

    student_count = await db.scalar(
        select(func.count(StudentClassAssignment.id)).where(
            StudentClassAssignment.class_id == cls.id,
            StudentClassAssignment.academic_year_id == term.academic_year_id,
            StudentClassAssignment.is_active.is_(True),
        )
    ) or 0

    today_cal: SchoolCalendar | None = await db.scalar(
        select(SchoolCalendar).where(
            SchoolCalendar.school_id == school_id,
            SchoolCalendar.date == date.today(),
        )
    )

    absent_students: list[AbsentStudent] = []
    present_count = 0
    marked_count = 0
    if today_cal:
        rows = await db.execute(
            select(
                AttendanceRecord.status,
                Student.id, Student.first_name,
                Student.last_name, Student.admission_number,
            )
            .join(Student, Student.id == AttendanceRecord.student_id)
            .join(
                StudentClassAssignment,
                StudentClassAssignment.student_id == AttendanceRecord.student_id,
            )
            .where(
                AttendanceRecord.school_calendar_id == today_cal.id,
                AttendanceRecord.period_id.is_(None),
                StudentClassAssignment.class_id == cls.id,
                StudentClassAssignment.academic_year_id == term.academic_year_id,
                StudentClassAssignment.is_active.is_(True),
            )
        )
        for row in rows:
            # Every status counts toward "marked today" — LATE/EXCUSED are neither
            # present nor absent, but their presence still means the roster was marked.
            marked_count += 1
            if row.status == AttendanceStatus.PRESENT:
                present_count += 1
            elif row.status == AttendanceStatus.ABSENT:
                absent_students.append(AbsentStudent(
                    id=row.id,
                    name=f"{row.first_name} {row.last_name}",
                    admission_number=row.admission_number,
                ))

    attendance_marked = bool(today_cal and marked_count > 0)
    return ClassSnapshot(
        id=cls.id,
        name=_class_label(cls, prog_name),
        student_count=student_count,
        present_today=present_count,
        absent_today=len(absent_students),
        attendance_marked_today=attendance_marked,
        absent_students=absent_students[:5],
    )


async def teacher_view(
    school_id: uuid.UUID,
    staff_id: uuid.UUID,
    greeting_name: str,
    db: AsyncSession,
) -> TeacherDashboard:
    today_iso = date.today().isoformat()
    term = await get_current_term(school_id, db)
    if not term:
        return TeacherDashboard(
            greeting_name=greeting_name, today_iso=today_iso,
            my_classes=[], pending_score_assessments=0,
        )

    cts = (await db.scalars(
        select(ClassTeacher).where(
            ClassTeacher.staff_member_id == staff_id,
            ClassTeacher.academic_year_id == term.academic_year_id,
            ClassTeacher.is_active.is_(True),
        )
    )).all()
    if not cts:
        return TeacherDashboard(
            greeting_name=greeting_name, today_iso=today_iso,
            my_classes=[], pending_score_assessments=0,
        )

    class_ids = [ct.class_id for ct in cts]
    classes = (await db.scalars(select(Class).where(Class.id.in_(class_ids)))).all()

    my_classes = [await _class_snapshot(cls, school_id, term, db) for cls in classes]
    my_classes.sort(key=lambda c: c.name)

    pending = await db.scalar(
        select(func.count(Assessment.id)).where(
            Assessment.class_id.in_(class_ids),
            Assessment.academic_term_id == term.id,
            Assessment.is_published.is_(False),
        )
    ) or 0

    return TeacherDashboard(
        greeting_name=greeting_name,
        today_iso=today_iso,
        my_classes=my_classes,
        pending_score_assessments=pending,
    )
