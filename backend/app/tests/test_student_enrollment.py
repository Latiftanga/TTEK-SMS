"""
Student enrollment integration tests — initial enrollment, term enrollment,
subject registration, and transfer requests.
Run inside Docker: docker compose exec api pytest app/tests/test_student_enrollment.py -v
"""
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import AcademicTerm, Class
from app.models.auth import LoginType, StaffPosition, User
from app.models.fees import StudentFeeRecord
from app.models.school import School
from app.models.staff import StaffMember
from app.models.students import Student, TermEnrollment


async def _assign_subject_teacher(
    db_session: AsyncSession, school: School, class_id, subject_id, academic_year_id, suffix: str,
) -> None:
    """Registration now requires someone assigned to teach the subject
    (services/subject_roster.py::subject_teacher_assigned) — who the
    teacher is doesn't matter for tests not about that scoping itself."""
    from app.models.academic import SubjectTeacher

    staff = StaffMember(school_id=school.id, staff_number=f"ENRTCH-{suffix}", first_name="Teach", last_name=suffix)
    db_session.add(staff)
    await db_session.flush()
    db_session.add(SubjectTeacher(
        school_id=school.id, class_id=class_id, subject_id=subject_id,
        staff_member_id=staff.id, academic_year_id=academic_year_id, is_active=True,
    ))
    await db_session.flush()


async def _assign_class(client, auth, student_id: str, school_class: Class, academic_term: AcademicTerm):
    """Create a StudentClassAssignment before enrolling for a term."""
    resp = await client.post("/students/class-assignments", json={
        "student_id": student_id,
        "class_id": str(school_class.id),
        "academic_year_id": str(academic_term.academic_year_id),
    }, headers=auth)
    assert resp.status_code == 201
    return resp.json()


async def _create_student(client, auth, num="ADM001"):
    resp = await client.post("/students", json={
        "admission_number": num, "first_name": "Kwame", "last_name": "Asante",
    }, headers=auth)
    assert resp.status_code == 201
    return resp.json()["id"]


