from __future__ import annotations
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fees import FeeDiscount, FeeInstalmentPlan, FeePayment, StudentFeeRecord
from app.schemas.fees import (
    FeeDiscountCreate, FeeDiscountRead,
    FeePaymentCreate, FeePaymentRead,
    InstalmentCreate, InstalmentRead,
)


def _to_payment_read(fp: FeePayment) -> FeePaymentRead:
    return FeePaymentRead.model_validate(fp)


def _to_discount_read(fd: FeeDiscount) -> FeeDiscountRead:
    return FeeDiscountRead.model_validate(fd)


def _to_instalment_read(fi: FeeInstalmentPlan) -> InstalmentRead:
    return InstalmentRead.model_validate(fi)


async def _get_record(
    fee_record_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> StudentFeeRecord:
    rec = await db.scalar(
        select(StudentFeeRecord).where(
            StudentFeeRecord.id == fee_record_id,
            StudentFeeRecord.school_id == school_id,
        )
    )
    if not rec:
        raise HTTPException(404, "Fee record not found.")
    return rec


async def record_payment(
    req: FeePaymentCreate, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> FeePaymentRead:
    rec = await _get_record(req.fee_record_id, school_id, db)
    if rec.is_waived:
        raise HTTPException(409, "Cannot record a payment on a waived fee record.")
    payment = FeePayment(
        school_id=school_id,
        student_id=req.student_id,
        academic_term_id=rec.academic_term_id,
        fee_record_id=req.fee_record_id,
        amount_paid=req.amount_paid,
        payment_method=req.payment_method,
        reference_number=req.reference_number,
        received_by_id=user_id,
        payment_date=req.payment_date,
        notes=req.notes,
    )
    db.add(payment)
    await db.flush()
    return _to_payment_read(payment)


async def list_payments(
    student_id: uuid.UUID, term_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> list[FeePaymentRead]:
    rows = (await db.scalars(
        select(FeePayment)
        .where(
            FeePayment.student_id == student_id,
            FeePayment.academic_term_id == term_id,
            FeePayment.school_id == school_id,
        )
        .order_by(FeePayment.payment_date)
    )).all()
    return [_to_payment_read(fp) for fp in rows]


async def apply_discount(
    req: FeeDiscountCreate, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> FeeDiscountRead:
    rec = await _get_record(req.fee_record_id, school_id, db)
    discount = FeeDiscount(
        school_id=school_id,
        student_id=req.student_id,
        academic_term_id=rec.academic_term_id,
        fee_record_id=req.fee_record_id,
        discount_type=req.discount_type,
        amount=req.amount,
        percentage=req.percentage,
        reason=req.reason,
        approved_by_id=user_id,
    )
    db.add(discount)
    await db.flush()
    return _to_discount_read(discount)


async def list_discounts(
    student_id: uuid.UUID, term_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> list[FeeDiscountRead]:
    rows = (await db.scalars(
        select(FeeDiscount)
        .where(
            FeeDiscount.student_id == student_id,
            FeeDiscount.academic_term_id == term_id,
            FeeDiscount.school_id == school_id,
        )
    )).all()
    return [_to_discount_read(fd) for fd in rows]


async def create_instalment_plan(
    record_id: uuid.UUID,
    items: list[InstalmentCreate],
    school_id: uuid.UUID,
    db: AsyncSession,
) -> list[InstalmentRead]:
    rec = await _get_record(record_id, school_id, db)
    nums = [i.instalment_number for i in items]
    if len(nums) != len(set(nums)):
        raise HTTPException(422, "Duplicate instalment_number values in plan.")
    # Replace existing plan
    existing = (await db.scalars(
        select(FeeInstalmentPlan).where(FeeInstalmentPlan.fee_record_id == record_id)
    )).all()
    for inst in existing:
        await db.delete(inst)
    result = []
    for item in sorted(items, key=lambda x: x.instalment_number):
        inst = FeeInstalmentPlan(
            school_id=school_id,
            student_id=rec.student_id,
            fee_record_id=record_id,
            instalment_number=item.instalment_number,
            amount=item.amount,
            due_date=item.due_date,
            is_paid=False,
        )
        db.add(inst)
        result.append(inst)
    await db.flush()
    return [_to_instalment_read(i) for i in result]


async def list_instalments(
    record_id: uuid.UUID, school_id: uuid.UUID, db: AsyncSession
) -> list[InstalmentRead]:
    await _get_record(record_id, school_id, db)
    rows = (await db.scalars(
        select(FeeInstalmentPlan)
        .where(FeeInstalmentPlan.fee_record_id == record_id)
        .order_by(FeeInstalmentPlan.instalment_number)
    )).all()
    return [_to_instalment_read(fi) for fi in rows]
