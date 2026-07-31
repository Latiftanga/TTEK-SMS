"""
ClassSubject.is_elective + bulk_register_core_subjects() — lets a class
register every actively-enrolled student for its non-elective subjects in
one action, instead of the fully manual, one-student-at-a-time flow.
Electives are deliberately never touched by the bulk action; a student
needing an exemption from an otherwise-universal subject (e.g. a disability
exemption) is handled by removing their registration afterward via the
existing delete_subject_registration endpoint, not a separate mechanism.

Run inside Docker: docker compose exec api pytest app/tests/test_subject_bulk_registration.py -v
"""
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import (
    AcademicTerm, AcademicYear, Class, ClassSubject,
    SchoolLevel, Subject, SubjectCatalogue, SubjectType,
)
from app.models.auth import LoginType, StaffPosition, User
from app.models.school import School
from app.models.students import Student, StudentClassAssignment, SubjectRegistration, TermEnrollment


async def _login_as_position(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, position_code: str,
) -> dict:
    """Create a staff member holding `position_code`, give them a login, and return
    their bearer-token auth headers — mirrors test_scoring_lock.py's helper."""
    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == position_code))
    assert pos is not None, "Run seed_reference_data.py first"

    staff_id = (await client.post("/staff", json={
        "staff_number": f"TST-{position_code}", "first_name": "Test", "last_name": position_code.title(),
    }, headers=auth)).json()["id"]
    await client.patch(f"/staff/{staff_id}", json={"position_ids": [str(pos.id)]}, headers=auth)

    email = f"{position_code.lower()}@presec-test.edu.gh"
    db_session.add(User(
        school_id=school.id, login_type=LoginType.EMAIL, email=email,
        password_hash=hash_password("Whatever123!"), is_active=True, staff_member_id=staff_id,
    ))
    await db_session.flush()

    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL", "identifier": email, "password": "Whatever123!",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _make_subject(db_session: AsyncSession, school: School, code: str, name: str) -> Subject:
    cat = SubjectCatalogue(name=name, code=code, subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code=code, name=name, is_active=True)
    db_session.add(subj)
    await db_session.flush()
    return subj


async def _enroll_student(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_year: AcademicYear, academic_term: AcademicTerm, enrolled_by_id, suffix: str,
    *, term_enrolled: bool = True,
) -> tuple[Student, TermEnrollment | None]:
    student = Student(
        school_id=school.id, admission_number=f"BULK{suffix}", first_name="Test", last_name=suffix, is_active=True,
    )
    db_session.add(student)
    await db_session.flush()
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=school_class.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()
    te = None
    if term_enrolled:
        te = TermEnrollment(
            school_id=school.id, student_id=student.id, academic_term_id=academic_term.id,
            enrolled_by_id=enrolled_by_id, is_active=True,
        )
        db_session.add(te)
        await db_session.flush()
    return student, te


@pytest.fixture
async def math_subject(db_session: AsyncSession, school: School, school_class: Class) -> Subject:
    subj = await _make_subject(db_session, school, "MATH_BULK", "Mathematics")
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subj.id, is_active=True))
    await db_session.flush()
    return subj


@pytest.fixture
async def french_elective(db_session: AsyncSession, school: School, school_class: Class) -> Subject:
    subj = await _make_subject(db_session, school, "FR_BULK", "French")
    db_session.add(ClassSubject(
        school_id=school.id, class_id=school_class.id, subject_id=subj.id, is_active=True, is_elective=True,
    ))
    await db_session.flush()
    return subj