async def _login_as_position(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, position_code: str,
) -> dict:
    """Create a staff member holding `position_code`, give them a login, and return
    their bearer-token auth headers."""
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
        "school_code": school.school_code,
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Initial enrollment ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_initial_enrollment(client: AsyncClient, auth: dict):
    sid = await _create_student(client, auth)
    resp = await client.post(f"/students/{sid}/enroll", json={
        "enrolled_at": "2024-09-02",
        "enrollment_type": "NEW",
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["enrollment_type"] == "NEW"


@pytest.mark.asyncio
async def test_transfer_enrollment_records_source_school(client: AsyncClient, auth: dict):
    sid = await _create_student(client, auth)
    resp = await client.post(f"/students/{sid}/enroll", json={
        "enrolled_at": "2024-09-02",
        "enrollment_type": "TRANSFER",
        "transfer_from_school": "Accra Academy",
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["transfer_from_school"] == "Accra Academy"


# ── Term enrollment ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_class_assignment(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
):
    sid = await _create_student(client, auth)
    data = await _assign_class(client, auth, sid, school_class, academic_term)
    assert data["student_id"] == sid
    assert data["class_id"] == str(school_class.id)
    assert "class_display_name" in data
    assert data["class_display_name"]


@pytest.mark.asyncio
async def test_duplicate_class_assignment_rejected(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
):
    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    resp = await client.post("/students/class-assignments", json={
        "student_id": sid,
        "class_id": str(school_class.id),
        "academic_year_id": str(academic_term.academic_year_id),
    }, headers=auth)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_term_enrollment(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
):
    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    resp = await client.post("/students/term-enrollments", json={
        "student_id": sid,
        "academic_term_id": str(academic_term.id),
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["student_id"] == sid
    assert "class_display_name" in data
    assert data["class_display_name"]  # derived from StudentClassAssignment


@pytest.mark.asyncio
async def test_term_enrollment_requires_class_assignment(
    client: AsyncClient, auth: dict,
    academic_term: AcademicTerm,
):
    sid = await _create_student(client, auth)
    resp = await client.post("/students/term-enrollments", json={
        "student_id": sid,
        "academic_term_id": str(academic_term.id),
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_term_enrollment_rejected(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
):
    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    payload = {"student_id": sid, "academic_term_id": str(academic_term.id)}
    await client.post("/students/term-enrollments", json=payload, headers=auth)
    resp = await client.post("/students/term-enrollments", json=payload, headers=auth)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_term_enrollments(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
):
    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    await client.post("/students/term-enrollments", json={
        "student_id": sid,
        "academic_term_id": str(academic_term.id),
    }, headers=auth)
    resp = await client.get(f"/students/{sid}/term-enrollments", headers=auth)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_list_students_by_class(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
):
    sid1 = await _create_student(client, auth, "ADM001")
    sid2 = await _create_student(client, auth, "ADM002")
    # Assign only sid1 to the class
    await _assign_class(client, auth, sid1, school_class, academic_term)
    resp = await client.get(
        f"/students?class_id={school_class.id}",
        headers=auth,
    )
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert sid1 in ids
    assert sid2 not in ids


# ── Subject registration ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_subjects(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
    db_session: AsyncSession, school: School,
):
    from app.models.academic import ClassSubject, Subject
    sub = Subject(school_id=school.id, code="MATH01", name="Mathematics", is_active=True)
    db_session.add(sub)
    await db_session.flush()
    # register_subjects requires subject_id to be an active ClassSubject on
    # the student's class (services/subject_roster.py::class_subject_exists).
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=sub.id, is_active=True))
    await db_session.flush()
    await _assign_subject_teacher(db_session, school, school_class.id, sub.id, academic_term.academic_year_id, "REG")

    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    te_id = (await client.post("/students/term-enrollments", json={
        "student_id": sid,
        "academic_term_id": str(academic_term.id),
    }, headers=auth)).json()["id"]

    resp = await client.post(f"/students/term-enrollments/{te_id}/subjects", json={"items": [
        {"subject_id": str(sub.id), "registration_type": "CORE"},
    ]}, headers=auth)
    assert resp.status_code == 201
    assert len(resp.json()) == 1
    assert resp.json()[0]["registration_type"] == "CORE"


@pytest.mark.asyncio
async def test_duplicate_subject_skipped_silently(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
    db_session: AsyncSession, school: School,
):
    from app.models.academic import ClassSubject, Subject
    sub = Subject(school_id=school.id, code="ENG01", name="English", is_active=True)
    db_session.add(sub)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=sub.id, is_active=True))
    await db_session.flush()
    await _assign_subject_teacher(db_session, school, school_class.id, sub.id, academic_term.academic_year_id, "DUP")

    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    te_id = (await client.post("/students/term-enrollments", json={
        "student_id": sid,
        "academic_term_id": str(academic_term.id),
    }, headers=auth)).json()["id"]

    await client.post(f"/students/term-enrollments/{te_id}/subjects", json={"items": [
        {"subject_id": str(sub.id), "registration_type": "CORE"},
    ]}, headers=auth)
    # Register same subject again — should silently skip
    resp = await client.post(f"/students/term-enrollments/{te_id}/subjects", json={"items": [
        {"subject_id": str(sub.id), "registration_type": "CORE"},
    ]}, headers=auth)
    assert resp.status_code == 201
    assert resp.json() == []   # nothing new registered


@pytest.mark.asyncio
async def test_register_subject_not_on_class_rejected(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
    db_session: AsyncSession, school: School,
):
    """A subject never assigned to the class (no ClassSubject row) can't be
    registered for a student in that class — mirrors create_assessment's
    guard from 12q."""
    from app.models.academic import Subject
    orphan = Subject(school_id=school.id, code="ORPHAN01", name="Nobody's Subject", is_active=True)
    db_session.add(orphan)
    await db_session.flush()

    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    te_id = (await client.post("/students/term-enrollments", json={
        "student_id": sid,
        "academic_term_id": str(academic_term.id),
    }, headers=auth)).json()["id"]

    resp = await client.post(f"/students/term-enrollments/{te_id}/subjects", json={"items": [
        {"subject_id": str(orphan.id), "registration_type": "CORE"},
    ]}, headers=auth)
    assert resp.status_code == 422
    assert "not assigned" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_register_subject_rejected_when_no_teacher_assigned(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
    db_session: AsyncSession, school: School,
):
    """A subject can sit on a class's curriculum (ClassSubject) before anyone
    is assigned to teach it — registering a student for it doesn't make
    sense until someone is."""
    from app.models.academic import ClassSubject, Subject
    sub = Subject(school_id=school.id, code="NOTEACH01", name="No Teacher Yet", is_active=True)
    db_session.add(sub)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=sub.id, is_active=True))
    await db_session.flush()
    # Deliberately no SubjectTeacher row.

    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    te_id = (await client.post("/students/term-enrollments", json={
        "student_id": sid,
        "academic_term_id": str(academic_term.id),
    }, headers=auth)).json()["id"]

    resp = await client.post(f"/students/term-enrollments/{te_id}/subjects", json={"items": [
        {"subject_id": str(sub.id), "registration_type": "CORE"},
    ]}, headers=auth)
    assert resp.status_code == 422
    assert "no teacher assigned" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_register_subject_allowed_once_teacher_assigned(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
    db_session: AsyncSession, school: School,
):
    from app.models.academic import ClassSubject, Subject
    sub = Subject(school_id=school.id, code="NOTEACH02", name="Teacher Assigned Later", is_active=True)
    db_session.add(sub)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=sub.id, is_active=True))
    await db_session.flush()

    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    te_id = (await client.post("/students/term-enrollments", json={
        "student_id": sid,
        "academic_term_id": str(academic_term.id),
    }, headers=auth)).json()["id"]

    resp = await client.post(f"/students/term-enrollments/{te_id}/subjects", json={"items": [
        {"subject_id": str(sub.id), "registration_type": "CORE"},
    ]}, headers=auth)
    assert resp.status_code == 422

    await _assign_subject_teacher(db_session, school, school_class.id, sub.id, academic_term.academic_year_id, "NOTEACH02")
    resp = await client.post(f"/students/term-enrollments/{te_id}/subjects", json={"items": [
        {"subject_id": str(sub.id), "registration_type": "CORE"},
    ]}, headers=auth)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_register_subjects_rejects_deactivated_term_enrollment(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
    db_session: AsyncSession, school: School,
):
    """A withdrawn/transferred student's TermEnrollment is deactivated (not
    deleted) by student_lifecycle.py — subjects must not be registerable
    against it afterward."""
    from app.models.academic import ClassSubject, Subject
    sub = Subject(school_id=school.id, code="WD01", name="Withdrawn Test Subject", is_active=True)
    db_session.add(sub)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=sub.id, is_active=True))
    await db_session.flush()

    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    te_id = (await client.post("/students/term-enrollments", json={
        "student_id": sid,
        "academic_term_id": str(academic_term.id),
    }, headers=auth)).json()["id"]

    te = await db_session.get(TermEnrollment, te_id)
    te.is_active = False
    await db_session.flush()

    resp = await client.post(f"/students/term-enrollments/{te_id}/subjects", json={"items": [
        {"subject_id": str(sub.id), "registration_type": "CORE"},
    ]}, headers=auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_register_subjects_rejected_when_class_deactivated(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
    db_session: AsyncSession, school: School,
):
    """A class retired (Class.is_active=False) after a student was already
    assigned to it must stop accepting new subject registrations — same
    reasoning as a locked term, just for the class itself rather than the
    term (services/academic_class.py::get_active_class)."""
    from app.models.academic import ClassSubject, Subject
    sub = Subject(school_id=school.id, code="INACT01", name="Inactive Class Test Subject", is_active=True)
    db_session.add(sub)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=sub.id, is_active=True))
    await db_session.flush()
    await _assign_subject_teacher(db_session, school, school_class.id, sub.id, academic_term.academic_year_id, "INACT01")

    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    te_id = (await client.post("/students/term-enrollments", json={
        "student_id": sid,
        "academic_term_id": str(academic_term.id),
    }, headers=auth)).json()["id"]

    resp = await client.patch(f"/academic/classes/{school_class.id}", json={"is_active": False}, headers=auth)
    assert resp.status_code == 200

    resp = await client.post(f"/students/term-enrollments/{te_id}/subjects", json={"items": [
        {"subject_id": str(sub.id), "registration_type": "CORE"},
    ]}, headers=auth)
    assert resp.status_code == 422
    assert "inactive" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_class_assignment_rejected_on_inactive_class(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
    db_session: AsyncSession,
):
    """A retired class shouldn't gain new members either — the failure this
    session started from (assigning subjects to an inactive class) had the
    same root gap one step earlier, at class assignment itself."""
    resp = await client.patch(f"/academic/classes/{school_class.id}", json={"is_active": False}, headers=auth)
    assert resp.status_code == 200

    sid = await _create_student(client, auth)
    resp = await client.post("/students/class-assignments", json={
        "student_id": sid,
        "class_id": str(school_class.id),
        "academic_year_id": str(academic_term.academic_year_id),
    }, headers=auth)
    assert resp.status_code == 422
    assert "inactive" in resp.json()["detail"].lower()


