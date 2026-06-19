"""
Offline sync tests — outbox ingestion and conflict detection.
Run inside Docker: docker compose exec api pytest app/tests/test_sync.py -v
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class
from app.models.assessments import Assessment, AssessmentType, Score
from app.models.school import School
from app.models.students import Student


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
async def assessment_type(db_session: AsyncSession, school: School) -> AssessmentType:
    t = AssessmentType(
        school_id=school.id, name="Class Test", code="CT_SYNC", weight=Decimal("30.00")
    )
    db_session.add(t)
    await db_session.flush()
    return t


@pytest.fixture
async def subject(db_session: AsyncSession, school: School):
    from app.models.academic import SubjectCatalogue, SubjectType, Subject, SchoolLevel
    cat = SubjectCatalogue(name="English", code="ENG_SYNC", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code="ENG", name="English", is_active=True)
    db_session.add(subj)
    await db_session.flush()
    return subj


@pytest.fixture
async def assessment(
    db_session: AsyncSession, school: School, school_class: Class,
    subject, assessment_type: AssessmentType, academic_term: AcademicTerm,
) -> Assessment:
    a = Assessment(
        school_id=school.id,
        class_id=school_class.id,
        subject_id=subject.id,
        assessment_type_id=assessment_type.id,
        academic_term_id=academic_term.id,
        name="Sync Test",
        max_score=Decimal("100.00"),
    )
    db_session.add(a)
    await db_session.flush()
    return a


def _outbox_payload(assessment: Assessment, student: Student, raw_score: str, outbox_id: str, offline_ts: str) -> dict:
    return {
        "items": [{
            "outbox_id": outbox_id,
            "entity_type": "score",
            "offline_session_started_at": offline_ts,
            "data": {
                "assessment_id": str(assessment.id),
                "student_id": str(student.id),
                "raw_score": raw_score,
            },
        }]
    }


# ── Outbox — no conflict ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_outbox_applies_new_score(
    client: AsyncClient, auth: dict, assessment: Assessment, student: Student,
):
    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = await client.post("/sync/outbox",
        json=_outbox_payload(assessment, student, "78.00", "ob-001", offline_ts),
        headers=auth,
    )
    assert resp.status_code == 200
    result = resp.json()[0]
    assert result["status"] == "applied"
    assert result["conflict_id"] is None


@pytest.mark.asyncio
async def test_outbox_applies_when_server_older(
    client: AsyncClient, auth: dict,
    assessment: Assessment, student: Student,
    db_session: AsyncSession, school: School, school_admin,
):
    """Server score was submitted BEFORE the offline session started → safe apply."""
    score = Score(
        school_id=school.id,
        assessment_id=assessment.id,
        student_id=student.id,
        raw_score=Decimal("60.00"),
        entered_by_id=school_admin.id,
        submitted_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    db_session.add(score)
    await db_session.flush()

    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = await client.post("/sync/outbox",
        json=_outbox_payload(assessment, student, "80.00", "ob-002", offline_ts),
        headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "applied"


# ── Outbox — conflict ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_outbox_detects_conflict(
    client: AsyncClient, auth: dict,
    assessment: Assessment, student: Student,
    db_session: AsyncSession, school: School, school_admin,
):
    """Server score submitted AFTER offline session started → conflict written."""
    score = Score(
        school_id=school.id,
        assessment_id=assessment.id,
        student_id=student.id,
        raw_score=Decimal("55.00"),
        entered_by_id=school_admin.id,
        submitted_at=datetime.now(timezone.utc) - timedelta(minutes=30),
    )
    db_session.add(score)
    await db_session.flush()

    # Offline session started 1 hour ago — server update (30 min ago) is newer
    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = await client.post("/sync/outbox",
        json=_outbox_payload(assessment, student, "90.00", "ob-003", offline_ts),
        headers=auth,
    )
    assert resp.status_code == 200
    result = resp.json()[0]
    assert result["status"] == "conflict"
    assert result["conflict_id"] is not None


# ── Conflict list ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_conflicts_empty_initially(client: AsyncClient, auth: dict):
    resp = await client.get("/sync/conflicts", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_conflicts_shows_unresolved(
    client: AsyncClient, auth: dict,
    assessment: Assessment, student: Student,
    db_session: AsyncSession, school: School, school_admin,
):
    score = Score(
        school_id=school.id,
        assessment_id=assessment.id,
        student_id=student.id,
        raw_score=Decimal("40.00"),
        entered_by_id=school_admin.id,
        submitted_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    db_session.add(score)
    await db_session.flush()

    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    await client.post("/sync/outbox",
        json=_outbox_payload(assessment, student, "88.00", "ob-list-001", offline_ts),
        headers=auth,
    )

    resp = await client.get("/sync/conflicts", headers=auth)
    assert resp.status_code == 200
    conflicts = resp.json()
    assert len(conflicts) == 1
    assert conflicts[0]["outbox_id"] == "ob-list-001"
    assert conflicts[0]["resolution"] is None
