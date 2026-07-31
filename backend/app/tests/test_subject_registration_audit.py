"""
Two gaps found during a design-pattern comparison review, both fixed here:

1. register_subjects()/delete_subject_registration() called
   check_term_lock_override() but discarded the returned reason, and no
   audit table existed for subject-registration changes at all — the same
   gap already found and fixed for scores (ScoreAuditLog), assessments
   (AssessmentAuditLog), and behaviour records (BehaviourAuditLog).
   SubjectRegistrationAuditLog closes it the same way.
2. Score has no FK to SubjectRegistration, so removing a registration never
   deletes existing scores — but it does silently block future score edits
   for that student/subject. get_subject_roster() now reports has_scores so
   the UI can warn before an uncheck creates that trap.

Run inside Docker: docker compose exec api pytest app/tests/test_subject_registration_audit.py -v
"""
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import (
    AcademicTerm, AcademicYear, Class, ClassSubject,
    SchoolLevel, Subject, SubjectCatalogue, SubjectType,
)
from app.models.assessments import Assessment, AssessmentType, Score
from app.models.auth import User
from app.models.school import School
from app.models.students import (
    Student, StudentClassAssignment, SubjectRegistration,
    SubjectRegistrationAuditLog, TermEnrollment,
)


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
) -> tuple[Student, TermEnrollment]:
    student = Student(
        school_id=school.id, admission_number=f"AUDIT{suffix}", first_name="Test", last_name=suffix, is_active=True,
    )
    db_session.add(student)
    await db_session.flush()
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=school_class.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    te = TermEnrollment(
        school_id=school.id, student_id=student.id, academic_term_id=academic_term.id,
        enrolled_by_id=enrolled_by_id, is_active=True,
    )
    db_session.add(te)
    await db_session.flush()
    return student, te


@pytest.fixture
async def subject(db_session: AsyncSession, school: School, school_class: Class) -> Subject:
    subj = await _make_subject(db_session, school, "AUDIT_SUBJ", "Audit Test Subject")
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subj.id, is_active=True))
    await db_session.flush()
    return subj


# ── Audit log ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_subjects_writes_create_audit_log(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm, subject: Subject,
):
    student, te = await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "A")

    resp = await client.post(f"/students/term-enrollments/{te.id}/subjects", json={
        "items": [{"subject_id": str(subject.id), "registration_type": "CORE"}],
    }, headers=auth)
    assert resp.status_code == 201
    reg_id = resp.json()[0]["id"]

    log = await db_session.scalar(
        select(SubjectRegistrationAuditLog).where(SubjectRegistrationAuditLog.registration_id == reg_id)
    )
    assert log is not None
    assert log.action == "CREATE"
    assert log.term_enrollment_id == te.id
    assert log.subject_id == subject.id
    assert log.registration_type == "CORE"
    assert log.reason is None   # term wasn't locked — no override happened


@pytest.mark.asyncio
async def test_delete_subject_registration_writes_delete_audit_log(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm, subject: Subject,
):
    student, te = await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "B")
    reg_id = (await client.post(f"/students/term-enrollments/{te.id}/subjects", json={
        "items": [{"subject_id": str(subject.id), "registration_type": "CORE"}],
    }, headers=auth)).json()[0]["id"]

    resp = await client.delete(f"/students/term-enrollments/{te.id}/subjects/{reg_id}", headers=auth)
    assert resp.status_code == 204

    log = await db_session.scalar(
        select(SubjectRegistrationAuditLog).where(
            SubjectRegistrationAuditLog.registration_id.is_(None),
            SubjectRegistrationAuditLog.term_enrollment_id == te.id,
            SubjectRegistrationAuditLog.action == "DELETE",
        )
    )
    # registration_id is SET NULL once the row it points to is deleted —
    # confirm the log survived and correctly lost its FK, not the row itself.
    assert log is not None
    assert log.subject_id == subject.id


@pytest.mark.asyncio
async def test_audit_log_captures_override_reason_not_discarded(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm, subject: Subject,
):
    student, te = await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "C")
    academic_term.results_locked = True
    await db_session.flush()

    resp = await client.post(f"/students/term-enrollments/{te.id}/subjects", json={
        "items": [{"subject_id": str(subject.id), "registration_type": "CORE"}],
        "override_reason": "Late registration approved by exams office.",
    }, headers=auth)
    assert resp.status_code == 201
    reg_id = resp.json()[0]["id"]

    log = await db_session.scalar(
        select(SubjectRegistrationAuditLog).where(SubjectRegistrationAuditLog.registration_id == reg_id)
    )
    assert log.reason == "Late registration approved by exams office."


# ── has_scores on the roster ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_roster_reports_has_scores_for_a_student_with_a_score(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm, subject: Subject,
):
    scored, _te1 = await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "D")
    unscored, _te2 = await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "E")

    atype = AssessmentType(school_id=school.id, name="Class Test", code="CT_AUDIT", weight=Decimal("30.00"))
    db_session.add(atype)
    await db_session.flush()
    assessment = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        assessment_type_id=atype.id, academic_term_id=academic_term.id,
        name="Audit Test Assessment", max_score=Decimal("100.00"),
    )
    db_session.add(assessment)
    await db_session.flush()
    db_session.add(Score(
        school_id=school.id, assessment_id=assessment.id, student_id=scored.id,
        raw_score=Decimal("75.00"), entered_by_id=school_admin.id,
    ))
    await db_session.flush()

    resp = await client.get(
        f"/students/classes/{school_class.id}/subjects/{subject.id}/roster",
        params={"academic_term_id": str(academic_term.id)}, headers=auth,
    )
    assert resp.status_code == 200
    by_id = {row["student_id"]: row for row in resp.json()}
    assert by_id[str(scored.id)]["has_scores"] is True
    assert by_id[str(unscored.id)]["has_scores"] is False


@pytest.mark.asyncio
async def test_unregistering_scored_student_does_not_delete_the_score(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    school_class: Class, academic_year: AcademicYear, academic_term: AcademicTerm, subject: Subject,
):
    """Backend never blocks the removal (only the frontend warns) — and the
    score itself must survive untouched, since Score has no FK to
    SubjectRegistration at all."""
    student, te = await _enroll_student(db_session, school, school_class, academic_year, academic_term, school_admin.id, "F")

    atype = AssessmentType(school_id=school.id, name="Class Test", code="CT_AUDIT2", weight=Decimal("30.00"))
    db_session.add(atype)
    await db_session.flush()
    assessment = Assessment(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        assessment_type_id=atype.id, academic_term_id=academic_term.id,
        name="Audit Test Assessment 2", max_score=Decimal("100.00"),
    )
    db_session.add(assessment)
    await db_session.flush()
    score = Score(
        school_id=school.id, assessment_id=assessment.id, student_id=student.id,
        raw_score=Decimal("60.00"), entered_by_id=school_admin.id,
    )
    db_session.add(score)
    await db_session.flush()
    score_id = score.id

    resp = await client.post(
        f"/students/classes/{school_class.id}/subjects/{subject.id}/roster",
        json={"academic_term_id": str(academic_term.id), "student_ids": [str(student.id)]}, headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["registered"] == 1

    # Now unregister.
    resp = await client.post(
        f"/students/classes/{school_class.id}/subjects/{subject.id}/roster",
        json={"academic_term_id": str(academic_term.id), "student_ids": []}, headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["removed"] == 1

    surviving_score = await db_session.get(Score, score_id)
    assert surviving_score is not None
    assert surviving_score.raw_score == Decimal("60.00")
