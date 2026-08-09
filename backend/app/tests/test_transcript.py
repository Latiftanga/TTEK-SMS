"""
Transcript integration tests — full multi-term academic history PDF.
Run inside Docker: docker compose exec api pytest app/tests/test_transcript.py -v
"""
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import AcademicTerm, AcademicYear, Class, SchoolLevel, Subject, SubjectCatalogue, SubjectType
from app.models.assessments import Assessment, AssessmentType, Score
from app.models.auth import LoginType, StaffPosition, User
from app.models.school import School
from app.models.students import Student, StudentClassAssignment, TermEnrollment


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


async def _assign_and_enroll(
    db_session: AsyncSession, school: School, student: Student,
    school_class: Class, academic_term: AcademicTerm, school_admin: User,
) -> TermEnrollment:
    sca = await db_session.scalar(
        select(StudentClassAssignment).where(
            StudentClassAssignment.student_id == student.id,
            StudentClassAssignment.academic_year_id == academic_term.academic_year_id,
        )
    )
    if not sca:
        sca = StudentClassAssignment(
            school_id=school.id, student_id=student.id, class_id=school_class.id,
            academic_year_id=academic_term.academic_year_id,
            assigned_by_id=school_admin.id, is_active=True,
        )
        db_session.add(sca)
        await db_session.flush()

    te = TermEnrollment(
        school_id=school.id, student_id=student.id, academic_term_id=academic_term.id,
        enrolled_by_id=school_admin.id, is_active=True,
    )
    db_session.add(te)
    await db_session.flush()
    return te


@pytest.fixture
async def assessment_type(db_session: AsyncSession, school) -> AssessmentType:
    t = AssessmentType(school_id=school.id, name="Exam", code="EX_TRANSCRIPT", weight=Decimal("100.00"))
    db_session.add(t)
    await db_session.flush()
    return t


@pytest.fixture
async def subject(db_session: AsyncSession, school, school_class: Class) -> Subject:
    from app.models.academic import ClassSubject
    cat = SubjectCatalogue(name="Core Maths", code="MATH_TR", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code="MATH_TR", name="Core Maths", is_active=True)
    db_session.add(subj)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subj.id, is_active=True))
    await db_session.flush()
    return subj


