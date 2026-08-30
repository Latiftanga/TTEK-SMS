"""
Curriculum-grounded chat assistant — send/list messages, and finalize a
conversation into the same GeneratedContent shape the button-driven
generate_lessons() produces.

Run inside Docker: docker compose exec api pytest app/tests/test_lesson_plan_chat.py -v
"""
import json
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from weasyprint import HTML

from app.models.academic import AcademicTerm, Class, Subject
from app.models.school import AiConfig, AiProvider, School
from app.services import ai_config as ai_config_module
from app.tests.test_curriculum_materials import class_subject  # noqa: F401 — reused fixture
from app.tests.test_lesson_plan_generation import _add_period_and_slot  # noqa: F401
from app.tests.test_lesson_plans import _login_as_position, _make_subject_teacher, _payload, subject  # noqa: F401


class _StubDriver:
    def __init__(self, response: str):
        self._response = response

    async def generate(self, prompt: str, system: str = "") -> str:
        return self._response


def _patch_driver(monkeypatch, response: str) -> None:
    monkeypatch.setattr(ai_config_module, "build_ai_driver", lambda *a, **kw: _StubDriver(response))


class _CountingStubDriver:
    """Every instance shares `call_log` (captured by closure in
    _patch_counting_driver) — build_ai_driver() is called fresh per message
    (a new driver instance each time), but the call count must accumulate
    across messages within one test to verify "only the first message
    proposes a curriculum reference."""
    def __init__(self, response: str, call_log: list[str]):
        self._response = response
        self._call_log = call_log

    async def generate(self, prompt: str, system: str = "") -> str:
        self._call_log.append(prompt)
        return self._response


def _patch_counting_driver(monkeypatch, response: str, call_log: list[str]) -> None:
    monkeypatch.setattr(ai_config_module, "build_ai_driver", lambda *a, **kw: _CountingStubDriver(response, call_log))


async def _with_ai_config(db_session: AsyncSession, school: School) -> None:
    db_session.add(AiConfig(school_id=school.id, provider=AiProvider.GEMINI, api_key="fake-key", daily_limit_per_teacher=10, is_active=True))
    await db_session.flush()


async def _create_plan(client, teacher_auth, academic_term, school_class, subject) -> dict:
    resp = await client.post("/lesson-plans", json=_payload(academic_term, school_class, subject), headers=teacher_auth)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_send_message_grounds_reply_in_curriculum_excerpt(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, class_subject, subject: Subject, academic_term: AcademicTerm,
    redis_permissions: None, monkeypatch,
):
    """subject/class_subject fixtures must agree — class_subject wraps a
    DIFFERENT subject (MATH_CM) than test_lesson_plans.py's own `subject`
    fixture, so this test uses class_subject.subject_id directly rather than
    the unrelated `subject` fixture, to keep the curriculum material's real
    scope aligned with the plan being chatted about."""
    real_subject = await db_session.get(Subject, class_subject.subject_id)
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, real_subject, academic_term)
    await _with_ai_config(db_session, school)

    # Real curriculum material + extraction, so search_curriculum has something to find.
    from app.services import curriculum_extraction
    from app.services.curriculum_materials import upload_material
    from fastapi import UploadFile
    import io
    me = await client.get("/auth/me", headers=teacher_auth)
    teacher_user_id = me.json()["id"]
    pdf_bytes = HTML(string="<html><body><p>Fractions represent parts of a whole number.</p></body></html>").write_pdf()
    upload = UploadFile(filename="textbook.pdf", file=io.BytesIO(pdf_bytes), headers={"content-type": "application/pdf"})
    material = await upload_material(class_subject.id, "TEXTBOOK", upload, school.id, teacher_user_id, db_session)
    await curriculum_extraction._run(db_session, material.id)

    lp = await _create_plan(client, teacher_auth, academic_term, school_class, real_subject)

    _patch_driver(monkeypatch, "Focus on fractions as parts of a whole, per the textbook (p.1).")
    resp = await client.post(f"/lesson-plans/{lp['id']}/chat", headers=teacher_auth, json={"message": "How should I teach this topic?"})
    assert resp.status_code == 200, resp.text
    messages = resp.json()
    assert len(messages) == 2
    assert messages[0]["role"] == "USER"
    assert messages[1]["role"] == "ASSISTANT"
    assert "fractions" in messages[1]["content"].lower()