# ── Category B scoping (class teacher OR the specific subject's teacher) ──────

@pytest.mark.asyncio
async def test_register_subjects_404_for_unrelated_teacher(
    client: AsyncClient, auth: dict, school_class: Class, academic_term: AcademicTerm,
    db_session: AsyncSession, school: School, redis_permissions: None,
):
    from app.models.academic import ClassSubject, Subject
    sub = Subject(school_id=school.id, code="SCOPE01", name="Scope Test Subject", is_active=True)
    db_session.add(sub)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=sub.id, is_active=True))
    await db_session.flush()

    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    te_id = (await client.post("/students/term-enrollments", json={
        "student_id": sid, "academic_term_id": str(academic_term.id),
    }, headers=auth)).json()["id"]

    # No ClassTeacher/SubjectTeacher assignment anywhere for this staff member.
    teacher_auth = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    resp = await client.post(f"/students/term-enrollments/{te_id}/subjects", json={"items": [
        {"subject_id": str(sub.id), "registration_type": "CORE"},
    ]}, headers=teacher_auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_register_subjects_allowed_for_own_subject_teacher(
    client: AsyncClient, auth: dict, school_class: Class, academic_term: AcademicTerm,
    db_session: AsyncSession, school: School, redis_permissions: None,
):
    """A SubjectTeacher (no ClassTeacher row) may register their own subject,
    but not a different one in the same class."""
    from app.models.academic import ClassSubject, Subject, SubjectTeacher

    own_subject = Subject(school_id=school.id, code="SCOPE02", name="Own Subject", is_active=True)
    other_subject = Subject(school_id=school.id, code="SCOPE03", name="Other Subject", is_active=True)
    db_session.add_all([own_subject, other_subject])
    await db_session.flush()
    db_session.add_all([
        ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=own_subject.id, is_active=True),
        ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=other_subject.id, is_active=True),
    ])
    await db_session.flush()

    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    te_id = (await client.post("/students/term-enrollments", json={
        "student_id": sid, "academic_term_id": str(academic_term.id),
    }, headers=auth)).json()["id"]

    teacher_auth = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    teacher_user = await db_session.scalar(
        select(User).where(User.email == "class_teacher@presec-test.edu.gh")
    )
    db_session.add(SubjectTeacher(
        school_id=school.id, class_id=school_class.id, subject_id=own_subject.id,
        staff_member_id=teacher_user.staff_member_id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.post(f"/students/term-enrollments/{te_id}/subjects", json={"items": [
        {"subject_id": str(own_subject.id), "registration_type": "CORE"},
    ]}, headers=teacher_auth)
    assert resp.status_code == 201

    resp = await client.post(f"/students/term-enrollments/{te_id}/subjects", json={"items": [
        {"subject_id": str(other_subject.id), "registration_type": "CORE"},
    ]}, headers=teacher_auth)
    assert resp.status_code == 404


@pytest.fixture
async def locked_term_setup(client: AsyncClient, auth: dict, school_class: Class, academic_term: AcademicTerm, db_session: AsyncSession, school: School):
    """A registered subject, a term enrollment, and the term locked afterward —
    the state every 'already past' term-lock test starts from."""
    from app.models.academic import ClassSubject, Subject
    sub = Subject(school_id=school.id, code="LOCK01", name="Locked Term Subject", is_active=True)
    db_session.add(sub)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=sub.id, is_active=True))
    await db_session.flush()
    await _assign_subject_teacher(db_session, school, school_class.id, sub.id, academic_term.academic_year_id, "LOCK01")

    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    te_id = (await client.post("/students/term-enrollments", json={
        "student_id": sid, "academic_term_id": str(academic_term.id),
    }, headers=auth)).json()["id"]
    reg_id = (await client.post(f"/students/term-enrollments/{te_id}/subjects", json={"items": [
        {"subject_id": str(sub.id), "registration_type": "CORE"},
    ]}, headers=auth)).json()[0]["id"]

    academic_term.results_locked = True
    await db_session.flush()
    return te_id, reg_id, sub