async def _add_score(
    db_session: AsyncSession, school: School, school_class: Class, subject: Subject,
    assessment_type: AssessmentType, academic_term: AcademicTerm, student: Student,
    school_admin: User,
    raw_score: Decimal = Decimal("80.00"), is_approved: bool = True, is_published: bool = True,
) -> Score:
    a = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        assessment_type_id=assessment_type.id, academic_term_id=academic_term.id,
        description=f"Test {academic_term.id}", recorded_date=date.today(),
        max_score=Decimal("100.00"), is_published=is_published,
    )
    db_session.add(a)
    await db_session.flush()
    s = Score(
        school_id=school.id, assessment_id=a.id, student_id=student.id,
        raw_score=raw_score, is_approved=is_approved, entered_by_id=school_admin.id,
        cached_grade_label="A1" if is_approved else None,
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.mark.asyncio
async def test_transcript_empty_history(client: AsyncClient, auth: dict, student: Student):
    """A student with zero term enrollments must not 500 — just an empty transcript."""
    resp = await client.get(f"/students/{student.id}/transcript", headers=auth)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 500


@pytest.mark.asyncio
async def test_transcript_spans_multiple_terms_and_years(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school: School, student: Student, school_class: Class,
    academic_term: AcademicTerm, academic_year: AcademicYear, school_admin: User,
    subject: Subject, assessment_type: AssessmentType,
):
    await _assign_and_enroll(db_session, school, student, school_class, academic_term, school_admin)
    await _add_score(db_session, school, school_class, subject, assessment_type, academic_term, student, school_admin)

    # A second year, second term, same class — proves the transcript spans years,
    # not just terms within one year.
    year2 = AcademicYear(
        school_id=school.id, name="2025/2026",
        start_date=date(2025, 9, 1), end_date=date(2026, 7, 31), is_current=False,
    )
    db_session.add(year2)
    await db_session.flush()
    term2 = AcademicTerm(
        school_id=school.id, academic_year_id=year2.id, term_number=1, name="Term 1",
        start_date=date(2025, 9, 1), end_date=date(2025, 12, 20), is_current=False,
    )
    db_session.add(term2)
    await db_session.flush()
    await _assign_and_enroll(db_session, school, student, school_class, term2, school_admin)
    await _add_score(db_session, school, school_class, subject, assessment_type, term2, student, school_admin, raw_score=Decimal("90.00"))

    resp = await client.get(f"/students/{student.id}/transcript", headers=auth)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 1000


@pytest.mark.asyncio
async def test_transcript_excludes_unpublished_scores(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school: School, student: Student, school_class: Class,
    academic_term: AcademicTerm, school_admin: User,
    subject: Subject, assessment_type: AssessmentType,
):
    """An unpublished assessment's score must not appear on the transcript —
    same is_approved+is_published gate as a single report card."""
    from app.services.transcript import assemble_transcript

    await _assign_and_enroll(db_session, school, student, school_class, academic_term, school_admin)
    await _add_score(
        db_session, school, school_class, subject, assessment_type, academic_term, student, school_admin,
        is_published=False,
    )

    context = await assemble_transcript(student.id, school.id, school_admin.id, db_session)
    term_ctx = context["years"][0]["terms"][0]
    assert term_ctx["subject_weighted"] == {}


@pytest.mark.asyncio
async def test_transcript_includes_letterhead_photo_and_grade_legend(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school: School, student: Student, school_class: Class,
    academic_term: AcademicTerm, school_admin: User,
    subject: Subject, assessment_type: AssessmentType,
):
    """Same letterhead/photo/grade-legend fields as the single-term report
    card (services/report_card.py) — degrade gracefully to None/empty for a
    school with no phone/email/address and a student with no photo."""
    from app.services.transcript import assemble_transcript

    await _assign_and_enroll(db_session, school, student, school_class, academic_term, school_admin)
    await _add_score(db_session, school, school_class, subject, assessment_type, academic_term, student, school_admin)

    context = await assemble_transcript(student.id, school.id, school_admin.id, db_session)
    assert context["school_phone"] is None
    assert context["school_email"] is None
    assert context["school_address"] is None
    assert context["photo_url"] is None
    assert context["grade_legend"], "shared seeded default scale must populate the legend"


@pytest.mark.asyncio
async def test_transcript_empty_history_includes_grade_legend(
    db_session: AsyncSession, school: School, student: Student, school_admin: User,
):
    """The empty-history early-return branch (zero term enrollments) must
    also carry the letterhead/legend fields — the two-return-statement shape
    invites forgetting one of them."""
    from app.services.transcript import assemble_transcript

    context = await assemble_transcript(student.id, school.id, school_admin.id, db_session)
    assert context["years"] == []
    assert context["school_phone"] is None
    assert context["photo_url"] is None
    assert context["grade_legend"], "shared seeded default scale must populate the legend"


@pytest.mark.asyncio
async def test_transcript_requires_assessments_view(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school: School, student: Student, redis_permissions: None,
):
    """A Housemaster (students.view but no assessments.* permission) must not
    be able to pull a transcript — same bar as a single report card."""
    housemaster_auth = await _login_as_position(client, auth, db_session, school, "HOUSEMASTER")
    resp = await client.get(f"/students/{student.id}/transcript", headers=housemaster_auth)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_transcript_scoped_to_students_the_caller_teaches(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school: School, student: Student, redis_permissions: None,
):
    """assessments.view alone doesn't imply cross-class visibility — a
    TEACHER holding the right permission but with no ClassTeacher/
    SubjectTeacher assignment to this student's class must 404, matching
    the same boundary a single report card already enforces
    (resolve_report_card_scope). Regression for a gap where
    assemble_transcript() never received user_id at all and so could not
    apply any per-caller scoping."""
    teacher_auth = await _login_as_position(client, auth, db_session, school, "TEACHER")
    resp = await client.get(f"/students/{student.id}/transcript", headers=teacher_auth)
    assert resp.status_code == 404, resp.text
