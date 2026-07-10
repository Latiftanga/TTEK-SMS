"""
Student CRUD and medical record upsert.

Guardian add/update/remove live in student_guardian.py.
Enrollment (initial + term) and transfer logic live in student_enrollment.py.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import Class, ClassTeacher, SHSProgramme, SubjectTeacher
from app.models.auth import User
from app.models.housing import HouseMaster, StudentHouseAssignment
from app.models.students import (
    Guardian,
    Student,
    StudentClassAssignment,
    StudentGuardian,
    StudentMedicalRecord,
    TermEnrollment,
)
from app.schemas.students import (
    MedicalRecordRead,
    MedicalRecordUpsert,
    StudentCreate,
    StudentDetail,
    StudentGuardianRead,
    StudentSummary,
    StudentUpdate,
)


def _display_name(first: str, middle: str | None, last: str) -> str:
    parts = [first]
    if middle:
        parts.append(middle)
    parts.append(last)
    return " ".join(parts)


def _class_display(level: str, year_group: int, programme: str | None, stream: str | None) -> str:
    parts = [level, str(year_group)]
    if programme:
        parts.append(programme)
    if stream:
        parts.append(stream)
    return " ".join(parts)


def _to_summary(
    s: Student,
    class_info: tuple[str, int, str | None, str | None, uuid.UUID] | None = None,
) -> StudentSummary:
    current_class_name = None
    current_class_id = None
    if class_info:
        level, year_group, programme, stream, cls_id = class_info
        current_class_name = _class_display(level, year_group, programme, stream)
        current_class_id = cls_id
    return StudentSummary(
        id=s.id,
        school_id=s.school_id,
        admission_number=s.admission_number,
        first_name=s.first_name,
        middle_name=s.middle_name,
        last_name=s.last_name,
        display_name=_display_name(s.first_name, s.middle_name, s.last_name),
        gender=s.gender,
        is_active=s.is_active,
        is_boarding=s.is_boarding,
        current_class_name=current_class_name,
        current_class_id=current_class_id,
    )


def _to_guardian_read(sg: StudentGuardian) -> StudentGuardianRead:
    g = sg.guardian
    return StudentGuardianRead(
        guardian_id=sg.guardian_id,
        first_name=g.first_name,
        last_name=g.last_name,
        phone=g.phone,
        email=g.email,
        address=g.address,
        occupation=g.occupation,
        relation_type=sg.relation_type,
        is_primary=sg.is_primary,
    )


def _to_detail(s: Student, has_portal_access: bool = False) -> StudentDetail:
    return StudentDetail(
        **_to_summary(s).model_dump(),
        date_of_birth=s.date_of_birth,
        nationality=s.nationality,
        religion=s.religion,
        hometown=s.hometown,
        residential_address=s.residential_address,
        nhis_number=s.nhis_number,
        ghana_card_number=s.ghana_card_number,
        orphan_status=s.orphan_status,
        disability=s.disability,
        photo_path=s.photo_path,
        has_portal_access=has_portal_access,
        medical_record=MedicalRecordRead.model_validate(s.medical_record) if s.medical_record else None,
        guardians=[_to_guardian_read(sg) for sg in s.guardians],
    )


async def _portal_access(student_id: uuid.UUID, db: AsyncSession) -> bool:
    return await db.scalar(
        select(User.id).where(User.student_id == student_id, User.is_active.is_(True))
    ) is not None


async def create_student(
    req: StudentCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> StudentDetail:
    student = Student(
        school_id=school_id,
        admission_number=req.admission_number.strip(),
        first_name=req.first_name.strip(),
        middle_name=req.middle_name.strip() if req.middle_name else None,
        last_name=req.last_name.strip(),
        date_of_birth=req.date_of_birth,
        gender=req.gender,
        nationality=req.nationality,
        religion=req.religion,
        hometown=req.hometown,
        residential_address=req.residential_address,
        nhis_number=req.nhis_number,
        ghana_card_number=req.ghana_card_number,
        is_boarding=req.is_boarding,
        orphan_status=req.orphan_status,
        disability=req.disability,
        is_active=True,
    )
    db.add(student)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Admission number '{req.admission_number}' already exists at this school.",
        )
    await db.refresh(student, attribute_names=["medical_record", "guardians"])
    return _to_detail(student)


def _active_class_assignment_subquery():
    """Most-recent active StudentClassAssignment per student.

    A promoted (not graduated/withdrawn) student is never deactivated from their
    prior year's assignment, so 2+ is_active=True rows can coexist for one student.
    DISTINCT ON collapses that to exactly one row per student, keeping this join
    provably 1:1 wherever it's used (list_students' count/sort, and here).
    """
    return (
        select(StudentClassAssignment.student_id, StudentClassAssignment.class_id)
        .where(StudentClassAssignment.is_active == True)  # noqa: E712
        .distinct(StudentClassAssignment.student_id)
        .order_by(StudentClassAssignment.student_id, StudentClassAssignment.created_at.desc())
        .subquery()
    )


async def _get_class_map(
    student_ids: list[uuid.UUID],
    db: AsyncSession,
) -> dict[uuid.UUID, tuple[str, int, str | None, str | None, uuid.UUID]]:
    if not student_ids:
        return {}
    active_sca = _active_class_assignment_subquery()
    rows = await db.execute(
        select(
            active_sca.c.student_id,
            Class.level,
            Class.year_group,
            Class.stream,
            SHSProgramme.name.label("programme_name"),
            Class.id.label("class_id"),
        )
        .join(Class, Class.id == active_sca.c.class_id)
        .outerjoin(SHSProgramme, SHSProgramme.id == Class.programme_id)
        .where(active_sca.c.student_id.in_(student_ids))
    )
    return {
        r.student_id: (r.level, r.year_group, r.programme_name, r.stream, r.class_id)
        for r in rows
    }


# Pedagogical order — Class.level is a free-text column, not a DB-enforced enum,
# so plain alphabetical ORDER BY would put "Basic" before "Creche".
_CLASS_LEVEL_ORDER = ["Creche", "Nursery", "KG", "Basic", "SHS"]


async def list_students(
    school_id: uuid.UUID,
    db: AsyncSession,
    *,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 50,
    search: str | None = None,
    class_id: uuid.UUID | None = None,
    term_id: uuid.UUID | None = None,
    gender: str | None = None,
    level: str | None = None,
    year_group: int | None = None,
    staff_member_id: uuid.UUID | None = None,
    sort_by: str = "name",
    sort_dir: str = "asc",
) -> tuple[list[StudentSummary], int]:
    q = select(Student).where(Student.school_id == school_id)

    if staff_member_id is not None:
        # Restrict to students the staff member is directly responsible for:
        # classes they teach (ClassTeacher) or subjects they deliver (SubjectTeacher),
        # plus any house they manage (HouseMaster).
        taught_class_ids = (
            select(ClassTeacher.class_id).where(
                ClassTeacher.staff_member_id == staff_member_id,
                ClassTeacher.is_active == True,  # noqa: E712
            )
        ).union(
            select(SubjectTeacher.class_id).where(
                SubjectTeacher.staff_member_id == staff_member_id,
                SubjectTeacher.is_active == True,  # noqa: E712
            )
        )
        in_taught_class = select(StudentClassAssignment.student_id).where(
            StudentClassAssignment.class_id.in_(taught_class_ids),
            StudentClassAssignment.is_active == True,  # noqa: E712
        )
        managed_house_ids = select(HouseMaster.house_id).where(
            HouseMaster.staff_member_id == staff_member_id,
            HouseMaster.is_active == True,  # noqa: E712
        )
        in_managed_house = select(StudentHouseAssignment.student_id).where(
            StudentHouseAssignment.house_id.in_(managed_house_ids),
            StudentHouseAssignment.vacated_at.is_(None),
        )
        q = q.where(or_(Student.id.in_(in_taught_class), Student.id.in_(in_managed_house)))

    if active_only:
        q = q.where(Student.is_active == True)  # noqa: E712
    if gender:
        q = q.where(Student.gender == gender)

    # Class filter/sort share one dedup'd active-assignment join so a student with
    # 2+ active StudentClassAssignment rows (promoted, not graduated) can't fan out
    # the result — see _active_class_assignment_subquery().
    class_filtered = bool(class_id or level or year_group)
    class_sorted = sort_by == "class"
    active_sca = _active_class_assignment_subquery()
    if class_filtered:
        q = q.join(active_sca, active_sca.c.student_id == Student.id)
        if class_id:
            q = q.where(active_sca.c.class_id == class_id)
        if level or year_group or class_sorted:
            q = q.join(Class, Class.id == active_sca.c.class_id)
            if level:
                q = q.where(Class.level == level)
            if year_group:
                q = q.where(Class.year_group == year_group)
    elif class_sorted:
        # No class filter active — outer join so students with no current class
        # assignment still appear in an otherwise-unfiltered list.
        q = q.outerjoin(active_sca, active_sca.c.student_id == Student.id)
        q = q.outerjoin(Class, Class.id == active_sca.c.class_id)

    if term_id:
        q = q.join(TermEnrollment, TermEnrollment.student_id == Student.id).where(
            TermEnrollment.is_active == True,  # noqa: E712
            TermEnrollment.academic_term_id == term_id,
        )
    if search:
        s = f"%{search}%"
        q = q.where(or_(
            Student.first_name.ilike(s),
            Student.last_name.ilike(s),
            Student.admission_number.ilike(s),
        ))

    total = await db.scalar(select(func.count()).select_from(q.subquery()))

    desc = sort_dir == "desc"
    if sort_by == "admission":
        order_cols = [Student.admission_number.desc() if desc else Student.admission_number.asc()]
    elif sort_by == "class":
        level_rank = case(
            {lvl: i for i, lvl in enumerate(_CLASS_LEVEL_ORDER)},
            value=Class.level,
            else_=len(_CLASS_LEVEL_ORDER),
        )
        order_cols = [
            c.desc().nulls_last() if desc else c.asc().nulls_last()
            for c in (level_rank, Class.year_group, Class.stream)
        ]
    else:
        order_cols = (
            [Student.last_name.desc(), Student.first_name.desc()] if desc
            else [Student.last_name.asc(), Student.first_name.asc()]
        )
    order_cols.append(Student.id)  # deterministic tiebreaker — none of the above are unique keys

    q = q.order_by(*order_cols).offset(skip).limit(limit)
    students = list(await db.scalars(q))
    class_map = await _get_class_map([s.id for s in students], db)
    return [_to_summary(s, class_map.get(s.id)) for s in students], total


async def get_student(
    student_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> StudentDetail:
    student = await db.scalar(
        select(Student)
        .where(Student.id == student_id, Student.school_id == school_id)
        .options(
            selectinload(Student.medical_record),
            selectinload(Student.guardians).selectinload(StudentGuardian.guardian),
        )
    )
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    portal = await _portal_access(student_id, db)
    return _to_detail(student, has_portal_access=portal)


async def update_student(
    student_id: uuid.UUID,
    req: StudentUpdate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> StudentDetail:
    student = await db.scalar(
        select(Student)
        .where(Student.id == student_id, Student.school_id == school_id)
        .options(
            selectinload(Student.medical_record),
            selectinload(Student.guardians).selectinload(StudentGuardian.guardian),
        )
    )
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    for field, val in req.model_dump(exclude_unset=True).items():
        setattr(student, field, val)
    await db.flush()
    return _to_detail(student)


async def upsert_medical_record(
    student_id: uuid.UUID,
    req: MedicalRecordUpsert,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> MedicalRecordRead:
    student = await db.get(Student, student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    rec = await db.scalar(
        select(StudentMedicalRecord).where(StudentMedicalRecord.student_id == student_id)
    )
    if rec:
        for field, val in req.model_dump(exclude_unset=True).items():
            setattr(rec, field, val)
    else:
        rec = StudentMedicalRecord(
            school_id=school_id,
            student_id=student_id,
            **req.model_dump(),
        )
        db.add(rec)
    await db.flush()
    return MedicalRecordRead.model_validate(rec)


