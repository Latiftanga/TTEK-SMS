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
    resolve_term_enrollment_scope,
)
from app.models.academic import AcademicYear, Class, ClassTeacher, SubjectTeacher
from app.models.auth import LoginType, PositionPermission, StaffPosition, User
from app.models.school import School
from app.models.staff import StaffMember
from app.models.students import Student, StudentClassAssignment
from app.tests.legacy_position_perms import LEGACY_POSITION_PERMISSIONS


async def _make_staff_with_position(
    db_session: AsyncSession, school: School, position_code: str, suffix: str,
) -> tuple[StaffMember, User]:
    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == position_code))
    if pos is None and position_code in LEGACY_POSITION_PERMISSIONS:
        pos = StaffPosition(school_id=school.id, code=position_code, name=position_code.title(), is_template=False)
        db_session.add(pos)
        await db_session.flush()
        for module, action in LEGACY_POSITION_PERMISSIONS[position_code]:
            db_session.add(PositionPermission(position_id=pos.id, module=module, action=action, is_allowed=True))
        await db_session.flush()
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


@pytest.mark.asyncio
async def test_view_scope_excludes_student_promoted_out_of_taught_class(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_year: AcademicYear, student: Student, redis_permissions: None,
):
    """Regression test: a promoted (not graduated/withdrawn) student's prior
    StudentClassAssignment row is never deactivated (student_display.py's own
    documented behaviour) — reported live as "making a staff_member a
    class_teacher allows that teacher to see all students". A ClassTeacher of
    `school_class` must not see a student whose *current* class is somewhere
    else, even though a stale is_active=True row to school_class still exists.
    (StudentClassAssignment has a UNIQUE(student_id, academic_year_id)
    constraint, so this can only happen across two different years — same
    shape as a real promotion.)"""
    from datetime import date as _date

    staff, user = await _make_staff_with_position(db_session, school, "CLASS_TEACHER", "CT-PROMO")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    other_class = Class(school_id=school.id, level="SHS", year_group=3, stream="B", is_active=True)
    prior_year = AcademicYear(
        school_id=school.id, name="2023/2024",
        start_date=_date(2023, 9, 1), end_date=_date(2024, 7, 31), is_current=False,
    )
    db_session.add_all([other_class, prior_year])
    await db_session.flush()

    # Stale row from a prior year (promoted away from, but never deactivated).
    await _assign_class(db_session, school, student, school_class, prior_year)
    # Current row, current year — the student's real, present-day class.
    await _assign_class(db_session, school, student, other_class, academic_year)

    scope = await resolve_student_view_scope(user.id, school.id, db_session)
    assert scope == set(), (
        "student's current class is other_class, not school_class — the stale "
        "row must not leak them into this class teacher's scope"
    )


