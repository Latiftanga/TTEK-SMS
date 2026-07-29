"""
Offline sync tests — conflict resolution (CLIENT_WINS, SERVER_WINS, DISCARDED).
Run inside Docker: docker compose exec api pytest app/tests/test_sync_resolve.py -v
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicTerm, Class
from app.models.assessments import Assessment, AssessmentType, Score
from app.models.school import School
from app.models.students import Student


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def assessment_type(db_session: AsyncSession, school: School) -> AssessmentType:
    t = AssessmentType(
        school_id=school.id, name="Test", code="CT_RES", weight=Decimal("30.00")
    )
    db_session.add(t)
    await db_session.flush()
    return t


@pytest.fixture
async def subject(db_session: AsyncSession, school: School):
    from app.models.academic import SubjectCatalogue, SubjectType, Subject, SchoolLevel
    cat = SubjectCatalogue(name="Science", code="SCI_RES", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code="SCI", name="Science", is_active=True)
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
        name="Resolve Test",
        max_score=Decimal("100.00"),
    )
    db_session.add(a)
    await db_session.flush()
    return a


async def _create_conflict(
    client, auth, assessment, student, school, school_admin, db_session, raw_score_server, raw_score_client, outbox_id
) -> str:
    """Helper: create a server score then submit conflicting offline score. Returns conflict_id."""
    score = Score(
        school_id=school.id,
        assessment_id=assessment.id,
        student_id=student.id,
        raw_score=raw_score_server,
        entered_by_id=school_admin.id,
        submitted_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    db_session.add(score)
    await db_session.flush()

    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = await client.post("/sync/outbox", json={
        "items": [{
            "outbox_id": outbox_id,
            "client_op_id": f"op-{outbox_id}",
            "entity_type": "score",
            "offline_session_started_at": offline_ts,
            "data": {
                "assessment_id": str(assessment.id),
                "student_id": str(student.id),
                "raw_score": str(raw_score_client),
            },
        }],
    }, headers=auth)
    return resp.json()[0]["conflict_id"]


# ── Resolution tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolve_server_wins(
    client: AsyncClient, auth: dict,
    assessment: Assessment, student: Student,
    db_session: AsyncSession, school: School, school_admin,
):
    conflict_id = await _create_conflict(
        client, auth, assessment, student, school, school_admin, db_session,
        Decimal("70.00"), Decimal("95.00"), "ob-srv-wins",
    )
    resp = await client.post(f"/sync/conflicts/{conflict_id}/resolve",
        json={"resolution": "SERVER_WINS"}, headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["resolution"] == "SERVER_WINS"
    assert resp.json()["resolved_at"] is not None


@pytest.mark.asyncio
async def test_resolve_client_wins_applies_score(
    client: AsyncClient, auth: dict,
    assessment: Assessment, student: Student,
    db_session: AsyncSession, school: School, school_admin,
):
    conflict_id = await _create_conflict(
        client, auth, assessment, student, school, school_admin, db_session,
        Decimal("50.00"), Decimal("92.00"), "ob-cli-wins",
    )
    resp = await client.post(f"/sync/conflicts/{conflict_id}/resolve",
        json={"resolution": "CLIENT_WINS"}, headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["resolution"] == "CLIENT_WINS"

    updated = await db_session.scalar(
        select(Score).where(
            Score.assessment_id == assessment.id,
            Score.student_id == student.id,
        )
    )
    assert updated.raw_score == Decimal("92.00")


@pytest.mark.asyncio
async def test_resolve_discarded(
    client: AsyncClient, auth: dict,
    assessment: Assessment, student: Student,
    db_session: AsyncSession, school: School, school_admin,
):
    conflict_id = await _create_conflict(
        client, auth, assessment, student, school, school_admin, db_session,
        Decimal("30.00"), Decimal("65.00"), "ob-discard",
    )
    resp = await client.post(f"/sync/conflicts/{conflict_id}/resolve",
        json={"resolution": "DISCARDED"}, headers=auth,
    )
    assert resp.status_code == 200
    assert resp.json()["resolution"] == "DISCARDED"


@pytest.mark.asyncio
async def test_resolve_already_resolved_returns_409(
    client: AsyncClient, auth: dict,
    assessment: Assessment, student: Student,
    db_session: AsyncSession, school: School, school_admin,
):
    conflict_id = await _create_conflict(
        client, auth, assessment, student, school, school_admin, db_session,
        Decimal("45.00"), Decimal("80.00"), "ob-double-resolve",
    )
    await client.post(f"/sync/conflicts/{conflict_id}/resolve",
        json={"resolution": "DISCARDED"}, headers=auth,
    )
    resp = await client.post(f"/sync/conflicts/{conflict_id}/resolve",
        json={"resolution": "CLIENT_WINS"}, headers=auth,
    )
    assert resp.status_code == 409
