"""
Lesson planner tests — CRUD, SubjectTeacher scoping (reused from Assessments
via core/teacher_scope.py::resolve_assessment_scope), week normalization,
and the AI-assist endpoint.

Run inside Docker: docker compose exec api pytest app/tests/test_lesson_plans.py -v
"""
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.academic import (
    AcademicTerm, Class, ClassSubject, SchoolLevel, Subject, SubjectCatalogue,
    SubjectTeacher, SubjectType,
)
from app.models.auth import LoginType, PositionPermission, StaffPosition, User
from app.models.school import School
from app.tests.legacy_position_perms import LEGACY_POSITION_PERMISSIONS


async def _login_as_position(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School, position_code: str,
) -> tuple[dict, str]:
    """Mirrors test_assessment_scope.py's helper."""
    pos = await db_session.scalar(select(StaffPosition).where(StaffPosition.code == position_code))
    if pos is None and position_code in LEGACY_POSITION_PERMISSIONS:
        pos = StaffPosition(school_id=school.id, code=position_code, name=position_code.title(), is_template=False)
        db_session.add(pos)
        await db_session.flush()
        for module, action in LEGACY_POSITION_PERMISSIONS[position_code]:
            db_session.add(PositionPermission(position_id=pos.id, module=module, action=action, is_allowed=True))
        await db_session.flush()
    assert pos is not None, "Run seed_reference_data.py first"

    staff_id = (await client.post("/staff", json={
        "staff_number": f"TST-{position_code}", "first_name": "Test", "last_name": position_code.title(),
    }, headers=auth)).json()["id"]
    await client.patch(f"/staff/{staff_id}", json={"position_ids": [str(pos.id)]}, headers=auth)

    email = f"{position_code.lower()}-lp@presec-test.edu.gh"
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
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, staff_id


@pytest.fixture
async def subject(db_session: AsyncSession, school: School, school_class: Class) -> Subject:
    cat = SubjectCatalogue(name="Mathematics", code="MATH_LP", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code="MATH_LP", name="Mathematics", is_active=True)
    db_session.add(subj)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subj.id, is_active=True))
    await db_session.flush()
    return subj


@pytest.fixture
async def other_subject(db_session: AsyncSession, school: School, school_class: Class) -> Subject:
    cat = SubjectCatalogue(name="Physics", code="PHY_LP", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code="PHY_LP", name="Physics", is_active=True)
    db_session.add(subj)
    await db_session.flush()
    db_session.add(ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subj.id, is_active=True))
    await db_session.flush()
    return subj


async def _make_subject_teacher(
    db_session: AsyncSession, school: School, staff_id: str,
    school_class: Class, subject: Subject, academic_term: AcademicTerm,
) -> None:
    db_session.add(SubjectTeacher(
        school_id=school.id, class_id=school_class.id, subject_id=subject.id,
        staff_member_id=staff_id, academic_year_id=academic_term.academic_year_id, is_active=True,
    ))
    await db_session.flush()


def _payload(academic_term: AcademicTerm, school_class: Class, subject: Subject, week: str = "2024-09-09") -> dict:
    return {
        "class_id": str(school_class.id), "subject_id": str(subject.id),
        "academic_term_id": str(academic_term.id), "week_start_date": week,
        "topic": "Introduction to Fractions",
    }


# ── CRUD + scoping ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_and_get_lesson_plan(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)

    resp = await client.post("/lesson-plans", json=_payload(academic_term, school_class, subject), headers=teacher_auth)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["topic"] == "Introduction to Fractions"
    assert data["week_start_date"] == "2024-09-09"  # already a Monday, unchanged
    assert data["created_by_id"] == staff_id

    get_resp = await client.get(f"/lesson-plans/{data['id']}", headers=teacher_auth)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == data["id"]


