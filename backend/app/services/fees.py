from __future__ import annotations
import uuid

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import AcademicTerm, Class
from app.models.fees import FeeStructure, FeeType, StudentFeeRecord, StudentFeeSummary
from app.models.students import Student, StudentClassAssignment
from app.schemas.fees import (
    BulkAssignResult, FeeRecordRead, FeeSummaryRead,
    FeeStructureCreate, FeeStructureRead, FeeStructureUpdate,
    FeeTypeCreate, FeeTypeRead, FeeTypeUpdate,
)


def _to_type_read(ft: FeeType) -> FeeTypeRead:
    return FeeTypeRead.model_validate(ft)


def _to_structure_read(fs: FeeStructure) -> FeeStructureRead:
    return FeeStructureRead(
        id=fs.id,
        school_id=fs.school_id,
        academic_term_id=fs.academic_term_id,
        fee_type_id=fs.fee_type_id,
        fee_type_name=fs.fee_type.name,
        amount=fs.amount,
        is_mandatory=fs.is_mandatory,
        applies_to_year_group=fs.applies_to_year_group,
        applies_to_programme_id=fs.applies_to_programme_id,
    )


def _to_record_read(sfr: StudentFeeRecord) -> FeeRecordRead:
    return FeeRecordRead(
        id=sfr.id,
        student_id=sfr.student_id,
        academic_term_id=sfr.academic_term_id,
        fee_structure_id=sfr.fee_structure_id,
        fee_type_name=sfr.fee_structure.fee_type.name,
        amount_due=sfr.amount_due,
        due_date=sfr.due_date,
        is_waived=sfr.is_waived,
    )


# ── Fee types ─────────────────────────────────────────────────────────────────

async def create_fee_type(req: FeeTypeCreate, school_id: uuid.UUID, db: AsyncSession) -> FeeTypeRead:
    ft = FeeType(
        school_id=school_id,
        name=req.name,
        code=req.code.upper(),
        description=req.description,
        is_recurring=req.is_recurring,
        is_active=True,
    )
    db.add(ft)
    await db.flush()
    return _to_type_read(ft)


async def list_fee_types(school_id: uuid.UUID, db: AsyncSession) -> list[FeeTypeRead]:
    rows = (await db.scalars(
        select(FeeType)
        .where(or_(FeeType.school_id == school_id, FeeType.school_id.is_(None)))
        .where(FeeType.is_active.is_(True))
        .order_by(FeeType.name)
    )).all()
    return [_to_type_read(ft) for ft in rows]


async def update_fee_type(
    type_id: uuid.UUID, req: FeeTypeUpdate, school_id: uuid.UUID, db: AsyncSession
) -> FeeTypeRead:
    ft = await db.scalar(
        select(FeeType).where(FeeType.id == type_id, FeeType.school_id == school_id)
    )
    if not ft:
        raise HTTPException(404, "Fee type not found.")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(ft, k, v)
    await db.flush()
    return _to_type_read(ft)


# ── Fee structures ────────────────────────────────────────────────────────────

async def create_fee_structure(
    req: FeeStructureCreate, school_id: uuid.UUID, db: AsyncSession
) -> FeeStructureRead:
    term = await db.scalar(
        select(AcademicTerm).where(
            AcademicTerm.id == req.academic_term_id, AcademicTerm.school_id == school_id
        )
    )
    if not term:
        raise HTTPException(404, "Academic term not found.")
    fee_type = await db.scalar(
        select(FeeType).where(
            FeeType.id == req.fee_type_id,
            or_(FeeType.school_id == school_id, FeeType.school_id.is_(None)),
        )
    )
    if not fee_type:
        raise HTTPException(404, "Fee type not found.")
    fs = FeeStructure(
        school_id=school_id,
        academic_term_id=req.academic_term_id,
        fee_type_id=req.fee_type_id,
        amount=req.amount,
        is_mandatory=req.is_mandatory,
        applies_to_year_group=req.applies_to_year_group,
        applies_to_programme_id=req.applies_to_programme_id,
    )
    db.add(fs)
    await db.flush()
    await db.refresh(fs, attribute_names=["fee_type"])
    return _to_structure_read(fs)


