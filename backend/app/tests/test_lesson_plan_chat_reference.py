"""
Curriculum-reference auto-proposal on the first chat turn — split out of
test_lesson_plan_chat.py to stay under the 300-line cap.

Run inside Docker: docker compose exec api pytest app/tests/test_lesson_plan_chat_reference.py -v
"""
import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class, Subject
from app.models.school import AiConfig, AiProvider, School
from app.services import ai_config as ai_config_module
from app.tests.test_lesson_plan_chat import _create_plan, _patch_driver, _with_ai_config
from app.tests.test_lesson_plans import _login_as_position, _make_subject_teacher, subject  # noqa: F401


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
async def test_first_message_429s_before_second_call_when_only_one_generation_left(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    """Regression: the first chat turn makes TWO real AI generations (the
    curriculum-reference proposal, then the actual reply) but
    get_ready_driver() only checked the quota once, before either ran — a
    caller with exactly 1 generation left could silently run one call over
    budget. Now the reference proposal's own increment must be re-checked
    before the second call, surfacing a clean 429 instead."""
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    db_session.add(AiConfig(
        school_id=school.id, provider=AiProvider.GEMINI, api_key="fake-key",
        daily_limit_per_teacher=1, is_active=True,
    ))
    await db_session.flush()
    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)

    reference = json.dumps({
        "content_standard": "Number — Fractions", "indicator": "B7.1.1.1",
        "learning_objectives": "Learners will add simple fractions.",
    })
    call_log: list[str] = []
    _patch_counting_driver(monkeypatch, reference, call_log)

    resp = await client.post(f"/lesson-plans/{lp['id']}/chat", headers=teacher_auth, json={"message": "Hello"})
    assert resp.status_code == 429, resp.text
    assert len(call_log) == 1  # only the reference proposal ran — the reply call never happened

    listed = await client.get(f"/lesson-plans/{lp['id']}/chat", headers=teacher_auth)
    assert listed.json() == []  # the user's message was never persisted either


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
