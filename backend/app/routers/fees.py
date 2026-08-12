"""
fees.collect/fees.manage are deliberately unscoped school-wide (a bursar's
job legitimately spans every student) — but a plain fees.view holder (e.g.
CLASS_TEACHER/TEACHER, who need it for other reasons) was previously able
to read *any* student's balance/payment/discount history via the four
per-student read endpoints below, with no scoping at all, unlike every
other module that draws this line (Students/Attendance/Assessments/
Housing). assert_can_view_student() closes that gap; it already returns
"unrestricted" for fees.collect/fees.manage holders (see
core/student_scope.py::resolve_student_view_scope's own docstring), so a
bursar's access is unaffected.
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.student_scope import assert_can_view_student
from app.schemas.fees import (
    BulkAssignResult, FeeDiscountCreate, FeeDiscountRead,
    FeePaymentCreate, FeePaymentRead, FeeRecordRead, FeeSummaryRead,
    FeeStructureCreate, FeeStructureRead, FeeStructureUpdate,
    FeeTypeCreate, FeeTypeRead, FeeTypeUpdate,
    InstalmentCreate, InstalmentRead,
)
from app.services import fees as fee_svc
from app.services import fees_payment as payment_svc

router = APIRouter(prefix="/fees", tags=["fees"])


# ── Fee types ─────────────────────────────────────────────────────────────────

@router.post("/types", response_model=FeeTypeRead, status_code=201)
async def create_fee_type(
    req: FeeTypeCreate,
    auth=Depends(require_permission("fees", "manage")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = auth
    return await fee_svc.create_fee_type(req, school_id, db)


@router.get("/types", response_model=list[FeeTypeRead])
async def list_fee_types(
    auth=Depends(require_permission("fees", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = auth
    return await fee_svc.list_fee_types(school_id, db)


@router.patch("/types/{type_id}", response_model=FeeTypeRead)
async def update_fee_type(
    type_id: uuid.UUID,
    req: FeeTypeUpdate,
    auth=Depends(require_permission("fees", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = auth
    return await fee_svc.update_fee_type(type_id, req, school_id, db)


# ── Fee structures ────────────────────────────────────────────────────────────

@router.post("/structures", response_model=FeeStructureRead, status_code=201)
async def create_fee_structure(
    req: FeeStructureCreate,
    auth=Depends(require_permission("fees", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = auth
    return await fee_svc.create_fee_structure(req, school_id, db)


@router.get("/structures", response_model=list[FeeStructureRead])
async def list_fee_structures(
    term_id: uuid.UUID = Query(...),
    auth=Depends(require_permission("fees", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = auth
    return await fee_svc.list_fee_structures(term_id, school_id, db)


@router.patch("/structures/{structure_id}", response_model=FeeStructureRead)
async def update_fee_structure(
    structure_id: uuid.UUID,
    req: FeeStructureUpdate,
    auth=Depends(require_permission("fees", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = auth
    return await fee_svc.update_fee_structure(structure_id, req, school_id, db)


@router.post("/structures/{structure_id}/bulk-assign", response_model=BulkAssignResult)
async def bulk_assign_fees(
    structure_id: uuid.UUID,
    auth=Depends(require_permission("fees", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = auth
    return await fee_svc.bulk_assign_fees(structure_id, school_id, db)


# ── Student fee records & summary ─────────────────────────────────────────────

@router.get("/students/{student_id}/records", response_model=list[FeeRecordRead])
async def get_student_fee_records(
    student_id: uuid.UUID,
    term_id: uuid.UUID = Query(...),
    auth=Depends(require_permission("fees", "view")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = auth
    await assert_can_view_student(user_id, student_id, school_id, db)
    return await fee_svc.get_student_fee_records(student_id, term_id, school_id, db)


@router.get("/students/{student_id}/summary", response_model=FeeSummaryRead)
async def get_fee_summary(
    student_id: uuid.UUID,
    term_id: uuid.UUID = Query(...),
    auth=Depends(require_permission("fees", "view")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = auth
    await assert_can_view_student(user_id, student_id, school_id, db)
    return await fee_svc.get_fee_summary(student_id, term_id, school_id, db)


# ── Payments ──────────────────────────────────────────────────────────────────

@router.post("/payments", response_model=FeePaymentRead, status_code=201)
async def record_payment(
    req: FeePaymentCreate,
    auth=Depends(require_permission("fees", "collect")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = auth
    return await payment_svc.record_payment(req, school_id, user_id, db)


@router.get("/payments", response_model=list[FeePaymentRead])
async def list_payments(
    student_id: uuid.UUID = Query(...),
    term_id: uuid.UUID = Query(...),
    auth=Depends(require_permission("fees", "view")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = auth
    await assert_can_view_student(user_id, student_id, school_id, db)
    return await payment_svc.list_payments(student_id, term_id, school_id, db)


# ── Discounts ─────────────────────────────────────────────────────────────────

@router.post("/discounts", response_model=FeeDiscountRead, status_code=201)
async def apply_discount(
    req: FeeDiscountCreate,
    auth=Depends(require_permission("fees", "manage")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = auth
    return await payment_svc.apply_discount(req, school_id, user_id, db)


@router.get("/discounts", response_model=list[FeeDiscountRead])
async def list_discounts(
    student_id: uuid.UUID = Query(...),
    term_id: uuid.UUID = Query(...),
    auth=Depends(require_permission("fees", "view")),
    db: AsyncSession = Depends(get_db),
):
    user_id, school_id = auth
    await assert_can_view_student(user_id, student_id, school_id, db)
    return await payment_svc.list_discounts(student_id, term_id, school_id, db)


# ── Instalment plans ──────────────────────────────────────────────────────────

@router.put("/records/{record_id}/instalments", response_model=list[InstalmentRead])
async def set_instalment_plan(
    record_id: uuid.UUID,
    items: list[InstalmentCreate],
    auth=Depends(require_permission("fees", "manage")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = auth
    return await payment_svc.create_instalment_plan(record_id, items, school_id, db)


@router.get("/records/{record_id}/instalments", response_model=list[InstalmentRead])
async def list_instalments(
    record_id: uuid.UUID,
    auth=Depends(require_permission("fees", "view")),
    db: AsyncSession = Depends(get_db),
):
    _, school_id = auth
    return await payment_svc.list_instalments(record_id, school_id, db)
