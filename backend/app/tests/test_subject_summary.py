"""
Subject-level summary — aggregates ClassSubject/SubjectTeacher/
SubjectRegistration across every class in the school that offers a
subject, something nothing else in the codebase does (everything else is
scoped to one class_id at a time).

Run inside Docker: docker compose exec api pytest app/tests/test_subject_summary.py -v
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import (
    AcademicTerm, AcademicYear, Class, ClassSubject,
    SchoolLevel, Subject, SubjectCatalogue, SubjectType,
)
from app.models.auth import User
from app.models.school import School
from app.models.students import Student, StudentClassAssignment, SubjectRegistration, TermEnrollment


async def _make_subject(db_session: AsyncSession, school: School, code: str, name: str) -> Subject:
    cat = SubjectCatalogue(name=name, code=code, subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code=code, name=name, is_active=True)
    db_session.add(subj)
    await db_session.flush()
    return subj


async def _make_class(db_session: AsyncSession, school: School, stream: str) -> Class:
    cls = Class(school_id=school.id, level="SHS", year_group=2, stream=stream, is_active=True)
    db_session.add(cls)
    await db_session.flush()
    return cls


async def _offer_subject(db_session: AsyncSession, school: School, cls: Class, subj: Subject) -> None:
    db_session.add(ClassSubject(school_id=school.id, class_id=cls.id, subject_id=subj.id, is_active=True))
    await db_session.flush()


async def _enroll_student(
    db_session: AsyncSession, school: School, cls: Class,
    academic_year: AcademicYear, academic_term: AcademicTerm, enrolled_by_id, suffix: str,
) -> Student:
    student = Student(
        school_id=school.id, admission_number=f"SUMM{suffix}", first_name="Test", last_name=suffix, is_active=True,
    )
    db_session.add(student)
    await db_session.flush()
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=cls.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    db_session.add(TermEnrollment(
        school_id=school.id, student_id=student.id, academic_term_id=academic_term.id,
        enrolled_by_id=enrolled_by_id, is_active=True,
    ))
    await db_session.flush()
    return student


@pytest.mark.asyncio
async def test_summary_aggregates_across_classes(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    academic_year: AcademicYear, academic_term: AcademicTerm,
):
    subj = await _make_subject(db_session, school, "SUMM_ENG", "English")
    class_a = await _make_class(db_session, school, "A")
    class_b = await _make_class(db_session, school, "B")
    await _offer_subject(db_session, school, class_a, subj)
    await _offer_subject(db_session, school, class_b, subj)

    s1 = await _enroll_student(db_session, school, class_a, academic_year, academic_term, school_admin.id, "1")
    s2 = await _enroll_student(db_session, school, class_a, academic_year, academic_term, school_admin.id, "2")
    s3 = await _enroll_student(db_session, school, class_b, academic_year, academic_term, school_admin.id, "3")

    # Register s1+s2 (class A) and s3 (class B) for the subject.
    for s in (s1, s2, s3):
        te = await db_session.scalar(
            select(TermEnrollment).where(TermEnrollment.student_id == s.id)
        )
        db_session.add(SubjectRegistration(
            school_id=school.id, term_enrollment_id=te.id, subject_id=subj.id, registration_type="CORE",
        ))
    await db_session.flush()

    # Assign a teacher only to class A.
    staff_id = (await client.post("/staff", json={
        "staff_number": "SUMM-T1", "first_name": "Ama", "last_name": "Owusu",
    }, headers=auth)).json()["id"]
    resp = await client.post(f"/academic/classes/{class_a.id}/subject-teachers", json={
        "subject_id": str(subj.id), "staff_member_id": staff_id, "academic_year_id": str(academic_year.id),
    }, headers=auth)
    assert resp.status_code in (200, 201)

    resp = await client.get(
        f"/academic/subjects/{subj.id}/summary",
        params={"academic_term_id": str(academic_term.id)}, headers=auth,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_classes"] == 2
    assert data["classes_without_teacher"] == 1
    assert data["total_students_registered"] == 3

    by_class = {c["class_id"]: c for c in data["classes"]}
    assert by_class[str(class_a.id)]["teacher_name"] == "Ama Owusu"
    assert by_class[str(class_a.id)]["registered_count"] == 2
    assert by_class[str(class_b.id)]["teacher_name"] is None
    assert by_class[str(class_b.id)]["registered_count"] == 1


@pytest.mark.asyncio
async def test_summary_empty_when_no_classes_offer_it(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, academic_term: AcademicTerm,
):
    subj = await _make_subject(db_session, school, "SUMM_ORPHAN", "Orphan Subject")
    resp = await client.get(
        f"/academic/subjects/{subj.id}/summary",
        params={"academic_term_id": str(academic_term.id)}, headers=auth,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "subject_id": str(subj.id), "subject_name": "Orphan Subject",
        "total_classes": 0, "classes_without_teacher": 0, "total_students_registered": 0, "classes": [],
    }


@pytest.mark.asyncio
async def test_summary_404_cross_school_subject(
    client: AsyncClient, auth: dict, db_session: AsyncSession, academic_term: AcademicTerm,
):
    resp = await client.get(
        f"/academic/subjects/{uuid.uuid4()}/summary",
        params={"academic_term_id": str(academic_term.id)}, headers=auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_summary_404_bogus_term(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    subj = await _make_subject(db_session, school, "SUMM_TERM404", "Term404 Subject")
    resp = await client.get(
        f"/academic/subjects/{subj.id}/summary",
        params={"academic_term_id": str(uuid.uuid4())}, headers=auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_summary_excludes_withdrawn_student_with_stale_active_assignment(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, school_admin: User,
    academic_year: AcademicYear, academic_term: AcademicTerm,
):
    """A withdrawn student (Student.is_active=False) whose
    StudentClassAssignment row was never deactivated in lockstep (stale
    data — confirmed live on the real dev DB) must not be counted as
    currently registered."""
    subj = await _make_subject(db_session, school, "SUMM_WITHDRAWN", "Withdrawn Test Subject")
    cls = await _make_class(db_session, school, "W")
    await _offer_subject(db_session, school, cls, subj)

    student = Student(
        school_id=school.id, admission_number="SUMMWD1", first_name="With", last_name="Drawn", is_active=False,
    )
    db_session.add(student)
    await db_session.flush()
    db_session.add(StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=cls.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    te = TermEnrollment(
        school_id=school.id, student_id=student.id, academic_term_id=academic_term.id,
        enrolled_by_id=school_admin.id, is_active=True,
    )
    db_session.add(te)
    await db_session.flush()
    db_session.add(SubjectRegistration(
        school_id=school.id, term_enrollment_id=te.id, subject_id=subj.id, registration_type="CORE",
    ))
    await db_session.flush()

    resp = await client.get(
        f"/academic/subjects/{subj.id}/summary",
        params={"academic_term_id": str(academic_term.id)}, headers=auth,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_students_registered"] == 0
    assert data["classes"][0]["registered_count"] == 0