@pytest.mark.asyncio
async def test_register_subject_blocked_when_term_locked_without_reason(
    client: AsyncClient, auth: dict, locked_term_setup, db_session: AsyncSession,
    school: School, school_class: Class,
):
    """It shouldn't be possible to add a subject to a term enrollment that's
    already been finalized — mirrors scoring.py's own term-lock behaviour."""
    from app.models.academic import ClassSubject, Subject
    te_id, _reg_id, _sub = locked_term_setup
    other = Subject(school_id=school.id, code="LOCK02", name="Another Subject", is_active=True)
    db_session.add(other)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=other.id, is_active=True))
    await db_session.flush()

    resp = await client.post(f"/students/term-enrollments/{te_id}/subjects", json={"items": [
        {"subject_id": str(other.id), "registration_type": "CORE"},
    ]}, headers=auth)
    assert resp.status_code == 423


@pytest.mark.asyncio
async def test_register_subject_allowed_when_locked_with_reason_and_permission(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_term: AcademicTerm, redis_permissions: None,
):
    from app.models.academic import ClassSubject, Subject
    sub = Subject(school_id=school.id, code="LOCK03", name="Override Subject", is_active=True)
    db_session.add(sub)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=sub.id, is_active=True))
    await db_session.flush()
    await _assign_subject_teacher(db_session, school, school_class.id, sub.id, academic_term.academic_year_id, "LOCK03")

    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    te_id = (await client.post("/students/term-enrollments", json={
        "student_id": sid, "academic_term_id": str(academic_term.id),
    }, headers=auth)).json()["id"]

    academic_term.results_locked = True
    await db_session.flush()

    hod_auth = await _login_as_position(client, auth, db_session, school, "HOD")
    resp = await client.post(f"/students/term-enrollments/{te_id}/subjects", json={
        "items": [{"subject_id": str(sub.id), "registration_type": "CORE"}],
        "override_reason": "Late correction approved by exams office",
    }, headers=hod_auth)
    assert resp.status_code == 201
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_register_subject_reason_alone_insufficient_without_permission(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_term: AcademicTerm, redis_permissions: None,
):
    """A class teacher (students.edit, no assessments.approve_scores) can't
    push a reason through on their own — matches submit_scores' behaviour."""
    from app.models.academic import ClassSubject, Subject
    sub = Subject(school_id=school.id, code="LOCK04", name="No Permission Subject", is_active=True)
    db_session.add(sub)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=sub.id, is_active=True))
    await db_session.flush()

    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    te_id = (await client.post("/students/term-enrollments", json={
        "student_id": sid, "academic_term_id": str(academic_term.id),
    }, headers=auth)).json()["id"]

    academic_term.results_locked = True
    await db_session.flush()

    teacher_auth = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    # Give the teacher an actual ClassTeacher assignment on this class, so the
    # request clears core/student_scope.py's Category B scoping check and
    # this test can isolate the term-lock-permission behaviour it's actually
    # about (otherwise it would now 404 on scope before ever reaching the
    # term-lock check).
    from app.models.academic import ClassTeacher
    teacher_user = await db_session.scalar(
        select(User).where(User.email == "class_teacher@presec-test.edu.gh")
    )
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=teacher_user.staff_member_id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.post(f"/students/term-enrollments/{te_id}/subjects", json={
        "items": [{"subject_id": str(sub.id), "registration_type": "CORE"}],
        "override_reason": "I really need to add this",
    }, headers=teacher_auth)
    assert resp.status_code == 423