# ── is_elective toggle ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_class_subject_toggle_persists(
    client: AsyncClient, auth: dict, school_class: Class, math_subject: Subject,
):
    resp = await client.patch(
        f"/academic/classes/{school_class.id}/subjects/{math_subject.id}",
        json={"is_elective": True}, headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["is_elective"] is True

    listed = await client.get(f"/academic/classes/{school_class.id}/subjects", headers=auth)
    row = next(r for r in listed.json() if r["subject_id"] == str(math_subject.id))
    assert row["is_elective"] is True


@pytest.mark.asyncio
async def test_update_class_subject_404_when_not_assigned(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school_class: Class, school: School,
):
    """A subject that's never been assigned to this class (no ClassSubject
    row) has nothing to toggle — 404, not a silent no-op."""
    orphan = Subject(school_id=school.id, code="ORPHAN_BULK", name="Orphan Subject", is_active=True)
    db_session.add(orphan)
    await db_session.flush()

    resp = await client.patch(
        f"/academic/classes/{school_class.id}/subjects/{orphan.id}",
        json={"is_elective": True}, headers=auth,
    )
    assert resp.status_code == 404


# ── Bulk register core subjects ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_register_only_non_elective_subjects(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm,
    math_subject: Subject, french_elective: Subject,
):
    s1, te1 = await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "A")
    s2, te2 = await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "B")

    resp = await client.post(
        f"/students/classes/{school_class.id}/subjects/bulk-register-core",
        json={"academic_term_id": str(academic_term.id)}, headers=auth,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["registered"] == 2
    assert data["skipped"] == 0

    for te in (te1, te2):
        regs = (await db_session.scalars(
            select(SubjectRegistration).where(SubjectRegistration.term_enrollment_id == te.id)
        )).all()
        subject_ids = {r.subject_id for r in regs}
        assert subject_ids == {math_subject.id}   # french (elective) never touched
        assert all(r.registration_type == "CORE" for r in regs)


@pytest.mark.asyncio
async def test_bulk_register_skips_students_not_term_enrolled(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm, math_subject: Subject,
):
    await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "C")
    await _enroll_student(
        db_session, school, school_class, academic_year, academic_term, school_admin.id, "D", term_enrolled=False,
    )

    resp = await client.post(
        f"/students/classes/{school_class.id}/subjects/bulk-register-core",
        json={"academic_term_id": str(academic_term.id)}, headers=auth,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["registered"] == 1
    assert data["skipped"] == 1


@pytest.mark.asyncio
async def test_bulk_register_is_idempotent(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm, math_subject: Subject,
):
    _s, te = await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "E")

    for _ in range(2):
        resp = await client.post(
            f"/students/classes/{school_class.id}/subjects/bulk-register-core",
            json={"academic_term_id": str(academic_term.id)}, headers=auth,
        )
        assert resp.status_code == 200
        assert resp.json()["registered"] == 1

    regs = (await db_session.scalars(
        select(SubjectRegistration).where(
            SubjectRegistration.term_enrollment_id == te.id, SubjectRegistration.subject_id == math_subject.id,
        )
    )).all()
    assert len(regs) == 1   # no duplicate row from the second run


@pytest.mark.asyncio
async def test_bulk_register_no_core_subjects_is_a_noop(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm, french_elective: Subject,
):
    """A class whose only assigned subject is an elective has nothing to
    bulk-register — must not error, just report zero."""
    await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "F")

    resp = await client.post(
        f"/students/classes/{school_class.id}/subjects/bulk-register-core",
        json={"academic_term_id": str(academic_term.id)}, headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json() == {"registered": 0, "skipped": 0}


@pytest.mark.asyncio
async def test_bulk_register_then_manual_exemption_leaves_others_untouched(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm, math_subject: Subject,
):
    """The disability-exemption case: bulk-register the whole class, then
    remove one student's registration for the (otherwise universal) core
    subject via the existing per-student endpoint — the rest are unaffected."""
    exempt_student, exempt_te = await _enroll_student(
        db_session, school, school_class, academic_year, academic_term, school_admin.id, "G",
    )
    _other, other_te = await _enroll_student(
        db_session, school, school_class, academic_year, academic_term, school_admin.id, "H",
    )

    await client.post(
        f"/students/classes/{school_class.id}/subjects/bulk-register-core",
        json={"academic_term_id": str(academic_term.id)}, headers=auth,
    )

    exempt_reg = await db_session.scalar(
        select(SubjectRegistration).where(SubjectRegistration.term_enrollment_id == exempt_te.id)
    )
    resp = await client.delete(
        f"/students/term-enrollments/{exempt_te.id}/subjects/{exempt_reg.id}", headers=auth,
    )
    assert resp.status_code == 204

    assert await db_session.scalar(
        select(SubjectRegistration).where(SubjectRegistration.term_enrollment_id == exempt_te.id)
    ) is None
    assert await db_session.scalar(
        select(SubjectRegistration).where(
            SubjectRegistration.term_enrollment_id == other_te.id, SubjectRegistration.subject_id == math_subject.id,
        )
    ) is not None


# ── Term lock ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_register_blocked_when_term_locked_without_reason(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm, math_subject: Subject,
):
    await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "I")
    academic_term.results_locked = True
    await db_session.flush()

    resp = await client.post(
        f"/students/classes/{school_class.id}/subjects/bulk-register-core",
        json={"academic_term_id": str(academic_term.id)}, headers=auth,
    )
    assert resp.status_code == 423


