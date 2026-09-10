"""
Lesson generation for a class+subject with no real timetable configured —
resolve_week_occurrences returns [] in this case (no TimetableSlot/
SchoolPeriod rows set up by the base fixtures here, deliberately, unlike
test_lesson_plan_generation.py's own fixtures which call _add_period_and_slot).
A teacher-supplied lesson_count is the fallback; whenever a real timetable
exists elsewhere, it stays authoritative (already covered by the existing
generation tests, unaffected by this file).

Run inside Docker: docker compose exec api pytest app/tests/test_lesson_plan_no_timetable.py -v
"""
import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class, Subject
from app.models.school import School
from app.tests.test_lesson_plan_generation import _create_plan, _lessons_json, _patch_driver, _skeleton_json, _with_ai_config
from app.tests.test_lesson_plans import _login_as_position, _make_subject_teacher, subject  # noqa: F401


@pytest.mark.asyncio
async def test_finalize_chat_succeeds_with_count_when_no_timetable(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    await _with_ai_config(db_session, school)
    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)

    _patch_driver(monkeypatch, "Let's discuss the topic generically since there's no timetable yet.")
    await client.post(f"/lesson-plans/{lp['id']}/chat", headers=teacher_auth, json={"message": "Any ideas?"})

    no_timetable = await client.post(f"/lesson-plans/{lp['id']}/chat/finalize", headers=teacher_auth)
    assert no_timetable.status_code == 422
    assert "how many lessons" in no_timetable.text

    _patch_driver(monkeypatch, _lessons_json(2))
    resp = await client.post(f"/lesson-plans/{lp['id']}/chat/finalize", headers=teacher_auth, json={"lesson_count": 2})
    assert resp.status_code == 200, resp.text
    lessons = resp.json()["generated_content"]["lessons"]
    assert len(lessons) == 2
    assert lessons[0]["sequence_index"] == 1


@pytest.mark.asyncio
async def test_generate_lessons_422_without_count_when_no_timetable(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    await _with_ai_config(db_session, school)
    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)
    _patch_driver(monkeypatch, _skeleton_json())
    await client.post(f"/lesson-plans/{lp['id']}/generate-skeleton", headers=teacher_auth)

    resp = await client.post(f"/lesson-plans/{lp['id']}/generate-lessons", headers=teacher_auth)
    assert resp.status_code == 422
    assert "how many lessons" in resp.text


@pytest.mark.asyncio
async def test_generate_lessons_succeeds_with_count_when_no_timetable(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    await _with_ai_config(db_session, school)
    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)
    _patch_driver(monkeypatch, _skeleton_json())
    await client.post(f"/lesson-plans/{lp['id']}/generate-skeleton", headers=teacher_auth)

    _patch_driver(monkeypatch, _lessons_json(2))
    resp = await client.post(f"/lesson-plans/{lp['id']}/generate-lessons", headers=teacher_auth, json={"lesson_count": 2})
    assert resp.status_code == 200, resp.text
    lessons = resp.json()["generated_content"]["lessons"]
    assert len(lessons) == 2
    assert lessons[0]["school_calendar_id"] is None
    assert lessons[0]["period_id"] is None
    assert lessons[0]["sequence_index"] == 1
    assert lessons[1]["sequence_index"] == 2


@pytest.mark.asyncio
async def test_regenerate_lesson_by_sequence_index_when_no_timetable(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    await _with_ai_config(db_session, school)
    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)
    _patch_driver(monkeypatch, _skeleton_json())
    await client.post(f"/lesson-plans/{lp['id']}/generate-skeleton", headers=teacher_auth)
    _patch_driver(monkeypatch, _lessons_json(2))
    await client.post(f"/lesson-plans/{lp['id']}/generate-lessons", headers=teacher_auth, json={"lesson_count": 2})

    _patch_driver(monkeypatch, json.dumps({"introduction": "New intro", "main_lesson": "New main", "closure": "New closure"}))
    resp = await client.post(
        f"/lesson-plans/{lp['id']}/regenerate-lesson", headers=teacher_auth, json={"sequence_index": 1},
    )
    assert resp.status_code == 200, resp.text
    lessons = resp.json()["generated_content"]["lessons"]
    changed = next(l for l in lessons if l["sequence_index"] == 1)
    untouched = next(l for l in lessons if l["sequence_index"] == 2)
    assert changed["introduction"] == "New intro"
    assert untouched["introduction"] != "New intro"


@pytest.mark.asyncio
async def test_review_approve_skips_drift_check_when_no_timetable(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    school_class: Class, subject: Subject, academic_term: AcademicTerm, redis_permissions: None, monkeypatch,
):
    """The occurrence-drift check has nothing real to diff against for an
    untimetabled plan — approval must succeed even though
    resolve_week_occurrences() would return [] both at generation and review
    time (the exact condition that would 409 a real-occurrence plan)."""
    teacher_auth, staff_id = await _login_as_position(client, auth, db_session, school, "TEACHER")
    await _make_subject_teacher(db_session, school, staff_id, school_class, subject, academic_term)
    await _with_ai_config(db_session, school)
    lp = await _create_plan(client, teacher_auth, academic_term, school_class, subject)
    _patch_driver(monkeypatch, _skeleton_json())
    await client.post(f"/lesson-plans/{lp['id']}/generate-skeleton", headers=teacher_auth)
    _patch_driver(monkeypatch, _lessons_json(1))
    await client.post(f"/lesson-plans/{lp['id']}/generate-lessons", headers=teacher_auth, json={"lesson_count": 1})

    head_auth, _ = await _login_as_position(client, auth, db_session, school, "HEAD")
    resp = await client.patch(f"/lesson-plans/{lp['id']}/review", headers=head_auth, json={"status": "APPROVED"})
    assert resp.status_code == 200, resp.text
