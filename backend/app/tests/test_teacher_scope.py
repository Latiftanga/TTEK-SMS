"""
Direct unit tests of core/teacher_scope.py's resolver functions — the shared
authorization primitive behind the Attendance/Assessments/Report-Card
scoping fixes (integration-level regression tests live in test_attendance.py,
test_assessment_scope.py, test_report_cards.py, test_students.py).

Run inside Docker: docker compose exec api pytest app/tests/test_teacher_scope.py -v
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.core.teacher_scope import (
    classes_for_scope, resolve_assessment_scope, resolve_attendance_scope, resolve_report_card_scope,
)
from app.models.academic import AcademicTerm, AcademicYear, Class, ClassTeacher, SubjectTeacher
from app.models.assessments import Assessment  # noqa: F401 — ensures models are registered
from app.models.auth import LoginType, StaffPosition, User
from app.models.school import School
from app.models.staff import StaffMember


async def _make_staff_with_position(
    db_session: AsyncSession, school: School, position_code: str, suffix: str,
) -> tuple[StaffMember, User]:
    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == position_code))
    assert pos is not None, "Run seed_reference_data.py first"

    staff = StaffMember(
        school_id=school.id, staff_number=f"TS-{suffix}",
        first_name="Test", last_name=position_code.title(), is_active=True,
    )
    db_session.add(staff)
    await db_session.flush()

    from app.models.staff import staff_member_positions
    await db_session.execute(
        staff_member_positions.insert().values(staff_member_id=staff.id, position_id=pos.id)
    )

    user = User(
        school_id=school.id, login_type=LoginType.EMAIL, email=f"{suffix.lower()}@presec-test.edu.gh",
        password_hash=hash_password("Whatever123!"), is_active=True, staff_member_id=staff.id,
    )
    db_session.add(user)
    await db_session.flush()
    return staff, user


# ── resolve_attendance_scope ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolve_attendance_scope_none_for_approve_holder(
    db_session: AsyncSession, school: School, academic_year: AcademicYear, redis_permissions: None,
):
    """HEAD holds attendance.approve — always unrestricted."""
    _staff, user = await _make_staff_with_position(db_session, school, "HEAD", "HEAD1")
    scope = await resolve_attendance_scope(user.id, academic_year.id, db_session)
    assert scope is None


@pytest.mark.asyncio
async def test_resolve_attendance_scope_exact_set_for_class_teacher(
    db_session: AsyncSession, school: School, school_class: Class, academic_year: AcademicYear, redis_permissions: None,
):
    staff, user = await _make_staff_with_position(db_session, school, "CLASS_TEACHER", "CT1")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    scope = await resolve_attendance_scope(user.id, academic_year.id, db_session)
    assert scope == {school_class.id}


@pytest.mark.asyncio
async def test_resolve_attendance_scope_empty_not_none_with_zero_assignments(
    db_session: AsyncSession, school: School, academic_year: AcademicYear, redis_permissions: None,
):
    """A hard access-control boundary, not a curriculum fallback: zero
    recorded assignments means an empty set (deny), never None (unrestricted)."""
    _staff, user = await _make_staff_with_position(db_session, school, "CLASS_TEACHER", "CT2")
    scope = await resolve_attendance_scope(user.id, academic_year.id, db_session)
    assert scope == set()


# ── resolve_assessment_scope ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolve_assessment_scope_none_for_approve_scores_holder(
    db_session: AsyncSession, school: School, academic_year: AcademicYear, redis_permissions: None,
):
    _staff, user = await _make_staff_with_position(db_session, school, "EXAM_OFFICER", "EO1")
    scope = await resolve_assessment_scope(user.id, academic_year.id, db_session)
    assert scope is None


@pytest.mark.asyncio
async def test_resolve_assessment_scope_exact_pairs_for_subject_teacher(
    db_session: AsyncSession, school: School, school_class: Class, academic_year: AcademicYear, redis_permissions: None,
):
    import uuid
    subject_id = uuid.uuid4()
    staff, user = await _make_staff_with_position(db_session, school, "CLASS_TEACHER", "CT3")
    # Bypass the Subject FK for this direct-resolver unit test by using a real
    # subject row instead — keeps the test focused on the resolver, not on
    # subject setup, mirroring the fixtures already used elsewhere.
    from app.models.academic import SchoolLevel, Subject, SubjectCatalogue, SubjectType
    cat = SubjectCatalogue(name="Test Subject", code="SCOPE_UNIT", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code="SCOPE_UNIT", name="Test Subject", is_active=True)
    db_session.add(subj)
    await db_session.flush()

    db_session.add(SubjectTeacher(
        school_id=school.id, class_id=school_class.id, subject_id=subj.id,
        staff_member_id=staff.id, academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    scope = await resolve_assessment_scope(user.id, academic_year.id, db_session)
    assert scope == {(school_class.id, subj.id)}


@pytest.mark.asyncio
async def test_resolve_assessment_scope_empty_not_none_with_zero_assignments(
    db_session: AsyncSession, school: School, academic_year: AcademicYear, redis_permissions: None,
):
    _staff, user = await _make_staff_with_position(db_session, school, "CLASS_TEACHER", "CT4")
    scope = await resolve_assessment_scope(user.id, academic_year.id, db_session)
    assert scope == set()


# ── resolve_report_card_scope ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolve_report_card_scope_none_for_approve_scores_holder(
    db_session: AsyncSession, school: School, academic_year: AcademicYear, redis_permissions: None,
):
    _staff, user = await _make_staff_with_position(db_session, school, "HOD", "HOD1")
    scope = await resolve_report_card_scope(user.id, academic_year.id, db_session)
    assert scope is None


@pytest.mark.asyncio
async def test_resolve_report_card_scope_exact_set_for_class_teacher(
    db_session: AsyncSession, school: School, school_class: Class, academic_year: AcademicYear, redis_permissions: None,
):
    staff, user = await _make_staff_with_position(db_session, school, "CLASS_TEACHER", "CT5")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    scope = await resolve_report_card_scope(user.id, academic_year.id, db_session)
    assert scope == {school_class.id}


# ── classes_for_scope ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_classes_for_scope_returns_every_class_when_unrestricted(
    db_session: AsyncSession, school: School, school_class: Class,
):
    classes = await classes_for_scope(None, school.id, db_session)
    assert any(c.id == school_class.id for c in classes)


@pytest.mark.asyncio
async def test_classes_for_scope_empty_set_returns_no_classes(
    db_session: AsyncSession, school: School, school_class: Class,
):
    classes = await classes_for_scope(set(), school.id, db_session)
    assert classes == []


@pytest.mark.asyncio
async def test_classes_for_scope_filters_to_given_ids(
    db_session: AsyncSession, school: School, school_class: Class,
):
    other = Class(school_id=school.id, level="SHS", year_group=1, stream="B", is_active=True)
    db_session.add(other)
    await db_session.flush()

    classes = await classes_for_scope({school_class.id}, school.id, db_session)
    assert [c.id for c in classes] == [school_class.id]