@pytest.mark.asyncio
async def test_delete_subject_registration_blocked_when_term_locked(
    client: AsyncClient, auth: dict, locked_term_setup,
):
    """Removing a subject from an already-finalized term is just as
    nonsensical as adding one — same lock applies both directions."""
    te_id, reg_id, _sub = locked_term_setup
    resp = await client.delete(f"/students/term-enrollments/{te_id}/subjects/{reg_id}", headers=auth)
    assert resp.status_code == 423


@pytest.mark.asyncio
async def test_delete_subject_registration_allowed_with_override(
    client: AsyncClient, auth: dict, locked_term_setup, db_session: AsyncSession, school: School,
    redis_permissions: None,
):
    te_id, reg_id, _sub = locked_term_setup
    hod_auth = await _login_as_position(client, auth, db_session, school, "HOD")
    resp = await client.delete(
        f"/students/term-enrollments/{te_id}/subjects/{reg_id}?override_reason=Correction+approved",
        headers=hod_auth,
    )
    assert resp.status_code == 204


@pytest.fixture
async def non_current_term_registration(
    client: AsyncClient, auth: dict, school_class: Class, academic_term: AcademicTerm,
    db_session: AsyncSession, school: School,
):
    """A subject already registered against a TermEnrollment for a term that
    isn't the current one — the state every 'not the current term' test
    starts from. Registration itself is done as the superadmin `auth`
    fixture (which bypasses the new check) since a scoped caller can't
    create this state through the API at all — that's the behaviour under
    test in the sibling 'blocked' cases."""
    from app.models.academic import ClassSubject, Subject

    non_current_term = AcademicTerm(
        school_id=school.id, academic_year_id=academic_term.academic_year_id,
        term_number=2, name="Term 2",
        start_date=date(2025, 1, 1), end_date=date(2025, 4, 1), is_current=False,
    )
    db_session.add(non_current_term)
    await db_session.flush()

    sub = Subject(school_id=school.id, code="NCT01", name="Non-Current Term Subject", is_active=True)
    db_session.add(sub)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=sub.id, is_active=True))
    await db_session.flush()
    await _assign_subject_teacher(db_session, school, school_class.id, sub.id, academic_term.academic_year_id, "NCT01")

    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)
    te_id = (await client.post("/students/term-enrollments", json={
        "student_id": sid, "academic_term_id": str(non_current_term.id),
    }, headers=auth)).json()["id"]
    reg_id = (await client.post(f"/students/term-enrollments/{te_id}/subjects", json={"items": [
        {"subject_id": str(sub.id), "registration_type": "CORE"},
    ]}, headers=auth)).json()[0]["id"]

    return te_id, reg_id, sub, non_current_term


async def _class_teacher_auth(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, academic_term: AcademicTerm,
) -> dict:
    """A CLASS_TEACHER login with a real ClassTeacher assignment on
    school_class, so the request clears student_scope's Category B check
    and any remaining rejection is attributable to the behaviour under
    test."""
    from app.models.academic import ClassTeacher

    teacher_auth = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    teacher_user = await db_session.scalar(
        select(User).where(User.email == "class_teacher@presec-test.edu.gh")
    )
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=teacher_user.staff_member_id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()
    return teacher_auth


