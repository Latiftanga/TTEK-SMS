"""
Report card integration tests — behaviour records, PDF generation, QR verification.
Run inside Docker: docker compose exec api pytest app/tests/test_report_cards.py -v

These tests run against the real DB. PDF generation uses WeasyPrint so the
container must have libpango/libcairo installed (it does — see Dockerfile).
"""
import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import AcademicTerm, Class, ClassTeacher
from app.models.school import School
from app.models.students import Student, StudentClassAssignment, TermEnrollment
from app.models.auth import LoginType, StaffPosition, User


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _login_as_position(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, position_code: str,
) -> tuple[dict, str]:
    """Create a staff member holding `position_code`, give them a login, and
    return (their bearer-token auth headers, their staff_member id) — mirrors
    test_attendance.py/test_scoring_lock.py's helper."""
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
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, staff_id

async def _make_enrollment(
    db: AsyncSession, school: School, student: Student,
    school_class: Class, academic_term: AcademicTerm, school_admin: User
) -> TermEnrollment:
    sca = StudentClassAssignment(
        school_id=school.id,
        student_id=student.id,
        class_id=school_class.id,
        academic_year_id=academic_term.academic_year_id,
        assigned_by_id=school_admin.id,
        is_active=True,
    )
    db.add(sca)
    await db.flush()

    te = TermEnrollment(
        school_id=school.id,
        student_id=student.id,
        academic_term_id=academic_term.id,
        enrolled_by_id=school_admin.id,
        is_active=True,
    )
    db.add(te)
    await db.flush()
    return te