@pytest.mark.asyncio
async def test_bulk_register_allowed_when_locked_with_reason(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm, math_subject: Subject,
):
    await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "J")
    academic_term.results_locked = True
    await db_session.flush()

    resp = await client.post(
        f"/students/classes/{school_class.id}/subjects/bulk-register-core",
        json={
            "academic_term_id": str(academic_term.id),
            "override_reason": "Late registration approved by exams office.",
        },
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["registered"] == 1


@pytest.mark.asyncio
async def test_bulk_register_reason_alone_insufficient_without_permission(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm, math_subject: Subject,
    redis_permissions: None,
):
    """A class teacher (students.edit, no assessments.approve_scores) can't
    push a reason through on their own — matches register_subjects' own
    behaviour, which this bulk action is built on top of."""
    await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "K")
    academic_term.results_locked = True
    await db_session.flush()

    teacher_auth = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    resp = await client.post(
        f"/students/classes/{school_class.id}/subjects/bulk-register-core",
        json={
            "academic_term_id": str(academic_term.id),
            "override_reason": "I really need to register this class.",
        },
        headers=teacher_auth,
    )
    assert resp.status_code == 423


# ── Per-subject roster (get_subject_roster / set_subject_roster) ──────────────

@pytest.mark.asyncio
async def test_get_roster_reflects_registration_and_enrollment_state(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm, math_subject: Subject,
):
    registered, _te1 = await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "L")
    unregistered, _te2 = await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "M")
    not_enrolled, _none = await _enroll_student(
        db_session, school, school_class, academic_year, academic_term, school_admin.id, "N", term_enrolled=False,
    )

    await client.post(
        f"/students/classes/{school_class.id}/subjects/{math_subject.id}/roster",
        json={"academic_term_id": str(academic_term.id), "student_ids": [str(registered.id)]}, headers=auth,
    )

    resp = await client.get(
        f"/students/classes/{school_class.id}/subjects/{math_subject.id}/roster",
        params={"academic_term_id": str(academic_term.id)}, headers=auth,
    )
    assert resp.status_code == 200
    by_id = {row["student_id"]: row for row in resp.json()}

    assert by_id[str(registered.id)]["enrolled"] is True
    assert by_id[str(registered.id)]["is_registered"] is True
    assert by_id[str(registered.id)]["registration_id"] is not None

    assert by_id[str(unregistered.id)]["enrolled"] is True
    assert by_id[str(unregistered.id)]["is_registered"] is False
    assert by_id[str(unregistered.id)]["registration_id"] is None

    assert by_id[str(not_enrolled.id)]["enrolled"] is False
    assert by_id[str(not_enrolled.id)]["is_registered"] is False


