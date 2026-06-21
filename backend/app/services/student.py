"""
Student CRUD, guardian management, and medical record upsert.

Enrollment (initial + term) and transfer logic live in student_enrollment.py.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import Class, SHSProgramme
from app.models.students import (
    Guardian,
    Student,
    StudentClassAssignment,
    StudentGuardian,
    StudentMedicalRecord,
    TermEnrollment,
)
from app.schemas.students import (
    GuardianCreate,
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
        occupation=g.occupation,
        relation_type=sg.relation_type,
        is_primary=sg.is_primary,
    )


def _to_detail(s: Student) -> StudentDetail:
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
        medical_record=MedicalRecordRead.model_validate(s.medical_record) if s.medical_record else None,
        guardians=[_to_guardian_read(sg) for sg in s.guardians],
    )


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


async def _get_class_map(
    student_ids: list[uuid.UUID],
    db: AsyncSession,
) -> dict[uuid.UUID, tuple[str, int, str | None, str | None, uuid.UUID]]:
    if not student_ids:
        return {}
    rows = await db.execute(
        select(
            StudentClassAssignment.student_id,
            Class.level,
            Class.year_group,
            Class.stream,
            SHSProgramme.name.label("programme_name"),
            Class.id.label("class_id"),
        )
        .join(Class, Class.id == StudentClassAssignment.class_id)
        .outerjoin(SHSProgramme, SHSProgramme.id == Class.programme_id)
        .where(
            StudentClassAssignment.student_id.in_(student_ids),
            StudentClassAssignment.is_active == True,  # noqa: E712
        )
    )
    result: dict[uuid.UUID, tuple] = {}
    for r in rows:
        if r.student_id not in result:
            result[r.student_id] = (r.level, r.year_group, r.programme_name, r.stream, r.class_id)
    return result


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
) -> list[StudentSummary]:
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
    if search:
        s = f"%{search}%"
        q = q.where(or_(
            Student.first_name.ilike(s),
            Student.last_name.ilike(s),
            Student.admission_number.ilike(s),
        ))
    q = q.distinct().order_by(Student.last_name, Student.first_name).offset(skip).limit(limit)
    students = list(await db.scalars(q))
    class_map = await _get_class_map([s.id for s in students], db)
    return [_to_summary(s, class_map.get(s.id)) for s in students]


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
    return _to_detail(student)


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


async def add_guardian(
    student_id: uuid.UUID,
    req: GuardianCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> StudentGuardianRead:
    student = await db.get(Student, student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    if req.is_primary:
        # Demote any existing primary guardian for this student
        await db.execute(
            select(StudentGuardian)
            .where(StudentGuardian.student_id == student_id, StudentGuardian.is_primary == True)  # noqa: E712
        )
        existing_primary = await db.scalars(
            select(StudentGuardian)
            .where(StudentGuardian.student_id == student_id, StudentGuardian.is_primary == True)  # noqa: E712
        )
        for sg in existing_primary:
            sg.is_primary = False

    guardian = Guardian(
        school_id=school_id,
        first_name=req.first_name.strip(),
        last_name=req.last_name.strip(),
        phone=req.phone.strip(),
        email=req.email.lower().strip() if req.email else None,
        occupation=req.occupation,
        address=req.address,
    )
    db.add(guardian)
    await db.flush()

    link = StudentGuardian(
        school_id=school_id,
        student_id=student_id,
        guardian_id=guardian.id,
        relation_type=req.relation_type.strip(),
        is_primary=req.is_primary,
    )
    db.add(link)
    await db.flush()
    link.guardian = guardian
    return _to_guardian_read(link)


async def remove_guardian(
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    link = await db.scalar(
        select(StudentGuardian).where(
            StudentGuardian.student_id == student_id,
            StudentGuardian.guardian_id == guardian_id,
            StudentGuardian.school_id == school_id,
        )
    )
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guardian link not found.")
    await db.delete(link)
    await db.flush()
