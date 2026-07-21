"""
Subject-registration eligibility — the fix for a class splitting into
electives (e.g. French vs Literature-in-French) where scoring must not treat
"everyone in the class" as "everyone taking this subject".

Covers services/subject_roster.py and its call sites:
  - create_assessment: subject must be an active ClassSubject on the class
  - GET /assessments/{id}/roster: only eligible students appear
  - submit_scores: rejects a student not registered for this subject

Run inside Docker: docker compose exec api pytest app/tests/test_subject_roster.py -v
"""
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, AcademicYear, Class, ClassSubject, SchoolLevel, Subject, SubjectCatalogue, SubjectType
from app.models.assessments import Assessment, AssessmentType
from app.models.students import Student, StudentClassAssignment, SubjectRegistration, TermEnrollment


async def _make_subject(db_session: AsyncSession, school, code: str, name: str) -> Subject:
    cat = SubjectCatalogue(name=name, code=code, subject_type=SubjectType.ELECTIVE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code=code, name=name, is_active=True)
    db_session.add(subj)
    await db_session.flush()
    return subj


async def _assign_to_class(
    db_session: AsyncSession, school, student: Student, school_class: Class, academic_year: AcademicYear,
) -> StudentClassAssignment:
    sca = StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=school_class.id,
        academic_year_id=academic_year.id, is_active=True,
    )
    db_session.add(sca)
    await db_session.flush()
    return sca


async def _enroll_for_term(
    db_session: AsyncSession, school, student: Student, academic_term: AcademicTerm, enrolled_by_id,
) -> TermEnrollment:
    te = TermEnrollment(
        school_id=school.id, student_id=student.id, academic_term_id=academic_term.id,
        enrolled_by_id=enrolled_by_id, is_active=True,
    )
    db_session.add(te)
    await db_session.flush()
    return te


@pytest.fixture
async def french(db_session: AsyncSession, school, school_class: Class) -> Subject:
    subj = await _make_subject(db_session, school, "FRENCH", "French")
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subj.id, is_active=True))
    await db_session.flush()
    return subj


@pytest.fixture
async def literature(db_session: AsyncSession, school, school_class: Class) -> Subject:
    subj = await _make_subject(db_session, school, "LIT", "Literature-in-French")
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subj.id, is_active=True))
    await db_session.flush()
    return subj


@pytest.fixture
async def assessment_type(db_session: AsyncSession, school) -> AssessmentType:
    t = AssessmentType(school_id=school.id, name="Class Test", code="CT_ROSTER", weight=Decimal("30.00"))
    db_session.add(t)
    await db_session.flush()
    return t


@pytest.fixture
async def french_assessment(
    db_session: AsyncSession, school, school_class: Class,
    french: Subject, assessment_type: AssessmentType, academic_term: AcademicTerm,
) -> Assessment:
    a = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=french.id,
        assessment_type_id=assessment_type.id, academic_term_id=academic_term.id,
        name="French Mid-Term", max_score=Decimal("100.00"),
    )
    db_session.add(a)
    await db_session.flush()
    return a


@pytest.mark.asyncio
async def test_create_assessment_rejects_subject_not_on_class(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school,
    school_class: Class, assessment_type: AssessmentType, academic_term: AcademicTerm,
):
    """A subject never assigned to the class (no ClassSubject row) can't get an assessment."""
    orphan = await _make_subject(db_session, school, "ORPHAN", "Nobody's Subject")
    resp = await client.post("/assessments", json={
        "class_id": str(school_class.id),
        "subject_id": str(orphan.id),
        "assessment_type_id": str(assessment_type.id),
        "academic_term_id": str(academic_term.id),
        "name": "Should Not Exist",
        "max_score": "100.00",
    }, headers=auth)
    assert resp.status_code == 422
    assert "not assigned" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_roster_excludes_student_registered_for_a_different_subject(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school, school_admin,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm,
    french: Subject, literature: Subject, french_assessment: Assessment,
):
    french_taker = Student(school_id=school.id, admission_number="FR001", first_name="Ama", last_name="Mensah", is_active=True)
    lit_taker = Student(school_id=school.id, admission_number="LIT001", first_name="Kojo", last_name="Owusu", is_active=True)
    db_session.add_all([french_taker, lit_taker])
    await db_session.flush()

    for s in (french_taker, lit_taker):
        await _assign_to_class(db_session, school, s, school_class, academic_year)
    te_french = await _enroll_for_term(db_session, school, french_taker, academic_term, school_admin.id)
    te_lit = await _enroll_for_term(db_session, school, lit_taker, academic_term, school_admin.id)
    db_session.add(SubjectRegistration(school_id=school.id, term_enrollment_id=te_french.id, subject_id=french.id, registration_type="ELECTIVE"))
    db_session.add(SubjectRegistration(school_id=school.id, term_enrollment_id=te_lit.id, subject_id=literature.id, registration_type="ELECTIVE"))
    await db_session.flush()

    resp = await client.get(f"/assessments/{french_assessment.id}/roster", headers=auth)
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.json()}
    assert str(french_taker.id) in ids
    assert str(lit_taker.id) not in ids


@pytest.mark.asyncio
async def test_roster_includes_student_with_no_registration_recorded(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school, school_admin,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm,
    french_assessment: Assessment,
):
    """Backward compatibility: a student never registered for any subject this
    term (the common case for schools that don't use electives at all) still
    shows up — registration data, when absent, doesn't block anyone."""
    unregistered = Student(school_id=school.id, admission_number="NOREG001", first_name="Yaw", last_name="Boateng", is_active=True)
    db_session.add(unregistered)
    await db_session.flush()
    await _assign_to_class(db_session, school, unregistered, school_class, academic_year)
    await _enroll_for_term(db_session, school, unregistered, academic_term, school_admin.id)

    resp = await client.get(f"/assessments/{french_assessment.id}/roster", headers=auth)
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.json()}
    assert str(unregistered.id) in ids


@pytest.mark.asyncio
async def test_submit_scores_rejects_student_registered_for_different_subject(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school, school_admin,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm,
    literature: Subject, french_assessment: Assessment,
):
    lit_taker = Student(school_id=school.id, admission_number="LIT002", first_name="Efua", last_name="Danso", is_active=True)
    db_session.add(lit_taker)
    await db_session.flush()
    await _assign_to_class(db_session, school, lit_taker, school_class, academic_year)
    te = await _enroll_for_term(db_session, school, lit_taker, academic_term, school_admin.id)
    db_session.add(SubjectRegistration(school_id=school.id, term_enrollment_id=te.id, subject_id=literature.id, registration_type="ELECTIVE"))
    await db_session.flush()

    resp = await client.post(f"/assessments/{french_assessment.id}/scores", json={
        "scores": [{"student_id": str(lit_taker.id), "raw_score": "80.00"}],
    }, headers=auth)
    assert resp.status_code == 422
    assert "Efua Danso" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_submit_scores_allows_student_with_no_registration_recorded(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school, school_admin,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm,
    french_assessment: Assessment,
):
    unregistered = Student(school_id=school.id, admission_number="NOREG002", first_name="Abena", last_name="Kufuor", is_active=True)
    db_session.add(unregistered)
    await db_session.flush()
    await _assign_to_class(db_session, school, unregistered, school_class, academic_year)
    await _enroll_for_term(db_session, school, unregistered, academic_term, school_admin.id)

    resp = await client.post(f"/assessments/{french_assessment.id}/scores", json={
        "scores": [{"student_id": str(unregistered.id), "raw_score": "80.00"}],
    }, headers=auth)
    assert resp.status_code == 201