@pytest.mark.asyncio
async def test_view_scope_excludes_subject_teacher_only_students(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_year: AcademicYear, student: Student, redis_permissions: None,
):
    """A pure subject-only teacher (SubjectTeacher row, no ClassTeacher row)
    has no legitimate reason to browse the Students module — their job is
    fully served by the Assessments page's own roster/registration flow,
    scoped independently. Reported directly by the user."""
    staff, user = await _make_staff_with_position(db_session, school, "TEACHER", "SUBJ-ONLY")
    from app.models.academic import SubjectCatalogue, SubjectType, Subject, SchoolLevel

    cat = SubjectCatalogue(name="Physics", code="PHY-SCOPE", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subject = Subject(school_id=school.id, catalogue_id=cat.id, code="PHY-SCOPE", name="Physics", is_active=True)
    db_session.add(subject)
    await db_session.flush()
    db_session.add(SubjectTeacher(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        staff_member_id=staff.id, academic_year_id=academic_year.id, is_active=True,
    ))
    await _assign_class(db_session, school, student, school_class, academic_year)

    scope = await resolve_student_view_scope(user.id, school.id, db_session)
    assert scope == set(), (
        "a subject-only teacher must not see the Students module at all — "
        "their roster access comes from Assessments, not this resolver"
    )


@pytest.mark.asyncio
async def test_view_scope_dual_role_excludes_subject_taught_class(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_year: AcademicYear, student: Student, redis_permissions: None,
):
    """The exact reported live shape: a staff member who is Class Teacher of
    one class AND Subject Teacher of a *different* class must see only the
    ClassTeacher class's students on the Students list — the SubjectTeacher
    class's students stay reachable only through Assessments."""
    from app.models.academic import SubjectCatalogue, SubjectType, Subject, SchoolLevel

    staff, user = await _make_staff_with_position(db_session, school, "CLASS_TEACHER", "DUAL-ROLE")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await _assign_class(db_session, school, student, school_class, academic_year)

    other_class = Class(school_id=school.id, level="SHS", year_group=3, stream="C", is_active=True)
    other_student = Student(
        school_id=school.id, admission_number="DUAL-ROLE-STU",
        first_name="Other", last_name="Student", is_active=True,
    )
    cat = SubjectCatalogue(name="Chemistry", code="CHEM-SCOPE", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add_all([other_class, other_student, cat])
    await db_session.flush()
    subject = Subject(school_id=school.id, catalogue_id=cat.id, code="CHEM-SCOPE", name="Chemistry", is_active=True)
    db_session.add(subject)
    await db_session.flush()
    db_session.add(SubjectTeacher(
        school_id=school.id, class_id=other_class.id, subject_id=subject.id,
        staff_member_id=staff.id, academic_year_id=academic_year.id, is_active=True,
    ))
    await _assign_class(db_session, school, other_student, other_class, academic_year)

    scope = await resolve_student_view_scope(user.id, school.id, db_session)
    assert scope == {student.id}, (
        "only the ClassTeacher-owned class's student should be visible — "
        "the SubjectTeacher-only class's student must not leak in"
    )


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


# ── resolve_term_enrollment_scope ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_term_enrollment_scope_exact_set_for_class_teacher(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_year: AcademicYear, redis_permissions: None,
):
    staff, user = await _make_staff_with_position(db_session, school, "CLASS_TEACHER", "TE1")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    scope = await resolve_term_enrollment_scope(user.id, academic_year.id, db_session)
    assert scope == {school_class.id}


@pytest.mark.asyncio
async def test_term_enrollment_scope_exact_set_for_subject_teacher_only(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_year: AcademicYear, redis_permissions: None,
):
    """Wider than resolve_class_teacher_scope — a subject teacher with no
    ClassTeacher row of their own is still in scope, since they have a
    legitimate reason (entering scores) to register a present student."""
    from app.models.academic import SchoolLevel, Subject, SubjectCatalogue, SubjectType

    staff, user = await _make_staff_with_position(db_session, school, "TEACHER", "TE2")
    cat = SubjectCatalogue(name="Test Subject", code="TERM_SCOPE1", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code="TERM_SCOPE1", name="Test Subject", is_active=True)
    db_session.add(subj)
    await db_session.flush()

    db_session.add(SubjectTeacher(
        school_id=school.id, class_id=school_class.id, subject_id=subj.id,
        staff_member_id=staff.id, academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    scope = await resolve_term_enrollment_scope(user.id, academic_year.id, db_session)
    assert scope == {school_class.id}


@pytest.mark.asyncio
async def test_term_enrollment_scope_union_when_both(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_year: AcademicYear, redis_permissions: None,
):
    from app.models.academic import SchoolLevel, Subject, SubjectCatalogue, SubjectType

    other_class = Class(school_id=school.id, level="SHS", year_group=1, stream="C", is_active=True)
    db_session.add(other_class)
    await db_session.flush()

    staff, user = await _make_staff_with_position(db_session, school, "CLASS_TEACHER", "TE3")
    cat = SubjectCatalogue(name="Test Subject", code="TERM_SCOPE2", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code="TERM_SCOPE2", name="Test Subject", is_active=True)
    db_session.add(subj)
    await db_session.flush()

    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    db_session.add(SubjectTeacher(
        school_id=school.id, class_id=other_class.id, subject_id=subj.id,
        staff_member_id=staff.id, academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    scope = await resolve_term_enrollment_scope(user.id, academic_year.id, db_session)
    assert scope == {school_class.id, other_class.id}


@pytest.mark.asyncio
async def test_term_enrollment_scope_none_for_deputy_head(
    db_session: AsyncSession, school: School, academic_year: AcademicYear, redis_permissions: None,
):
    _staff, user = await _make_staff_with_position(db_session, school, "DEPUTY_HEAD", "TE4")
    scope = await resolve_term_enrollment_scope(user.id, academic_year.id, db_session)
    assert scope is None


@pytest.mark.asyncio
async def test_term_enrollment_scope_empty_not_none_with_zero_assignments(
    db_session: AsyncSession, school: School, academic_year: AcademicYear, redis_permissions: None,
):
    _staff, user = await _make_staff_with_position(db_session, school, "CLASS_TEACHER", "TE5")
    scope = await resolve_term_enrollment_scope(user.id, academic_year.id, db_session)
    assert scope == set()


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
