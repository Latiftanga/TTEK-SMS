"""
Elective-aware class ranking — services/report_card_rank.py::compute_rank().

Ranking used to sum every subject a student had an approved+published score
for, which unfairly compared students taking different electives (one
student's total might include an easy elective, another's a hard one).
Fixed so CORE-registered subjects are what count toward rank, once a school
actually uses subject registration — backward compatible for schools that
never do (the common case for GES Basic, no electives).

Run inside Docker: docker compose exec api pytest app/tests/test_report_card_rank.py -v
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, AcademicYear, Class, SchoolLevel, Subject, SubjectCatalogue, SubjectType
from app.models.assessments import Assessment, AssessmentType, Score
from app.models.school import School
from app.models.students import Student, StudentClassAssignment, SubjectRegistration, TermEnrollment
from app.services.report_card_rank import compute_rank


async def _subject(db: AsyncSession, school: School, code: str, name: str) -> Subject:
    cat = SubjectCatalogue(name=name, code=code, subject_type=SubjectType.ELECTIVE, level=SchoolLevel.SHS)
    db.add(cat)
    await db.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code=code, name=name, is_active=True)
    db.add(subj)
    await db.flush()
    return subj


async def _assessment_type(db: AsyncSession, school: School, code: str) -> AssessmentType:
    at = AssessmentType(school_id=school.id, name=code, code=code, weight=Decimal("100.00"))
    db.add(at)
    await db.flush()
    return at


async def _enroll(
    db: AsyncSession, school: School, student: Student, school_class: Class,
    academic_year: AcademicYear, academic_term: AcademicTerm, enrolled_by_id,
) -> TermEnrollment:
    db.add(StudentClassAssignment(
        school_id=school.id, student_id=student.id, class_id=school_class.id,
        academic_year_id=academic_year.id, is_active=True,
    ))
    te = TermEnrollment(
        school_id=school.id, student_id=student.id, academic_term_id=academic_term.id,
        enrolled_by_id=enrolled_by_id, is_active=True,
    )
    db.add(te)
    await db.flush()
    return te


async def _score(
    db: AsyncSession, school: School, school_class: Class, academic_term: AcademicTerm,
    at: AssessmentType, subject: Subject, student: Student, raw_score: str, entered_by_id,
) -> None:
    # An assessment's identity is (class, subject, term, category, recorded_date)
    # — one per class-wide test event, many Score rows under it (one per
    # student), same as real usage. Reuse today's row for this (class,
    # subject, term, category) instead of creating one per student, which
    # would collide with uq_assessment_category_per_day.
    a = await db.scalar(
        select(Assessment).where(
            Assessment.school_id == school.id,
            Assessment.class_id == school_class.id,
            Assessment.subject_id == subject.id,
            Assessment.assessment_type_id == at.id,
            Assessment.academic_term_id == academic_term.id,
            Assessment.recorded_date == date.today(),
        )
    )
    if a is None:
        a = Assessment(
            school_id=school.id, class_id=school_class.id, subject_id=subject.id,
            assessment_type_id=at.id, academic_term_id=academic_term.id,
            recorded_date=date.today(), max_score=Decimal("100.00"),
            is_published=True,
        )
        db.add(a)
        await db.flush()
    db.add(Score(
        school_id=school.id, assessment_id=a.id, student_id=student.id,
        raw_score=Decimal(raw_score), entered_by_id=entered_by_id, is_approved=True,
    ))
    await db.flush()


@pytest.mark.asyncio
async def test_rank_backward_compatible_no_registration_data(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_year: AcademicYear, academic_term: AcademicTerm, school_admin,
):
    """No SubjectRegistration rows anywhere (a Basic school that never uses
    subject registration) — ranking still sums every subject with a score,
    exactly as before."""
    english = await _subject(db_session, school, "ENG-BC", "English")
    maths = await _subject(db_session, school, "MATH-BC", "Maths")
    at = await _assessment_type(db_session, school, "EOT-BC")

    higher = Student(school_id=school.id, admission_number="RANK001", first_name="Kwesi", last_name="Appiah", is_active=True)
    lower = Student(school_id=school.id, admission_number="RANK002", first_name="Adjoa", last_name="Sarpong", is_active=True)
    db_session.add_all([higher, lower])
    await db_session.flush()

    for s in (higher, lower):
        await _enroll(db_session, school, s, school_class, academic_year, academic_term, school_admin.id)

    await _score(db_session, school, school_class, academic_term, at, english, higher, "90.00", school_admin.id)
    await _score(db_session, school, school_class, academic_term, at, maths, higher, "90.00", school_admin.id)
    await _score(db_session, school, school_class, academic_term, at, english, lower, "50.00", school_admin.id)
    await _score(db_session, school, school_class, academic_term, at, maths, lower, "50.00", school_admin.id)

    higher_rank, class_size = await compute_rank(
        higher.id, school_class.id, academic_term.id, academic_year.id, school.id, db_session,
    )
    lower_rank, _ = await compute_rank(
        lower.id, school_class.id, academic_term.id, academic_year.id, school.id, db_session,
    )
    assert class_size == 2
    assert higher_rank == 1
    assert lower_rank == 2


@pytest.mark.asyncio
async def test_rank_ignores_electives_once_registered(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_year: AcademicYear, academic_term: AcademicTerm, school_admin,
):
    """Kofi has weaker core scores than Kwame but a strong French elective;
    Ama has the same core scores as Kofi but a weak Fine Art elective. Under
    the old bug, Kofi's French score would put him above Kwame overall —
    wrong, since Kwame outperforms him on every subject they actually share.
    Once subjects are registered CORE/ELECTIVE, only the shared core scores
    should decide rank: Kwame must come out on top."""
    english = await _subject(db_session, school, "ENG-EL", "English")
    maths = await _subject(db_session, school, "MATH-EL", "Maths")
    french = await _subject(db_session, school, "FR-EL", "French")
    fine_art = await _subject(db_session, school, "ART-EL", "Fine Art")
    at = await _assessment_type(db_session, school, "EOT-EL")

    kofi = Student(school_id=school.id, admission_number="RANK010", first_name="Kofi", last_name="Mensah", is_active=True)
    ama = Student(school_id=school.id, admission_number="RANK011", first_name="Ama", last_name="Boateng", is_active=True)
    kwame = Student(school_id=school.id, admission_number="RANK012", first_name="Kwame", last_name="Owusu", is_active=True)
    db_session.add_all([kofi, ama, kwame])
    await db_session.flush()

    kofi_te = await _enroll(db_session, school, kofi, school_class, academic_year, academic_term, school_admin.id)
    ama_te = await _enroll(db_session, school, ama, school_class, academic_year, academic_term, school_admin.id)
    kwame_te = await _enroll(db_session, school, kwame, school_class, academic_year, academic_term, school_admin.id)

    for te in (kofi_te, ama_te, kwame_te):
        for subj in (english, maths):
            db_session.add(SubjectRegistration(school_id=school.id, term_enrollment_id=te.id, subject_id=subj.id, registration_type="CORE"))
    db_session.add(SubjectRegistration(school_id=school.id, term_enrollment_id=kofi_te.id, subject_id=french.id, registration_type="ELECTIVE"))
    db_session.add(SubjectRegistration(school_id=school.id, term_enrollment_id=ama_te.id, subject_id=fine_art.id, registration_type="ELECTIVE"))
    await db_session.flush()

    # Core scores: Kwame > Kofi == Ama
    await _score(db_session, school, school_class, academic_term, at, english, kofi, "70.00", school_admin.id)
    await _score(db_session, school, school_class, academic_term, at, maths, kofi, "65.00", school_admin.id)
    await _score(db_session, school, school_class, academic_term, at, english, ama, "70.00", school_admin.id)
    await _score(db_session, school, school_class, academic_term, at, maths, ama, "65.00", school_admin.id)
    await _score(db_session, school, school_class, academic_term, at, english, kwame, "80.00", school_admin.id)
    await _score(db_session, school, school_class, academic_term, at, maths, kwame, "80.00", school_admin.id)
    # Kofi's elective is strong enough to have won the OLD (buggy) ranking outright
    await _score(db_session, school, school_class, academic_term, at, french, kofi, "95.00", school_admin.id)
    await _score(db_session, school, school_class, academic_term, at, fine_art, ama, "20.00", school_admin.id)

    kofi_rank, class_size = await compute_rank(
        kofi.id, school_class.id, academic_term.id, academic_year.id, school.id, db_session,
    )
    kwame_rank, _ = await compute_rank(
        kwame.id, school_class.id, academic_term.id, academic_year.id, school.id, db_session,
    )
    assert class_size == 3
    assert kwame_rank == 1  # best core performance — must win despite having no elective at all
    assert kofi_rank > kwame_rank  # French no longer allowed to outweigh weaker core scores


@pytest.mark.asyncio
async def test_rank_excludes_withdrawn_student(
    db_session: AsyncSession, school: School, school_class: Class,
    academic_year: AcademicYear, academic_term: AcademicTerm, school_admin,
):
    """A student withdrawn/transferred mid-term has their
    StudentClassAssignment and TermEnrollment set is_active=False but the
    rows are left in place (student_lifecycle.py::deactivate_student) — they
    must not inflate class_size or appear in a classmate's ranking."""
    english = await _subject(db_session, school, "ENG-WD", "English")
    at = await _assessment_type(db_session, school, "EOT-WD")

    active = Student(school_id=school.id, admission_number="RANK020", first_name="Yaw", last_name="Darko", is_active=True)
    withdrawn = Student(school_id=school.id, admission_number="RANK021", first_name="Efua", last_name="Asante", is_active=False)
    db_session.add_all([active, withdrawn])
    await db_session.flush()

    await _enroll(db_session, school, active, school_class, academic_year, academic_term, school_admin.id)
    withdrawn_te = await _enroll(db_session, school, withdrawn, school_class, academic_year, academic_term, school_admin.id)

    await _score(db_session, school, school_class, academic_term, at, english, active, "60.00", school_admin.id)
    await _score(db_session, school, school_class, academic_term, at, english, withdrawn, "95.00", school_admin.id)

    # Simulate student_lifecycle.py::deactivate_student's cascade
    withdrawn_sca = await db_session.scalar(
        select(StudentClassAssignment).where(StudentClassAssignment.student_id == withdrawn.id)
    )
    withdrawn_sca.is_active = False
    withdrawn_te.is_active = False
    await db_session.flush()

    rank, class_size = await compute_rank(
        active.id, school_class.id, academic_term.id, academic_year.id, school.id, db_session,
    )
    assert class_size == 1
    assert rank == 1
