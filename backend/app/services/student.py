"""
Student CRUD and medical record upsert.

Guardian add/update/remove live in student_guardian.py.
Enrollment (initial + term) and transfer logic live in student_enrollment.py.
Listing/search lives in student_list.py. Photo upload/delete lives in
student_photo.py. Shared display helpers (_display_name, _class_display_name,
_photo_url, _get_class_map) live in student_display.py — split out when this
file went over the 300-line cap.

ADMISSION NUMBER AUTO-GENERATION
---------------------------------
StudentCreate.admission_number is optional. When omitted, _next_admission_number()
generates {SCHOOL_CODE}/{YEAR}/{SEQ} (YEAR = calendar year at creation time, SEQ
resets to 0001 each year, zero-padded to 4 digits). A caller-supplied value is
always honoured as-is, so existing numbering schemes (bulk import, mid-year
onboarding) keep working unchanged.
"""
from __future__ import annotations
import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auth import User
from app.models.school import School
from app.models.students import (
    Student,
    StudentGuardian,
    StudentMedicalRecord,
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
from app.services.student_display import _class_display_name, _display_name, _photo_url
from app.services.student_lifecycle import deactivate_student, reactivate_student


def _to_summary(
    s: Student,
    class_info: tuple[str, int, str | None, str | None, uuid.UUID] | None = None,
) -> StudentSummary:
    current_class_name = None
    current_class_id = None
    if class_info:
        level, year_group, programme, stream, cls_id = class_info
        current_class_name = _class_display_name(level, year_group, programme, stream)
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
        photo_url=_photo_url(s.photo_path),
    )


def _to_guardian_read(sg: StudentGuardian, has_portal_access: bool = False) -> StudentGuardianRead:
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
        has_portal_access=has_portal_access,
    )


def _to_detail(
    s: Student,
    has_portal_access: bool = False,
    guardian_portal_ids: set[uuid.UUID] | None = None,
) -> StudentDetail:
    guardian_portal_ids = guardian_portal_ids or set()
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
        guardians=[
            _to_guardian_read(sg, has_portal_access=sg.guardian_id in guardian_portal_ids)
            for sg in s.guardians
        ],
    )


async def _portal_access(student_id: uuid.UUID, db: AsyncSession) -> bool:
    return await db.scalar(
        select(User.id).where(User.student_id == student_id, User.is_active.is_(True))
    ) is not None


async def _guardian_portal_access_ids(guardian_ids: list[uuid.UUID], db: AsyncSession) -> set[uuid.UUID]:
    if not guardian_ids:
        return set()
    rows = await db.scalars(
        select(User.guardian_id).where(
            User.guardian_id.in_(guardian_ids), User.is_active.is_(True)
        )
    )
    return set(rows)


async def _next_admission_number(school_id: uuid.UUID, school_code: str, db: AsyncSession) -> str:
    """{SCHOOL_CODE}/{YEAR}/{SEQ} — SEQ resets to 0001 each calendar year.

    Scans existing admission numbers under this year's prefix rather than
    keeping a separate counter row, so it stays correct even if a school
    also has manually-entered numbers that don't match the auto pattern
    (those are simply ignored when computing the next sequence).
    """
    prefix = f"{school_code}/{date.today().year}/"
    existing = await db.scalars(
        select(Student.admission_number)
        .where(Student.school_id == school_id, Student.admission_number.like(f"{prefix}%"))
    )
    max_seq = 0
    for num in existing:
        suffix = num[len(prefix):]
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))
    return f"{prefix}{max_seq + 1:04d}"


async def create_student(
    req: StudentCreate,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> StudentDetail:
    auto_generate = req.admission_number is None
    school_code = "SCHOOL"
    if auto_generate:
        school = await db.get(School, school_id)
        school_code = school.school_code if school else "SCHOOL"

    # Auto-generated numbers get a few retries in case of a concurrent-create
    # race on the sequence; a caller-supplied number gets exactly one attempt
    # so a genuine duplicate still surfaces as a 409 immediately.
    max_attempts = 5 if auto_generate else 1
    for attempt in range(max_attempts):
        admission_number = (
            await _next_admission_number(school_id, school_code, db)
            if auto_generate else req.admission_number
        )
        student = Student(
            school_id=school_id,
            admission_number=admission_number,
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
            break
        except IntegrityError:
            await db.rollback()
            if not auto_generate or attempt == max_attempts - 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Admission number '{admission_number}' already exists at this school.",
                )
    await db.refresh(student, attribute_names=["medical_record", "guardians"])
    return _to_detail(student)


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
    guardian_portal_ids = await _guardian_portal_access_ids(
        [sg.guardian_id for sg in student.guardians], db
    )
    return _to_detail(student, has_portal_access=portal, guardian_portal_ids=guardian_portal_ids)


async def update_student(
    student_id: uuid.UUID,
    req: StudentUpdate,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
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

    data = req.model_dump(exclude_unset=True)
    new_active = data.pop("is_active", None)
    for field, val in data.items():
        setattr(student, field, val)

    # Student.is_active alone isn't the whole picture — class assignment,
    # term enrollment, and portal login all need to move with it. Route
    # through the same cascades transfer approval / bulk graduation use,
    # rather than a bare setattr, so this page's Deactivate/Reactivate
    # buttons behave consistently with every other path that changes this.
    if new_active is not None and new_active != student.is_active:
        if new_active:
            await reactivate_student(student_id, school_id, user_id, db)
        else:
            await deactivate_student(student_id, school_id, db)

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
