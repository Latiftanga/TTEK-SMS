"""
AI-assisted lesson plan generation — skeleton -> expand workflow, targeted
regeneration, and the approval/review workflow. Reuses test_lesson_plans.py's
fixture/helper shapes and test_attendance_periods.py's calendar/period
helpers (occurrence resolution needs real SchoolCalendar/SchoolPeriod/
TimetableSlot rows, exactly like period-level attendance did).

Run inside Docker: docker compose exec api pytest app/tests/test_lesson_plan_generation.py -v
"""
import json
from datetime import date, time

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import (
    AcademicTerm, Class, ClassSubject, SchoolLevel, Subject, SubjectCatalogue,
    SubjectTeacher, SubjectType, TimetableSlot,
)
from app.models.attendance import DayType, SchoolCalendar, SchoolPeriod
from app.models.auth import StaffPermission, StaffPosition
from app.models.school import AiConfig, AiProvider
from app.models.school import School
from app.services import ai_config as ai_config_module
from app.tests.test_attendance_periods import _weekday_of
from app.tests.test_lesson_plans import _login_as_position, _make_subject_teacher, _payload


@pytest.fixture
async def subject(db_session: AsyncSession, school: School, school_class: Class) -> Subject:
    cat = SubjectCatalogue(name="Mathematics", code="MATH_LPG", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code="MATH_LPG", name="Mathematics", is_active=True)
    db_session.add(subj)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subj.id, is_active=True))
    await db_session.flush()
    return subj


async def _add_period_and_slot(
    db_session: AsyncSession, school: School, school_class: Class, subject: Subject,
    academic_term: AcademicTerm, d: date, *, number: int,
) -> tuple[SchoolCalendar, SchoolPeriod]:
    cal = SchoolCalendar(school_id=school.id, date=d, day_type=DayType.SCHOOL_DAY, academic_term_id=academic_term.id)
    db_session.add(cal)
    period = SchoolPeriod(
        school_id=school.id, name=f"Period {number}", day_of_week=_weekday_of(d),
        period_number=number, start_time=time(8 + number, 0), end_time=time(8 + number, 45),
    )
    db_session.add(period)
    await db_session.flush()
    db_session.add(TimetableSlot(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        academic_year_id=academic_term.academic_year_id, period_id=period.id,
    ))
    await db_session.flush()
    return cal, period


def _skeleton_json() -> str:
    return json.dumps({
        "essential_questions": ["What is a fraction?"],
        "pedagogical_strategies": ["Think-pair-share"],
        "teaching_learning_resources": ["Fraction tiles"],
        "differentiation_notes": "Pair struggling learners with peer tutors.",
    })


def _lessons_json(n: int, *, prefix: str = "Lesson") -> str:
    return json.dumps({
        "lessons": [
            {"introduction": f"{prefix} {i} intro", "main_lesson": f"{prefix} {i} main", "closure": f"{prefix} {i} close"}
            for i in range(1, n + 1)
        ],
        "assessment": {
            "formative": {"mode": "Oral", "task": "Quick quiz", "mark_scheme": "1 pt each"},
            "transcript_assessment": {"mode": "Written", "task": "Worksheet", "rubric": "3-2-1 rubric"},
        },
    })


def _lesson_body_json(intro="New intro", main="New main", closure="New closure") -> str:
    return json.dumps({"introduction": intro, "main_lesson": main, "closure": closure})


class _StubDriver:
    def __init__(self, response: str):
        self._response = response

    async def generate(self, prompt: str, system: str = "") -> str:
        return self._response


def _patch_driver(monkeypatch, response: str) -> None:
    monkeypatch.setattr(ai_config_module, "build_ai_driver", lambda *a, **kw: _StubDriver(response))


async def _create_plan(client: AsyncClient, teacher_auth: dict, academic_term, school_class, subject) -> dict:
    resp = await client.post("/lesson-plans", json=_payload(academic_term, school_class, subject), headers=teacher_auth)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _with_ai_config(db_session: AsyncSession, school: School) -> None:
    db_session.add(AiConfig(school_id=school.id, provider=AiProvider.GEMINI, api_key="fake-key", daily_limit_per_teacher=10, is_active=True))
    await db_session.flush()


# ── generate-skeleton ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_skeleton_success(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    await _with_ai_config(db_session, school)
    _patch_driver(monkeypatch, _skeleton_json())

    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)
    resp = await client.post(f"/lesson-plans/{lp['id']}/generate-skeleton", headers=teacher_auth)
    assert resp.status_code == 200, resp.text
    content = resp.json()["generated_content"]
    assert content["essential_questions"] == ["What is a fraction?"]
    assert content["lessons"] == []


@pytest.mark.asyncio
async def test_generate_skeleton_503_when_no_provider(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)

    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)
    resp = await client.post(f"/lesson-plans/{lp['id']}/generate-skeleton", headers=teacher_auth)
    assert resp.status_code == 503