@pytest.mark.asyncio
async def test_week_start_normalized_to_monday(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)

    # 2024-09-11 is a Wednesday; that week's Monday is 2024-09-09.
    resp = await client.post(
        "/lesson-plans", json=_payload(academic_term, school_class, subject, week="2024-09-11"), headers=teacher_auth,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["week_start_date"] == "2024-09-09"


@pytest.mark.asyncio
async def test_create_rejects_week_outside_term_range(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)

    # Term runs 2024-09-01 to 2024-12-20 (conftest.py's academic_term fixture).
    resp = await client.post(
        "/lesson-plans", json=_payload(academic_term, school_class, subject, week="2025-02-03"), headers=teacher_auth,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_rejects_duplicate_week_with_409(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)

    first = await client.post("/lesson-plans", json=_payload(academic_term, school_class, subject), headers=teacher_auth)
    assert first.status_code == 201
    second = await client.post("/lesson-plans", json=_payload(academic_term, school_class, subject), headers=teacher_auth)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_create_404_for_non_owning_subject_teacher(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None,
):
    """A TEACHER with zero SubjectTeacher rows at all — mirrors
    test_assessment_scope.py's convention for the "not assigned" case."""
    teacher_auth, _staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    resp = await client.post("/lesson-plans", json=_payload(academic_term, school_class, subject), headers=teacher_auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_404_for_different_subject_same_class(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, other_subject: Subject, academic_term: AcademicTerm, redis_permissions: None,
):
    """A subject teacher assigned to `subject` can't plan lessons for
    `other_subject` in the same class."""
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)

    resp = await client.post(
        "/lesson-plans", json=_payload(academic_term, school_class, other_subject), headers=teacher_auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_and_delete_lesson_plan(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)

    created = (await client.post(
        "/lesson-plans", json=_payload(academic_term, school_class, subject), headers=teacher_auth,
    )).json()

    patched = await client.patch(
        f"/lesson-plans/{created['id']}", json={"activities": "Group work on fraction addition"}, headers=teacher_auth,
    )
    assert patched.status_code == 200
    assert patched.json()["activities"] == "Group work on fraction addition"
    assert patched.json()["topic"] == "Introduction to Fractions"  # untouched fields survive

    deleted = await client.delete(f"/lesson-plans/{created['id']}", headers=teacher_auth)
    assert deleted.status_code == 204
    gone = await client.get(f"/lesson-plans/{created['id']}", headers=teacher_auth)
    assert gone.status_code == 404


@pytest.mark.asyncio
async def test_list_unrestricted_for_approve_scores_holder(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None,
):
    """HEAD holds assessments.approve_scores — unrestricted, same bypass as
    Assessments, with zero SubjectTeacher row of their own."""
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    created = (await client.post(
        "/lesson-plans", json=_payload(academic_term, school_class, subject), headers=teacher_auth,
    )).json()

    head_auth, _ = await _login_as_position(client, auth, db_session, school, "HEAD")
    resp = await client.get(
        "/lesson-plans",
        params={
            "class_id": str(school_class.id), "subject_id": str(subject.id),
            "academic_term_id": str(academic_term.id), "week_start_date": "2024-09-09",
        },
        headers=head_auth,
    )
    assert resp.status_code == 200
    assert [p["id"] for p in resp.json()] == [created["id"]]


# ── AI-assist ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ai_draft_503_when_no_provider_configured(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)

    resp = await client.post(
        "/lesson-plans/ai-draft",
        json={"class_id": str(school_class.id), "subject_id": str(subject.id), "topic": "Fractions"},
        headers=teacher_auth,
    )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_ai_draft_429_when_daily_limit_exhausted(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None,
):
    from app.core.redis import redis_client
    from app.models.school import AiConfig, AiProvider

    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)

    db_session.add(AiConfig(
        school_id=school.id, provider=AiProvider.GEMINI, api_key="fake-key",
        daily_limit_per_teacher=1, is_active=True,
    ))
    await db_session.flush()

    me = await client.get("/auth/me", headers=teacher_auth)
    user_id = me.json()["id"]
    key = f"ai_usage:{school.id}:{user_id}:{date.today().isoformat()}"
    await redis_client.set(key, "1")
    try:
        resp = await client.post(
            "/lesson-plans/ai-draft",
            json={"class_id": str(school_class.id), "subject_id": str(subject.id), "topic": "Fractions"},
            headers=teacher_auth,
        )
        assert resp.status_code == 429
    finally:
        await redis_client.delete(key)


@pytest.mark.asyncio
async def test_ai_draft_success(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    from app.models.school import AiConfig, AiProvider
    from app.services import ai_config as ai_config_module

    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)

    db_session.add(AiConfig(
        school_id=school.id, provider=AiProvider.GEMINI, api_key="fake-key",
        daily_limit_per_teacher=10, is_active=True,
    ))
    await db_session.flush()

    class _StubDriver:
        async def generate(self, prompt: str, system: str = "") -> str:
            return "Learning Objectives: students will add fractions.\nActivities: worked examples."

    monkeypatch.setattr(ai_config_module, "build_ai_driver", lambda provider, api_key, model: _StubDriver())

    resp = await client.post(
        "/lesson-plans/ai-draft",
        json={"class_id": str(school_class.id), "subject_id": str(subject.id), "topic": "Fractions"},
        headers=teacher_auth,
    )
    assert resp.status_code == 200, resp.text
    assert "add fractions" in resp.json()["draft_text"]
