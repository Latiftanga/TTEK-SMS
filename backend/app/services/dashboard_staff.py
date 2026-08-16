"""
Composed dashboard view for anyone who isn't admin/finance/approver —
replaces the old separate teacher_view()/housemaster_view(). A staff member
can hold any combination of Class Teacher, Subject Teacher, and House Master
at once (nothing in the data model limits it to one), so this builds
my_classes/my_subjects/my_houses independently from the caller's real
assignment rows rather than picking a single "winning" role — a class
teacher who's also a housemaster gets both sections, not one.
"""
from __future__ import annotations
import uuid
from datetime import date
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class, ClassTeacher, SHSProgramme, Subject, SubjectTeacher
from app.models.assessments import Assessment
from app.models.attendance import AttendanceRecord, AttendanceStatus, SchoolCalendar
from app.models.housing import Exeat, ExeatStatus, ExeatType, House, HouseMaster, StudentHouseAssignment
from app.models.students import Student, StudentClassAssignment
from app.schemas.dashboard import AbsentStudent, ClassSnapshot, HouseSnapshot, StaffDashboard, SubjectSnapshot
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


async def _my_classes(
    school_id: uuid.UUID, staff_id: uuid.UUID, term: AcademicTerm, db: AsyncSession,
) -> tuple[list[ClassSnapshot], int, set[uuid.UUID]]:
    """Returns (snapshots, pending_score_assessments, class_ids) — class_ids
    is handed to _my_subjects() so it can exclude subjects taught within the
    caller's own homeroom classes (already counted in pending_score_assessments,
    which sums every assessment in the class regardless of subject)."""
    cts = (await db.scalars(
        select(ClassTeacher).where(
            ClassTeacher.staff_member_id == staff_id,
            ClassTeacher.academic_year_id == term.academic_year_id,
            ClassTeacher.is_active.is_(True),
        )
    )).all()
    if not cts:
        return [], 0, set()

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

    return my_classes, pending, set(class_ids)


async def _my_subjects(
    staff_id: uuid.UUID, term: AcademicTerm, own_class_ids: set[uuid.UUID], db: AsyncSession,
) -> list[SubjectSnapshot]:
    """(class, subject) pairs the caller is the active SubjectTeacher for
    this year, excluding any pair on a class they already class-teach (that
    class's assessments are already counted in my_classes' own
    pending_score_assessments — including it here too would double-count)."""
    rows = await db.execute(
        select(SubjectTeacher.class_id, SubjectTeacher.subject_id).where(
            SubjectTeacher.staff_member_id == staff_id,
            SubjectTeacher.academic_year_id == term.academic_year_id,
            SubjectTeacher.is_active.is_(True),
        )
    )
    pairs = [(r.class_id, r.subject_id) for r in rows if r.class_id not in own_class_ids]
    if not pairs:
        return []

    class_ids = {p[0] for p in pairs}
    subject_ids = {p[1] for p in pairs}
    classes = {c.id: c for c in (await db.scalars(select(Class).where(Class.id.in_(class_ids)))).all()}
    subjects = {s.id: s for s in (await db.scalars(select(Subject).where(Subject.id.in_(subject_ids)))).all()}
    prog_ids = {c.programme_id for c in classes.values() if c.programme_id}
    prog_names = {
        p.id: p.name for p in (await db.scalars(select(SHSProgramme).where(SHSProgramme.id.in_(prog_ids)))).all()
    } if prog_ids else {}

    snapshots: list[SubjectSnapshot] = []
    for class_id, subject_id in pairs:
        cls = classes.get(class_id)
        subj = subjects.get(subject_id)
        if not cls or not subj:
            continue
        pending = await db.scalar(
            select(func.count(Assessment.id)).where(
                Assessment.class_id == class_id,
                Assessment.subject_id == subject_id,
                Assessment.academic_term_id == term.id,
                Assessment.is_published.is_(False),
            )
        ) or 0
        snapshots.append(SubjectSnapshot(
            class_id=class_id,
            class_name=_class_label(cls, prog_names.get(cls.programme_id)),
            subject_id=subject_id,
            subject_name=subj.name,
            pending_score_assessments=pending,
        ))

    snapshots.sort(key=lambda s: (s.class_name, s.subject_name))
    return snapshots


async def _house_snapshot(house: House, school_id: uuid.UUID, db: AsyncSession) -> HouseSnapshot:
    total_residents = await db.scalar(
        select(func.count(StudentHouseAssignment.id)).where(
            StudentHouseAssignment.house_id == house.id,
            StudentHouseAssignment.school_id == school_id,
            StudentHouseAssignment.vacated_at.is_(None),
        )
    ) or 0

    active_students = (
        select(StudentHouseAssignment.student_id).where(
            StudentHouseAssignment.house_id == house.id,
            StudentHouseAssignment.school_id == school_id,
            StudentHouseAssignment.vacated_at.is_(None),
        )
    )
    pending_exeats = await db.scalar(
        select(func.count(Exeat.id)).where(
            Exeat.school_id == school_id,
            Exeat.status == ExeatStatus.PENDING,
            Exeat.student_id.in_(active_students),
        )
    ) or 0
    off_campus = await db.scalar(
        select(func.count(Exeat.id)).where(
            Exeat.school_id == school_id,
            Exeat.status == ExeatStatus.APPROVED,
            Exeat.exeat_type == ExeatType.EXTERNAL,
            Exeat.student_id.in_(active_students),
        )
    ) or 0

    return HouseSnapshot(
        id=house.id,
        name=house.name,
        capacity=house.capacity,
        total_residents=total_residents,
        pending_exeats=pending_exeats,
        off_campus_count=off_campus,
    )


async def _my_houses(staff_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession) -> list[HouseSnapshot]:
    hms = (await db.scalars(
        select(HouseMaster).where(
            HouseMaster.staff_member_id == staff_id,
            HouseMaster.school_id == school_id,
            HouseMaster.is_active.is_(True),
        )
    )).all()
    if not hms:
        return []

    house_ids = [hm.house_id for hm in hms]
    houses = (await db.scalars(select(House).where(House.id.in_(house_ids)))).all()

    my_houses = [await _house_snapshot(house, school_id, db) for house in houses]
    my_houses.sort(key=lambda h: h.name)
    return my_houses


async def staff_view(
    school_id: uuid.UUID,
    staff_id: uuid.UUID,
    greeting_name: str,
    db: AsyncSession,
) -> StaffDashboard:
    today_iso = date.today().isoformat()
    term = await get_current_term(school_id, db)

    my_classes: list[ClassSnapshot] = []
    pending = 0
    own_class_ids: set[uuid.UUID] = set()
    my_subjects: list[SubjectSnapshot] = []
    if term:
        my_classes, pending, own_class_ids = await _my_classes(school_id, staff_id, term, db)
        my_subjects = await _my_subjects(staff_id, term, own_class_ids, db)

    my_houses = await _my_houses(staff_id, school_id, db)

    return StaffDashboard(
        greeting_name=greeting_name,
        today_iso=today_iso,
        my_classes=my_classes,
        pending_score_assessments=pending,
        my_subjects=my_subjects,
        my_houses=my_houses,
    )