@pytest.mark.asyncio
async def test_set_roster_registers_checked_and_removes_unchecked(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm, math_subject: Subject,
):
    s1, te1 = await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "O")
    s2, te2 = await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "P")

    # First pass: check both.
    resp = await client.post(
        f"/students/classes/{school_class.id}/subjects/{math_subject.id}/roster",
        json={"academic_term_id": str(academic_term.id), "student_ids": [str(s1.id), str(s2.id)]}, headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json() == {"registered": 2, "removed": 0, "skipped": 0}

    # Second pass: uncheck s1, leave s2 checked — s1 must be removed, s2 untouched.
    resp = await client.post(
        f"/students/classes/{school_class.id}/subjects/{math_subject.id}/roster",
        json={"academic_term_id": str(academic_term.id), "student_ids": [str(s2.id)]}, headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json() == {"registered": 0, "removed": 1, "skipped": 0}

    assert await db_session.scalar(
        select(SubjectRegistration).where(SubjectRegistration.term_enrollment_id == te1.id)
    ) is None
    assert await db_session.scalar(
        select(SubjectRegistration).where(SubjectRegistration.term_enrollment_id == te2.id)
    ) is not None


@pytest.mark.asyncio
async def test_set_roster_uses_class_subjects_elective_flag_not_caller_choice(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm, french_elective: Subject,
):
    """registration_type is derived from ClassSubject.is_elective, never a
    caller-supplied value — the request schema doesn't even accept one."""
    s1, te1 = await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "Q")

    resp = await client.post(
        f"/students/classes/{school_class.id}/subjects/{french_elective.id}/roster",
        json={"academic_term_id": str(academic_term.id), "student_ids": [str(s1.id)]}, headers=auth,
    )
    assert resp.status_code == 200

    reg = await db_session.scalar(
        select(SubjectRegistration).where(SubjectRegistration.term_enrollment_id == te1.id)
    )
    assert reg.registration_type == "ELECTIVE"


@pytest.mark.asyncio
async def test_set_roster_skips_checked_student_not_term_enrolled(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm, math_subject: Subject,
):
    not_enrolled, _none = await _enroll_student(
        db_session, school, school_class, academic_year, academic_term, school_admin.id, "R", term_enrolled=False,
    )

    resp = await client.post(
        f"/students/classes/{school_class.id}/subjects/{math_subject.id}/roster",
        json={"academic_term_id": str(academic_term.id), "student_ids": [str(not_enrolled.id)]}, headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json() == {"registered": 0, "removed": 0, "skipped": 1}


@pytest.mark.asyncio
async def test_set_roster_is_isolated_per_subject(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm,
    math_subject: Subject, french_elective: Subject,
):
    """Registering/unregistering a student for one subject must have zero
    effect on their registration for a different subject — the whole point
    of scoping this action per-subject instead of per-class."""
    s1, te1 = await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "S")

    await client.post(
        f"/students/classes/{school_class.id}/subjects/{math_subject.id}/roster",
        json={"academic_term_id": str(academic_term.id), "student_ids": [str(s1.id)]}, headers=auth,
    )
    await client.post(
        f"/students/classes/{school_class.id}/subjects/{french_elective.id}/roster",
        json={"academic_term_id": str(academic_term.id), "student_ids": [str(s1.id)]}, headers=auth,
    )

    # Now unregister from French only.
    resp = await client.post(
        f"/students/classes/{school_class.id}/subjects/{french_elective.id}/roster",
        json={"academic_term_id": str(academic_term.id), "student_ids": []}, headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json() == {"registered": 0, "removed": 1, "skipped": 0}

    regs = (await db_session.scalars(
        select(SubjectRegistration).where(SubjectRegistration.term_enrollment_id == te1.id)
    )).all()
    subject_ids = {r.subject_id for r in regs}
    assert subject_ids == {math_subject.id}   # French removed, Math untouched


@pytest.mark.asyncio
async def test_set_roster_blocked_when_term_locked_without_reason(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm, math_subject: Subject,
):
    s1, _te1 = await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "T")
    academic_term.results_locked = True
    await db_session.flush()

    resp = await client.post(
        f"/students/classes/{school_class.id}/subjects/{math_subject.id}/roster",
        json={"academic_term_id": str(academic_term.id), "student_ids": [str(s1.id)]}, headers=auth,
    )
    assert resp.status_code == 423


@pytest.mark.asyncio
async def test_set_roster_allowed_when_locked_with_reason(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm, math_subject: Subject,
):
    s1, _te1 = await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "U")
    academic_term.results_locked = True
    await db_session.flush()

    resp = await client.post(
        f"/students/classes/{school_class.id}/subjects/{math_subject.id}/roster",
        json={
            "academic_term_id": str(academic_term.id), "student_ids": [str(s1.id)],
            "override_reason": "Late correction approved by exams office.",
        },
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["registered"] == 1