# ── Behaviour records ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_behaviour_record(
    client: AsyncClient, auth: dict,
    student: Student, academic_term: AcademicTerm
):
    resp = await client.post("/behaviour", json={
        "student_id": str(student.id),
        "academic_term_id": str(academic_term.id),
        "incident_type": "Late to class",
        "description": "Student arrived 20 minutes late without excuse.",
        "severity": "LOW",
        "incident_date": "2024-10-15",
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["incident_type"] == "Late to class"
    assert data["severity"] == "LOW"


@pytest.mark.asyncio
async def test_create_behaviour_invalid_severity(
    client: AsyncClient, auth: dict,
    student: Student, academic_term: AcademicTerm
):
    resp = await client.post("/behaviour", json={
        "student_id": str(student.id),
        "academic_term_id": str(academic_term.id),
        "incident_type": "Test",
        "description": "Test",
        "severity": "CRITICAL",    # not a valid literal
        "incident_date": "2024-10-15",
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_behaviour_records(
    client: AsyncClient, auth: dict,
    student: Student, academic_term: AcademicTerm
):
    await client.post("/behaviour", json={
        "student_id": str(student.id),
        "academic_term_id": str(academic_term.id),
        "incident_type": "Fighting",
        "description": "Involved in altercation.",
        "severity": "HIGH",
        "incident_date": "2024-11-01",
    }, headers=auth)
    resp = await client.get(
        f"/behaviour?student_id={student.id}&term_id={academic_term.id}", headers=auth
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_behaviour_record(
    client: AsyncClient, auth: dict,
    student: Student, academic_term: AcademicTerm
):
    r = await client.post("/behaviour", json={
        "student_id": str(student.id),
        "academic_term_id": str(academic_term.id),
        "incident_type": "Noise",
        "description": "Disruptive in class.",
        "severity": "MEDIUM",
        "incident_date": "2024-10-20",
    }, headers=auth)
    record_id = r.json()["id"]
    resp = await client.delete(f"/behaviour/{record_id}", headers=auth)
    assert resp.status_code == 204


# ── Report card PDF ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_report_card_pdf_generated(
    client: AsyncClient, auth: dict,
    db_session: AsyncSession,
    school: School, student: Student, school_class: Class,
    academic_term: AcademicTerm, school_admin: User
):
    te = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    resp = await client.get(f"/report-cards/{te.id}", headers=auth)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 1000   # non-trivial PDF


@pytest.mark.asyncio
async def test_assemble_includes_letterhead_photo_and_grade_legend(
    db_session: AsyncSession,
    school: School, student: Student, school_class: Class,
    academic_term: AcademicTerm, school_admin: User,
):
    """school.phone/email/address, the student's photo, and a grade legend
    (from the shared seeded default scale, since this school has no scale of
    its own) must all reach the template context. The `school` fixture sets
    no phone/email/address and `student` has no photo — both must degrade
    gracefully to None rather than erroring or leaking a literal "None"."""
    from app.services.report_card import assemble

    te = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    context = await assemble(te.id, school.id, school_admin.id, db_session)

    assert context["school_phone"] is None
    assert context["school_email"] is None
    assert context["school_address"] is None
    assert context["photo_url"] is None

    assert context["grade_legend"], "shared seeded default scale must populate the legend"
    assert context["grade_legend"][0]["letter_grade"] == "A1"  # highest band first


@pytest.mark.asyncio
async def test_assemble_groups_scores_by_subject_with_total_and_grade(
    db_session: AsyncSession,
    school: School, student: Student, school_class: Class,
    academic_term: AcademicTerm, school_admin: User,
):
    """The exact scenario a real school described: four assessment categories
    (Individual/Group Work/Mid-Sem/End of Term, weights 20/20/20/40) under one
    subject. The report card must show each category row grouped under its
    subject, plus a combined weighted total and a letter grade resolved for
    that total — not just four disconnected rows with no synthesis."""
    from decimal import Decimal
    from app.models.academic import ClassSubject, SchoolLevel, Subject, SubjectCatalogue, SubjectType
    from app.models.assessments import Assessment, AssessmentType, Score

    cat = SubjectCatalogue(name="Mathematics", code="MATH_RC", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subject = Subject(school_id=school.id, catalogue_id=cat.id, code="MATH_RC", name="Mathematics", is_active=True)
    db_session.add(subject)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subject.id, is_active=True))
    await db_session.flush()

    te = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)

    categories = [
        ("Individual", Decimal("20.00"), Decimal("18.00")),
        ("Group Work", Decimal("20.00"), Decimal("16.00")),
        ("Mid-Sem", Decimal("20.00"), Decimal("15.00")),
        ("End of Term", Decimal("40.00"), Decimal("30.00")),
    ]
    for name, weight_and_max, raw in categories:
        atype = AssessmentType(school_id=school.id, name=name, code=f"RC_{name[:4].upper()}", weight=weight_and_max)
        db_session.add(atype)
        await db_session.flush()
        a = Assessment(
            school_id=school.id, class_id=school_class.id, subject_id=subject.id,
            assessment_type_id=atype.id, academic_term_id=academic_term.id,
            description=name, recorded_date=date.today(), max_score=weight_and_max, is_published=True,
        )
        db_session.add(a)
        await db_session.flush()
        db_session.add(Score(
            school_id=school.id, assessment_id=a.id, student_id=student.id,
            raw_score=raw, is_approved=True, entered_by_id=school_admin.id,
        ))
    await db_session.flush()

    from app.services.report_card import assemble
    context = await assemble(te.id, school.id, school_admin.id, db_session)

    groups = context["subject_groups"]
    assert len(groups) == 1
    group = groups[0]
    assert group["subject_name"] == "Mathematics"
    assert len(group["rows"]) == 4
    # (18/20)*20 + (16/20)*20 + (15/20)*20 + (30/40)*40 = 18+16+15+30 = 79
    assert group["total"] == Decimal("79.00")
    assert group["grade"] == "B2"  # shared seeded scale: B2 = 75-79.99


# ── Class enrollment list (report card selection) ─────────────────────────────

@pytest.mark.asyncio
async def test_list_class_enrollments_excludes_withdrawn_student(
    client: AsyncClient, auth: dict,
    db_session: AsyncSession,
    school: School, student: Student, school_class: Class,
    academic_term: AcademicTerm, school_admin: User,
):
    """A withdrawn/transferred student (StudentClassAssignment/TermEnrollment
    deactivated, not deleted, by student_lifecycle.py) must not appear in the
    'select students to generate report cards for' list."""
    te = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)

    resp = await client.get(
        f"/report-cards/enrollments?class_id={school_class.id}&term_id={academic_term.id}", headers=auth,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["enrollment_id"] == str(te.id)

    sca = await db_session.scalar(
        select(StudentClassAssignment).where(StudentClassAssignment.student_id == student.id)
    )
    sca.is_active = False
    te.is_active = False
    await db_session.flush()

    resp_after = await client.get(
        f"/report-cards/enrollments?class_id={school_class.id}&term_id={academic_term.id}", headers=auth,
    )
    assert resp_after.status_code == 200
    assert resp_after.json() == []


@pytest.mark.asyncio
async def test_assemble_is_early_years_true_for_kg_class(
    db_session: AsyncSession,
    school: School, student: Student,
    academic_term: AcademicTerm, school_admin: User,
):
    """Creche/Nursery/KG get the milestone-style report section — auto-detected
    from the class-level ladder (services/class_progression.py), not a manual
    format choice like the old BASIC/SHS/ECM picker."""
    from app.services.report_card import assemble

    kg_class = Class(school_id=school.id, level="KG", year_group=2, stream="A", is_active=True)
    db_session.add(kg_class)
    await db_session.flush()
    te = await _make_enrollment(db_session, school, student, kg_class, academic_term, school_admin)

    context = await assemble(te.id, school.id, school_admin.id, db_session)
    assert context["is_early_years"] is True


@pytest.mark.asyncio
async def test_assemble_is_early_years_false_for_standard_class(
    db_session: AsyncSession,
    school: School, student: Student, school_class: Class,
    academic_term: AcademicTerm, school_admin: User,
):
    """school_class is level="SHS" — must get the standard numeric+rank
    layout, not the milestone section."""
    from app.services.report_card import assemble

    te = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    context = await assemble(te.id, school.id, school_admin.id, db_session)
    assert context["is_early_years"] is False


@pytest.mark.asyncio
async def test_report_card_unknown_enrollment(
    client: AsyncClient, auth: dict
):
    resp = await client.get(f"/report-cards/{uuid.uuid4()}", headers=auth)
    assert resp.status_code == 404


# ── QR verification ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_qr_verify_valid_token(
    client: AsyncClient, auth: dict,
    db_session: AsyncSession,
    school: School, student: Student, school_class: Class,
    academic_term: AcademicTerm, school_admin: User
):
    te = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    from app.services.qr import generate_token
    token = generate_token(te.id, school.id)
    resp = await client.get(f"/verify/{token}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["admission_number"] == student.admission_number


@pytest.mark.asyncio
async def test_qr_verify_tampered_token(client: AsyncClient):
    resp = await client.get("/verify/aGVsbG8.badhash123")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_qr_verify_garbage_token(client: AsyncClient):
    resp = await client.get("/verify/not-a-real-token")
    assert resp.status_code == 404


# ── Class-teacher scoping ──────────────────────────────────────────────────────
# A CLASS_TEACHER holds assessments.view (report cards are gated on that, not
# students.view) but should only reach report cards for classes they are the
# ClassTeacher of — matches the user's own framing ("report cards should only
# show when the teacher is a class_teacher for that class").

@pytest.mark.asyncio
async def test_report_card_404_for_non_owning_class_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school: School, student: Student, school_class: Class,
    academic_term: AcademicTerm, school_admin: User, redis_permissions: None,
):
    te = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    teacher_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    resp = await client.get(f"/report-cards/{te.id}", headers=teacher_auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_report_card_allowed_for_owning_class_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school: School, student: Student, school_class: Class,
    academic_term: AcademicTerm, school_admin: User, redis_permissions: None,
):
    te = await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.get(f"/report-cards/{te.id}", headers=teacher_auth)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


@pytest.mark.asyncio
async def test_list_class_enrollments_404_for_non_owning_class_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school: School, student: Student, school_class: Class,
    academic_term: AcademicTerm, school_admin: User, redis_permissions: None,
):
    await _make_enrollment(db_session, school, student, school_class, academic_term, school_admin)
    teacher_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")
    resp = await client.get(
        f"/report-cards/enrollments?class_id={school_class.id}&term_id={academic_term.id}", headers=teacher_auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_my_report_classes_scoped_to_own_class_teacher_assignment(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
    school: School, school_class: Class, academic_term: AcademicTerm, redis_permissions: None,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "CLASS_TEACHER")

    empty = await client.get(f"/report-cards/my-classes?term_id={academic_term.id}", headers=teacher_auth)
    assert empty.status_code == 200
    assert empty.json() == []

    db_session.add(ClassTeacher(
        school_id=school.id, class_id=school_class.id, staff_member_id=staff_id,
        academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.get(f"/report-cards/my-classes?term_id={academic_term.id}", headers=teacher_auth)
    assert resp.status_code == 200
    assert [c["id"] for c in resp.json()] == [str(school_class.id)]


@pytest.mark.asyncio
async def test_my_report_classes_unrestricted_for_admin(
    client: AsyncClient, auth: dict, school_class: Class, academic_term: AcademicTerm,
):
    """The school_admin fixture is a superadmin — always unrestricted."""
    resp = await client.get(f"/report-cards/my-classes?term_id={academic_term.id}", headers=auth)
    assert resp.status_code == 200
    assert any(c["id"] == str(school_class.id) for c in resp.json())