@pytest.mark.asyncio
async def test_list_chat_messages_returns_full_history(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    await _with_ai_config(db_session, school)
    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)

    _patch_driver(monkeypatch, "Sure, here's an idea.")
    await client.post(f"/lesson-plans/{lp['id']}/chat", headers=teacher_auth, json={"message": "Hello"})

    listed = await client.get(f"/lesson-plans/{lp['id']}/chat", headers=teacher_auth)
    assert listed.status_code == 200
    assert len(listed.json()) == 2


@pytest.mark.asyncio
async def test_finalize_requires_conversation_first(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)

    resp = await client.post(f"/lesson-plans/{lp['id']}/chat/finalize", headers=teacher_auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_finalize_produces_lessons_matching_occurrences(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    await _with_ai_config(db_session, school)
    await _add_period_and_slot(db_session, school, school_class, subject, academic_term, date(2024, 9, 9), number=1)

    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)
    _patch_driver(monkeypatch, "Let's do a hands-on activity with fraction tiles.")
    await client.post(f"/lesson-plans/{lp['id']}/chat", headers=teacher_auth, json={"message": "Any activity ideas?"})

    _patch_driver(monkeypatch, json.dumps({
        "lessons": [{"introduction": "Intro", "main_lesson": "Main", "closure": "Closure"}],
        "assessment": {
            "formative": {"mode": "Oral", "task": "Quiz", "mark_scheme": "1pt each"},
            "transcript_assessment": {"mode": "Written", "task": "Worksheet", "rubric": "3-2-1"},
        },
    }))
    resp = await client.post(f"/lesson-plans/{lp['id']}/chat/finalize", headers=teacher_auth)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["generated_content"]["lessons"]) == 1
    assert data["generated_content"]["assessment"]["formative"]["task"] == "Quiz"


# ── curriculum-reference auto-proposal (no manual typing required) ─────────

@pytest.mark.asyncio
async def test_first_chat_message_proposes_curriculum_reference(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    """A teacher never has to type content_standard/indicator/learning_objectives
    — chatting for the first time proposes them, exactly like the
    button-driven skeleton path does."""
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    await _with_ai_config(db_session, school)
    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)
    assert lp["content_standard"] is None

    reference = json.dumps({
        "content_standard": "Number — Fractions", "indicator": "B7.1.1.1",
        "learning_objectives": "Learners will add simple fractions.",
    })
    _patch_driver(monkeypatch, reference)
    resp = await client.post(f"/lesson-plans/{lp['id']}/chat", headers=teacher_auth, json={"message": "Hello"})
    assert resp.status_code == 200, resp.text

    updated = await client.get(f"/lesson-plans/{lp['id']}", headers=teacher_auth)
    assert updated.json()["content_standard"] == "Number — Fractions"
    assert updated.json()["indicator"] == "B7.1.1.1"
    assert updated.json()["learning_objectives"] == "Learners will add simple fractions."


@pytest.mark.asyncio
async def test_second_chat_message_does_not_retrigger_reference_proposal(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    await _with_ai_config(db_session, school)
    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)

    call_log: list[str] = []
    reference = json.dumps({
        "content_standard": "Number — Fractions", "indicator": "B7.1.1.1", "learning_objectives": "Learners will add fractions.",
    })
    _patch_counting_driver(monkeypatch, reference, call_log)
    await client.post(f"/lesson-plans/{lp['id']}/chat", headers=teacher_auth, json={"message": "Hello"})
    assert len(call_log) == 2  # reference proposal + the chat reply itself

    await client.post(f"/lesson-plans/{lp['id']}/chat", headers=teacher_auth, json={"message": "Tell me more"})
    assert len(call_log) == 3  # only the second message's chat reply — no re-proposal
