"""
Direct unit tests of core/student_scope.py's resolver functions — the shared
authorization primitive behind the Students module class-teacher/
subject-teacher scoping fix (integration-level regression tests live in
test_students.py, test_student_enrollment.py, test_student_lifecycle.py).

Mirrors test_teacher_scope.py's structure/fixture style.

Run inside Docker: docker compose exec api pytest app/tests/test_student_scope.py -v
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.core.student_scope import (
    can_write_student,
    current_class_assignment,
    resolve_class_teacher_scope,
    resolve_student_view_scope,
    resolve_subject_teacher_scope,
)
from app.models.academic import AcademicYear, Class, ClassTeacher, SubjectTeacher
from app.models.auth import LoginType, StaffPosition, User
from app.models.school import School
from app.models.staff import StaffMember
from app.models.students import Student, StudentClassAssignment


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


async def _assign_class(
    db_session: AsyncSession, school: School, student: Student, cls: Class, year: AcademicYear,
) -> StudentClassAssignment:
    sca = StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=cls.id,
        academic_year_id=year.id, is_active=True,
    )
    db_session.add(sca)
    await db_session.flush()
    return sca


# ── resolve_student_view_scope ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_view_scope_none_for_students_delete_holder(
    db_session: AsyncSession, school: School, redis_permissions: None,
):
    """HEAD holds students.delete — always unrestricted."""
    _staff, user = await _make_staff_with_position(db_session, school, "HEAD", "HEAD1")
    scope = await resolve_student_view_scope(user.id, school.id, db_session)
    assert scope is None


@pytest.mark.asyncio
async def test_view_scope_none_for_broad_access_perm_holder(
    db_session: AsyncSession, school: School, redis_permissions: None,
):
    """BURSAR holds fees.collect/manage — needs cross-class visibility for
    their own job, so stays unrestricted even without students.delete."""
    _staff, user = await _make_staff_with_position(db_session, school, "BURSAR", "BUR1")
    scope = await resolve_student_view_scope(user.id, school.id, db_session)
    assert scope is None


@pytest.mark.asyncio
async def test_view_scope_includes_class_teacher_students(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_year: AcademicYear, student: Student, redis_permissions: None,
):
    staff, user = await _make_staff_with_position(db_session, school, "CLASS_TEACHER", "CT1")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await _assign_class(db_session, school, student, school_class, academic_year)

    scope = await resolve_student_view_scope(user.id, school.id, db_session)
    assert scope == {student.id}


@pytest.mark.asyncio
async def test_view_scope_empty_not_none_with_zero_assignments(
    db_session: AsyncSession, school: School, redis_permissions: None,
):
    """A hard access-control boundary, not a curriculum fallback: zero
    recorded assignments means an empty set (deny), never None (unrestricted)."""
    _staff, user = await _make_staff_with_position(db_session, school, "CLASS_TEACHER", "CT2")
    scope = await resolve_student_view_scope(user.id, school.id, db_session)
    assert scope == set()


# ── resolve_class_teacher_scope ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_class_teacher_scope_exact_set(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_year: AcademicYear, redis_permissions: None,
):
    staff, user = await _make_staff_with_position(db_session, school, "CLASS_TEACHER", "CT3")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    scope = await resolve_class_teacher_scope(user.id, academic_year.id, db_session)
    assert scope == {school_class.id}


@pytest.mark.asyncio
async def test_class_teacher_scope_none_for_deputy_head(
    db_session: AsyncSession, school: School, academic_year: AcademicYear, redis_permissions: None,
):
    """DEPUTY_HEAD holds students.delete (added alongside this fix) — stays
    unrestricted even with zero ClassTeacher assignments of their own."""
    _staff, user = await _make_staff_with_position(db_session, school, "DEPUTY_HEAD", "DH1")
    scope = await resolve_class_teacher_scope(user.id, academic_year.id, db_session)
    assert scope is None


@pytest.mark.asyncio
async def test_class_teacher_scope_none_for_hod(
    db_session: AsyncSession, school: School, academic_year: AcademicYear, redis_permissions: None,
):
    _staff, user = await _make_staff_with_position(db_session, school, "HOD", "HOD1")
    scope = await resolve_class_teacher_scope(user.id, academic_year.id, db_session)
    assert scope is None


# ── resolve_subject_teacher_scope ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_subject_teacher_scope_exact_pairs(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_year: AcademicYear, redis_permissions: None,
):
    from app.models.academic import SchoolLevel, Subject, SubjectCatalogue, SubjectType

    staff, user = await _make_staff_with_position(db_session, school, "CLASS_TEACHER", "ST1")
    cat = SubjectCatalogue(name="Test Subject", code="SCOPE_UNIT2", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code="SCOPE_UNIT2", name="Test Subject", is_active=True)
    db_session.add(subj)
    await db_session.flush()

    db_session.add(SubjectTeacher(
        school_id=school.id, class_id=school_class.id, subject_id=subj.id,
        staff_member_id=staff.id, academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    scope = await resolve_subject_teacher_scope(user.id, academic_year.id, db_session)
    assert scope == {(school_class.id, subj.id)}


# ── can_write_student / current_class_assignment ───────────────────────────────

@pytest.mark.asyncio
async def test_current_class_assignment_none_when_unassigned(
    db_session: AsyncSession, student: Student,
):
    assert await current_class_assignment(student.id, db_session) is None


@pytest.mark.asyncio
async def test_can_write_student_true_for_own_class(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_year: AcademicYear, student: Student, redis_permissions: None,
):
    staff, user = await _make_staff_with_position(db_session, school, "CLASS_TEACHER", "CT4")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await _assign_class(db_session, school, student, school_class, academic_year)

    assert await can_write_student(user.id, student.id, db_session) is True


@pytest.mark.asyncio
async def test_can_write_student_false_for_other_class(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_year: AcademicYear, student: Student, redis_permissions: None,
):
    other_class = Class(school_id=school.id, level="SHS", year_group=1, stream="B", is_active=True)
    db_session.add(other_class)
    await db_session.flush()

    staff, user = await _make_staff_with_position(db_session, school, "CLASS_TEACHER", "CT5")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=other_class.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await _assign_class(db_session, school, student, school_class, academic_year)

    assert await can_write_student(user.id, student.id, db_session) is False


@pytest.mark.asyncio
async def test_can_write_student_false_when_unassigned_and_scoped(
    db_session: AsyncSession, school: School, student: Student, redis_permissions: None,
):
    """A student with no active class assignment can't be reached by a
    scoped caller — never a silent fallback."""
    _staff, user = await _make_staff_with_position(db_session, school, "CLASS_TEACHER", "CT6")
    assert await can_write_student(user.id, student.id, db_session) is False


@pytest.mark.asyncio
async def test_can_write_student_true_for_students_delete_holder_anywhere(
    db_session: AsyncSession, school: School, student: Student, redis_permissions: None,
):
    _staff, user = await _make_staff_with_position(db_session, school, "HEAD", "HEAD2")
    assert await can_write_student(user.id, student.id, db_session) is True