async def list_fee_structures(
    term_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> list[FeeStructureRead]:
    rows = (await db.scalars(
        select(FeeStructure)
        .where(FeeStructure.academic_term_id == term_id, FeeStructure.school_id == school_id)
        .options(selectinload(FeeStructure.fee_type))
        .order_by(FeeStructure.created_at)
    )).all()
    return [_to_structure_read(fs) for fs in rows]


async def update_fee_structure(
    structure_id: uuid.UUID, req: FeeStructureUpdate, school_id: uuid.UUID, db: AsyncSession
) -> FeeStructureRead:
    fs = await db.scalar(
        select(FeeStructure)
        .where(FeeStructure.id == structure_id, FeeStructure.school_id == school_id)
        .options(selectinload(FeeStructure.fee_type))
    )
    if not fs:
        raise HTTPException(404, "Fee structure not found.")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(fs, k, v)
    await db.flush()
    return _to_structure_read(fs)


# ── Bulk assignment ───────────────────────────────────────────────────────────

async def bulk_assign_fees(
    structure_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> BulkAssignResult:
    fs = await db.scalar(
        select(FeeStructure)
        .where(FeeStructure.id == structure_id, FeeStructure.school_id == school_id)
        .options(selectinload(FeeStructure.fee_type))
    )
    if not fs:
        raise HTTPException(404, "Fee structure not found.")

    term = await db.get(AcademicTerm, fs.academic_term_id)
    if not term:
        raise HTTPException(404, "Academic term not found.")

    q = (
        select(StudentClassAssignment)
        .join(Class, Class.id == StudentClassAssignment.class_id)
        .where(
            StudentClassAssignment.academic_year_id == term.academic_year_id,
            StudentClassAssignment.school_id == school_id,
            StudentClassAssignment.is_active.is_(True),
        )
    )
    if fs.applies_to_year_group:
        q = q.where(Class.year_group == fs.applies_to_year_group)
    if fs.applies_to_programme_id:
        q = q.where(Class.programme_id == fs.applies_to_programme_id)

    enrollments = (await db.scalars(q)).all()
    assigned = skipped = 0

    for te in enrollments:
        existing = await db.scalar(
            select(StudentFeeRecord).where(
                StudentFeeRecord.student_id == te.student_id,
                StudentFeeRecord.fee_structure_id == structure_id,
                StudentFeeRecord.school_id == school_id,
            )
        )
        if existing:
            skipped += 1
            continue
        db.add(StudentFeeRecord(
            school_id=school_id,
            student_id=te.student_id,
            academic_term_id=fs.academic_term_id,
            fee_structure_id=structure_id,
            amount_due=fs.amount,
        ))
        assigned += 1

    await db.flush()
    return BulkAssignResult(structure_id=structure_id, assigned=assigned, skipped=skipped)


# ── Student fee records & summary ─────────────────────────────────────────────

async def get_student_fee_records(
    student_id: uuid.UUID, term_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> list[FeeRecordRead]:
    student = await db.scalar(
        select(Student).where(Student.id == student_id, Student.school_id == school_id)
    )
    if not student:
        raise HTTPException(404, "Student not found.")
    rows = (await db.scalars(
        select(StudentFeeRecord)
        .where(
            StudentFeeRecord.student_id == student_id,
            StudentFeeRecord.academic_term_id == term_id,
            StudentFeeRecord.school_id == school_id,
        )
        .options(
            selectinload(StudentFeeRecord.fee_structure)
            .selectinload(FeeStructure.fee_type)
        )
    )).all()
    return [_to_record_read(r) for r in rows]


async def get_fee_summary(
    student_id: uuid.UUID, term_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> FeeSummaryRead:
    student = await db.scalar(
        select(Student).where(Student.id == student_id, Student.school_id == school_id)
    )
    if not student:
        raise HTTPException(404, "Student not found.")
    summary = await db.scalar(
        select(StudentFeeSummary).where(
            StudentFeeSummary.student_id == student_id,
            StudentFeeSummary.academic_term_id == term_id,
        )
    )
    if not summary:
        raise HTTPException(404, "No fee summary found — no fees have been assigned yet.")
    return FeeSummaryRead.from_model(summary)