def _skeleton_json_with_reference() -> str:
    return json.dumps({
        "essential_questions": ["What is a fraction?"],
        "pedagogical_strategies": ["Think-pair-share"],
        "teaching_learning_resources": ["Fraction tiles"],
        "differentiation_notes": "Pair struggling learners with peer tutors.",
        "content_standard": "Number — Fractions",
        "indicator": "B7.1.1.1",
        "learning_objectives": "By the end of the lesson, learners will add simple fractions.",
    })


@pytest.mark.asyncio
async def test_generate_skeleton_proposes_curriculum_reference_when_blank(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    """A teacher never has to type content_standard/indicator/learning_objectives
    — generate-skeleton proposes them as part of the same call."""
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    await _with_ai_config(db_session, school)
    _patch_driver(monkeypatch, _skeleton_json_with_reference())

    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)
    assert lp["content_standard"] is None
    resp = await client.post(f"/lesson-plans/{lp['id']}/generate-skeleton", headers=teacher_auth)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["content_standard"] == "Number — Fractions"
    assert data["indicator"] == "B7.1.1.1"
    assert data["learning_objectives"] == "By the end of the lesson, learners will add simple fractions."


@pytest.mark.asyncio
async def test_generate_skeleton_never_overwrites_existing_content_standard(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    await _with_ai_config(db_session, school)

    resp = await client.post("/lesson-plans", json={
        **_payload(academic_term, school_class, subject),
        "content_standard": "Teacher-entered standard",
    }, headers=teacher_auth)
    assert resp.status_code == 201, resp.text
    lp = resp.json()
    assert lp["content_standard"] == "Teacher-entered standard"

    _patch_driver(monkeypatch, _skeleton_json_with_reference())  # would propose a different value
    resp = await client.post(f"/lesson-plans/{lp['id']}/generate-skeleton", headers=teacher_auth)
    assert resp.status_code == 200, resp.text
    assert resp.json()["content_standard"] == "Teacher-entered standard"


# ── generate-lessons ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_lessons_requires_skeleton_first(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)

    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)
    resp = await client.post(f"/lesson-plans/{lp['id']}/generate-lessons", headers=teacher_auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_generate_lessons_excludes_holiday(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    """Week 2024-09-09 (Mon) to 2024-09-15 (Sun) — two timetabled days
    (Mon+Wed), Wed is a public holiday, so exactly 1 real occurrence should
    resolve. Proves the occurrence resolver's day_type filter is load-bearing,
    not just "any TimetableSlot in the week counts"."""
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    await _with_ai_config(db_session, school)

    await _add_period_and_slot(db_session, school, school_class, subject, academic_term, date(2024, 9, 9), number=1)
    holiday_cal, _ = await _add_period_and_slot(db_session, school, school_class, subject, academic_term, date(2024, 9, 11), number=2)
    holiday_cal.day_type = DayType.PUBLIC_HOLIDAY
    await db_session.flush()

    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)
    _patch_driver(monkeypatch, _skeleton_json())
    skel = await client.post(f"/lesson-plans/{lp['id']}/generate-skeleton", headers=teacher_auth)
    assert skel.status_code == 200

    _patch_driver(monkeypatch, _lessons_json(1))
    resp = await client.post(f"/lesson-plans/{lp['id']}/generate-lessons", headers=teacher_auth)
    assert resp.status_code == 200, resp.text
    lessons = resp.json()["generated_content"]["lessons"]
    assert len(lessons) == 1
    assert lessons[0]["lesson_date"] == "2024-09-09"


@pytest.mark.asyncio
async def test_generate_lessons_ai_count_mismatch_502(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    await _with_ai_config(db_session, school)
    await _add_period_and_slot(db_session, school, school_class, subject, academic_term, date(2024, 9, 9), number=1)

    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)
    _patch_driver(monkeypatch, _skeleton_json())
    await client.post(f"/lesson-plans/{lp['id']}/generate-skeleton", headers=teacher_auth)

    _patch_driver(monkeypatch, _lessons_json(2))  # 1 real occurrence, AI returns 2
    resp = await client.post(f"/lesson-plans/{lp['id']}/generate-lessons", headers=teacher_auth)
    assert resp.status_code == 502


# ── regenerate-lesson ────────────────────────────────────────────────────────

async def _generate_two_lessons(client, teacher_auth, db_session, school, school_class, subject, academic_term, monkeypatch) -> dict:
    await _with_ai_config(db_session, school)
    await _add_period_and_slot(db_session, school, school_class, subject, academic_term, date(2024, 9, 9), number=1)
    await _add_period_and_slot(db_session, school, school_class, subject, academic_term, date(2024, 9, 10), number=2)
    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)
    _patch_driver(monkeypatch, _skeleton_json())
    await client.post(f"/lesson-plans/{lp['id']}/generate-skeleton", headers=teacher_auth)
    _patch_driver(monkeypatch, _lessons_json(2))
    resp = await client.post(f"/lesson-plans/{lp['id']}/generate-lessons", headers=teacher_auth)
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_regenerate_lesson_only_touches_target(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    lp = await _generate_two_lessons(client, teacher_auth, db_session, school, school_class, subject, academic_term, monkeypatch)
    target = lp["generated_content"]["lessons"][0]
    untouched = lp["generated_content"]["lessons"][1]

    _patch_driver(monkeypatch, _lesson_body_json())
    resp = await client.post(
        f"/lesson-plans/{lp['id']}/regenerate-lesson", headers=teacher_auth,
        json={"school_calendar_id": target["school_calendar_id"], "period_id": target["period_id"]},
    )
    assert resp.status_code == 200, resp.text
    lessons = resp.json()["generated_content"]["lessons"]
    changed = next(l for l in lessons if l["period_id"] == target["period_id"])
    same = next(l for l in lessons if l["period_id"] == untouched["period_id"])
    assert changed["introduction"] == "New intro"
    assert same["introduction"] == untouched["introduction"]


@pytest.mark.asyncio
async def test_regenerate_lesson_404_for_unknown_occurrence(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    lp = await _generate_two_lessons(client, teacher_auth, db_session, school, school_class, subject, academic_term, monkeypatch)

    resp = await client.post(
        f"/lesson-plans/{lp['id']}/regenerate-lesson", headers=teacher_auth,
        json={"school_calendar_id": str(academic_term.id), "period_id": str(academic_term.id)},
    )
    assert resp.status_code == 404


# ── review / approval workflow ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_review_approve_success_without_ai_content(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None,
):
    """A plan with zero AI generation at all can still be approved — the
    approval workflow doesn't require having used AI generation."""
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)

    head_auth, head_staff_id = await _login_as_position(client, auth, db_session, school, "HEAD")
    resp = await client.patch(
        f"/lesson-plans/{lp['id']}/review", headers=head_auth,
        json={"status": "APPROVED", "review_notes": "Looks good"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "APPROVED"
    assert data["reviewed_by_staff_id"] == head_staff_id
    assert data["review_notes"] == "Looks good"
    assert data["reviewed_at"] is not None


@pytest.mark.asyncio
async def test_review_forbidden_for_manage_only_holder(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)

    resp = await client.patch(
        f"/lesson-plans/{lp['id']}/review", headers=teacher_auth, json={"status": "APPROVED"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_review_blocked_on_occurrence_mismatch(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    lp = await _generate_two_lessons(client, teacher_auth, db_session, school, school_class, subject, academic_term, monkeypatch)

    # Timetable changed after generation: retire one of the two TimetableSlots.
    slot = await db_session.scalar(select(TimetableSlot).where(TimetableSlot.class_id == school_class.id, TimetableSlot.subject_id == subject.id).limit(1))
    await db_session.delete(slot)
    await db_session.flush()

    head_auth, _ = await _login_as_position(client, auth, db_session, school, "HEAD")
    resp = await client.patch(f"/lesson-plans/{lp['id']}/review", headers=head_auth, json={"status": "APPROVED"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_review_reviewer_unrestricted_without_subject_teacher_scope(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None,
):
    """A staff member holding ONLY lesson_plans.approve (via a personal
    override, not assessments.approve_scores, not a SubjectTeacher on this
    class) can still review ANY plan — the review action is unrestricted by
    design once the caller clears the router-level permission gate."""
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)

    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == "TEACHER"))
    reviewer_id = (await client.post("/staff", json={
        "staff_number": "TST-REVIEWER", "first_name": "Rev", "last_name": "Iewer",
    }, headers=auth)).json()["id"]
    await client.patch(f"/staff/{reviewer_id}", json={"position_ids": [str(pos.id)]}, headers=auth)
    db_session.add(StaffPermission(
        school_id=school.id, staff_member_id=reviewer_id, module="lesson_plans", action="approve", is_allowed=True,
    ))
    await db_session.flush()

    from app.core.auth import hash_password
    from app.models.auth import LoginType, User
    db_session.add(User(
        school_id=school.id, login_type=LoginType.EMAIL, email="reviewer-lp@presec-test.edu.gh",
        password_hash=hash_password("Whatever123!"), is_active=True, staff_member_id=reviewer_id,
    ))
    await db_session.flush()
    login = await client.post("/auth/login", json={
        "login_type": "EMAIL", "identifier": "reviewer-lp@presec-test.edu.gh", "password": "Whatever123!",
        "school_code": school.school_code,
    })
    assert login.status_code == 200, login.text
    reviewer_auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.patch(f"/lesson-plans/{lp['id']}/review", headers=reviewer_auth, json={"status": "APPROVED"})
    assert resp.status_code == 200, resp.text