@pytest.mark.asyncio
async def test_register_subject_blocked_on_non_current_term(
    client: AsyncClient, auth: dict, non_current_term_registration, db_session: AsyncSession,
    school: School, school_class: Class, academic_term: AcademicTerm, redis_permissions: None,
):
    """A class/subject teacher can't register a subject against a term
    that isn't the one currently running — same reasoning as attendance
    and scoring being restricted to the current term."""
    _te_id, _reg_id, sub, non_current_term = non_current_term_registration
    teacher_auth = await _class_teacher_auth(client, auth, db_session, school, school_class, academic_term)

    sid = await _create_student(client, auth, num="NCT-BLOCKED")
    await _assign_class(client, auth, sid, school_class, academic_term)
    te_id = (await client.post("/students/term-enrollments", json={
        "student_id": sid, "academic_term_id": str(non_current_term.id),
    }, headers=auth)).json()["id"]

    resp = await client.post(f"/students/term-enrollments/{te_id}/subjects", json={"items": [
        {"subject_id": str(sub.id), "registration_type": "CORE"},
    ]}, headers=teacher_auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_subject_allowed_on_non_current_term_for_approve_scores_holder(
    client: AsyncClient, auth: dict, non_current_term_registration, db_session: AsyncSession,
    school: School, school_class: Class, academic_term: AcademicTerm, redis_permissions: None,
):
    """HOD holds assessments.approve_scores — the same permission that
    already bypasses the results_locked override — so backfilling a
    non-current term's registrations is still possible for senior staff."""
    _te_id, _reg_id, sub, non_current_term = non_current_term_registration
    hod_auth = await _login_as_position(client, auth, db_session, school, "HOD")

    sid = await _create_student(client, auth, num="NCT-ALLOWED")
    await _assign_class(client, auth, sid, school_class, academic_term)
    te_id = (await client.post("/students/term-enrollments", json={
        "student_id": sid, "academic_term_id": str(non_current_term.id),
    }, headers=auth)).json()["id"]

    resp = await client.post(f"/students/term-enrollments/{te_id}/subjects", json={"items": [
        {"subject_id": str(sub.id), "registration_type": "CORE"},
    ]}, headers=hod_auth)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_subject_registration_blocked_on_non_current_term(
    client: AsyncClient, auth: dict, non_current_term_registration, db_session: AsyncSession,
    school: School, school_class: Class, academic_term: AcademicTerm, redis_permissions: None,
):
    te_id, reg_id, _sub, _non_current_term = non_current_term_registration
    teacher_auth = await _class_teacher_auth(client, auth, db_session, school, school_class, academic_term)

    resp = await client.delete(f"/students/term-enrollments/{te_id}/subjects/{reg_id}", headers=teacher_auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_subject_registration_allowed_on_non_current_term_for_approve_scores_holder(
    client: AsyncClient, auth: dict, non_current_term_registration, db_session: AsyncSession,
    school: School, redis_permissions: None,
):
    te_id, reg_id, _sub, _non_current_term = non_current_term_registration
    hod_auth = await _login_as_position(client, auth, db_session, school, "HOD")

    resp = await client.delete(f"/students/term-enrollments/{te_id}/subjects/{reg_id}", headers=hod_auth)
    assert resp.status_code == 204


# ── Bulk class assignment ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_class_assignment_skips_duplicate_and_continues(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
):
    """A duplicate assignment earlier in the batch must not crash the request
    or block later items — each item runs in its own savepoint."""
    already_assigned = await _create_student(client, auth, num="BULK001")
    await _assign_class(client, auth, already_assigned, school_class, academic_term)
    fresh = await _create_student(client, auth, num="BULK002")

    resp = await client.post("/students/class-assignments/bulk", json={
        "items": [
            {"student_id": already_assigned, "class_id": str(school_class.id),
             "academic_year_id": str(academic_term.academic_year_id)},
            {"student_id": fresh, "class_id": str(school_class.id),
             "academic_year_id": str(academic_term.academic_year_id)},
        ]
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.json() == {"enrolled": 1, "skipped": 1}


# ── Transfer requests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_and_approve_transfer(client: AsyncClient, auth: dict):
    sid = await _create_student(client, auth)
    tr_resp = await client.post(f"/students/{sid}/transfers", json={
        "reason": "Family relocation",
    }, headers=auth)
    assert tr_resp.status_code == 201
    tr_id = tr_resp.json()["id"]
    assert tr_resp.json()["status"] == "PENDING"

    # Appears in pending list
    pending = (await client.get("/students/transfers/pending", headers=auth)).json()
    assert any(t["id"] == tr_id for t in pending)

    # Approve it — student should become inactive
    resp = await client.patch(f"/students/transfers/{tr_id}/review",
        json={"status": "APPROVED"}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["status"] == "APPROVED"

    detail = (await client.get(f"/students/{sid}", headers=auth)).json()
    assert detail["is_active"] is False


@pytest.mark.asyncio
async def test_transfer_approval_deactivates_class_assignment(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
):
    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)

    tr_id = (await client.post(f"/students/{sid}/transfers", json={}, headers=auth)).json()["id"]
    resp = await client.patch(f"/students/transfers/{tr_id}/review",
        json={"status": "APPROVED"}, headers=auth)
    assert resp.status_code == 200

    assignments = (await client.get(f"/students/{sid}/class-assignments", headers=auth)).json()
    assert all(a["is_active"] is False for a in assignments)


@pytest.mark.asyncio
async def test_duplicate_pending_transfer_rejected(client: AsyncClient, auth: dict):
    sid = await _create_student(client, auth)
    first = await client.post(f"/students/{sid}/transfers", json={}, headers=auth)
    assert first.status_code == 201

    second = await client.post(f"/students/{sid}/transfers", json={}, headers=auth)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_list_transfers_for_student(client: AsyncClient, auth: dict):
    sid = await _create_student(client, auth)
    tr_id = (await client.post(f"/students/{sid}/transfers", json={
        "reason": "Moving abroad",
    }, headers=auth)).json()["id"]

    resp = await client.get(f"/students/{sid}/transfers", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == tr_id
    assert data[0]["status"] == "PENDING"


@pytest.mark.asyncio
async def test_double_review_rejected(client: AsyncClient, auth: dict):
    sid = await _create_student(client, auth)
    tr_id = (await client.post(f"/students/{sid}/transfers", json={}, headers=auth)).json()["id"]
    await client.patch(f"/students/transfers/{tr_id}/review", json={"status": "REJECTED"}, headers=auth)
    resp = await client.patch(f"/students/transfers/{tr_id}/review", json={"status": "APPROVED"}, headers=auth)
    assert resp.status_code == 409


# ── Fee gate ─────────────────────────────────────────────────────────────────
# AcademicTerm.block_owing_students, off by default, blocks term enrollment for
# a student with a positive live-computed StudentFeeSummary balance unless a
# caller with fees.manage supplies a fee_waiver_reason.

async def _enable_fee_gate(client: AsyncClient, auth: dict, term_id) -> None:
    resp = await client.patch(f"/academic/terms/{term_id}", json={
        "block_owing_students": True,
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["block_owing_students"] is True


@pytest.mark.asyncio
async def test_update_term_toggles_block_owing_students(
    client: AsyncClient, auth: dict, academic_term: AcademicTerm,
):
    resp = await client.patch(f"/academic/terms/{academic_term.id}", json={
        "block_owing_students": True,
    }, headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["block_owing_students"] is True
    assert data["block_owing_students_set_by"] is not None
    assert data["block_owing_students_set_at"] is not None


@pytest.mark.asyncio
async def test_fee_gate_off_by_default_allows_owing_student(
    client: AsyncClient, auth: dict,
    student: Student, school_class: Class, academic_term: AcademicTerm, fee_record: StudentFeeRecord,
):
    await _assign_class(client, auth, str(student.id), school_class, academic_term)
    resp = await client.post("/students/term-enrollments", json={
        "student_id": str(student.id), "academic_term_id": str(academic_term.id),
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["fee_waived"] is False


@pytest.mark.asyncio
async def test_fee_gate_blocks_owing_student(
    client: AsyncClient, auth: dict,
    student: Student, school_class: Class, academic_term: AcademicTerm, fee_record: StudentFeeRecord,
):
    await _assign_class(client, auth, str(student.id), school_class, academic_term)
    await _enable_fee_gate(client, auth, academic_term.id)

    resp = await client.post("/students/term-enrollments", json={
        "student_id": str(student.id), "academic_term_id": str(academic_term.id),
    }, headers=auth)
    assert resp.status_code == 422
    assert "owes" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_fee_gate_not_applicable_without_fee_record(
    client: AsyncClient, auth: dict,
    school_class: Class, academic_term: AcademicTerm,
):
    """A student with no StudentFeeSummary row at all (nothing assigned yet)
    is never blocked, even with the gate on."""
    await _enable_fee_gate(client, auth, academic_term.id)
    sid = await _create_student(client, auth)
    await _assign_class(client, auth, sid, school_class, academic_term)

    resp = await client.post("/students/term-enrollments", json={
        "student_id": sid, "academic_term_id": str(academic_term.id),
    }, headers=auth)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_fee_gate_waived_with_reason(
    client: AsyncClient, auth: dict,
    student: Student, school_class: Class, academic_term: AcademicTerm, fee_record: StudentFeeRecord,
):
    """auth is a superadmin, so fees.manage always resolves True for it —
    supplying a waiver reason pushes the blocked enrollment through."""
    await _assign_class(client, auth, str(student.id), school_class, academic_term)
    await _enable_fee_gate(client, auth, academic_term.id)

    resp = await client.post("/students/term-enrollments", json={
        "student_id": str(student.id), "academic_term_id": str(academic_term.id),
        "fee_waiver_reason": "Hardship case — approved by head.",
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["fee_waived"] is True


@pytest.mark.asyncio
async def test_fee_gate_waiver_ignored_without_fees_manage(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, redis_permissions: None,
    student: Student, school_class: Class, academic_term: AcademicTerm, fee_record: StudentFeeRecord,
):
    """CLASS_TEACHER has students.edit (can reach this endpoint) but not
    fees.manage — a supplied waiver reason must be ignored, not trusted."""
    await _assign_class(client, auth, str(student.id), school_class, academic_term)
    await _enable_fee_gate(client, auth, academic_term.id)

    teacher_auth = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    # Give the teacher an actual ClassTeacher assignment on this class, so the
    # request clears core/student_scope.py's Category A scoping check and
    # this test can isolate the fee-gate-waiver behaviour it's actually about.
    from app.models.academic import ClassTeacher
    teacher_user = await db_session.scalar(
        select(User).where(User.email == "class_teacher@presec-test.edu.gh")
    )
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=teacher_user.staff_member_id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.post("/students/term-enrollments", json={
        "student_id": str(student.id), "academic_term_id": str(academic_term.id),
        "fee_waiver_reason": "trust me",
    }, headers=teacher_auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_fee_gate_cleared_by_payment(
    client: AsyncClient, auth: dict,
    student: Student, school_class: Class, academic_term: AcademicTerm, fee_record: StudentFeeRecord,
):
    await _assign_class(client, auth, str(student.id), school_class, academic_term)
    await _enable_fee_gate(client, auth, academic_term.id)

    await client.post("/fees/payments", json={
        "fee_record_id": str(fee_record.id),
        "amount_paid": "500.00", "payment_method": "CASH", "payment_date": "2024-10-01",
    }, headers=auth)

    resp = await client.post("/students/term-enrollments", json={
        "student_id": str(student.id), "academic_term_id": str(academic_term.id),
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["fee_waived"] is False


@pytest.mark.asyncio
async def test_bulk_term_enrollment_skips_fee_blocked_and_duplicate(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    student: Student, school_class: Class, academic_term: AcademicTerm, fee_record: StudentFeeRecord,
):
    """Regression check for a session bug found and fixed alongside this
    feature: bulk_term_enrollment shares ONE transaction across the whole
    batch (one request = one session; the test harness's get_db override never
    commits, so in tests this can even span the whole test function). A plain
    db.rollback() on a skipped item discards every earlier flush since the
    session's transaction began — not just the failed item, and in this test
    harness not even just the current request; confirmed by direct db_session
    checks showing the `student` fixture itself (created before any HTTP call
    in this test) disappeared under the old code. Each item must run in its
    own SAVEPOINT (db.begin_nested()) instead, matching register_subjects()
    in this file.

    A follow-up HTTP GET is NOT a reliable way to catch this — it passed even
    against the buggy code in earlier manual testing (the auth/session
    resolution path for the follow-up request didn't visibly break even
    though the data was gone). Assert directly against db_session instead."""
    await _assign_class(client, auth, str(student.id), school_class, academic_term)
    await _enable_fee_gate(client, auth, academic_term.id)

    new_sid = await _create_student(client, auth, "ADM-NEW")
    await _assign_class(client, auth, new_sid, school_class, academic_term)

    clear_sid = await _create_student(client, auth, "ADM-CLEAR")
    await _assign_class(client, auth, clear_sid, school_class, academic_term)
    await client.post("/students/term-enrollments", json={
        "student_id": clear_sid, "academic_term_id": str(academic_term.id),
    }, headers=auth)

    resp = await client.post("/students/bulk-term-enrollments", json={
        "items": [
            {"student_id": new_sid, "academic_term_id": str(academic_term.id)},            # succeeds
            {"student_id": str(student.id), "academic_term_id": str(academic_term.id)},    # fee-blocked
            {"student_id": clear_sid, "academic_term_id": str(academic_term.id)},           # duplicate
        ],
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.json() == {"enrolled": 1, "skipped": 2}

    # Direct DB check on the same session — the reliable way to catch this.
    # The `student` fixture itself is the canary: under the old bug it (and
    # everything else flushed earlier in the test) would be gone too.
    still_there = await db_session.get(Student, student.id)
    assert still_there is not None

    new_rows = (await db_session.execute(
        select(TermEnrollment).where(TermEnrollment.student_id == new_sid)
    )).scalars().all()
    assert len(new_rows) == 1

    clear_rows = (await db_session.execute(
        select(TermEnrollment).where(TermEnrollment.student_id == clear_sid)
    )).scalars().all()
    assert len(clear_rows) == 1
