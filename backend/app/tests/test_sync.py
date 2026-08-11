"""
Offline sync tests — outbox ingestion and conflict detection.
Run inside Docker: docker compose exec api pytest app/tests/test_sync.py -v
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.models.academic import AcademicTerm, Class
from app.models.assessments import Assessment, AssessmentType, Score
from app.models.school import GhanaDistrict, GhanaRegion, School, SchoolType
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
        description="Sync Test",
        recorded_date=date.today(),
        max_score=Decimal("100.00"),
    )
    db_session.add(a)
    await db_session.flush()
    return a


def _outbox_payload(
    assessment: Assessment, student: Student, raw_score: str, outbox_id: str, offline_ts: str,
    client_op_id: str | None = None,
) -> dict:
    return {
        "items": [{
            "outbox_id": outbox_id,
            "client_op_id": client_op_id or f"op-{outbox_id}",
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


# ── Idempotency ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_outbox_duplicate_client_op_id_is_noop(
    client: AsyncClient, auth: dict, assessment: Assessment, student: Student,
    db_session: AsyncSession, school: School,
):
    """Resubmitting the same client_op_id (a retried request, or two drain
    triggers racing) must not re-run the apply logic or write a second
    ScoreAuditLog entry — it should return the recorded outcome as-is."""
    from sqlalchemy import select
    from app.models.assessments import ScoreAuditLog

    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    payload = _outbox_payload(assessment, student, "78.00", "ob-idem-1", offline_ts, client_op_id="op-idem-1")

    first = await client.post("/sync/outbox", json=payload, headers=auth)
    assert first.status_code == 200
    assert first.json()[0]["status"] == "applied"

    second = await client.post("/sync/outbox", json=payload, headers=auth)
    assert second.status_code == 200
    assert second.json()[0]["status"] == "applied"

    score = await db_session.scalar(
        select(Score).where(Score.assessment_id == assessment.id, Score.student_id == student.id)
    )
    logs = (await db_session.scalars(
        select(ScoreAuditLog).where(ScoreAuditLog.score_id == score.id)
    )).all()
    assert len(logs) == 1, "duplicate submission must not double-write the audit log"


@pytest.mark.asyncio
async def test_outbox_duplicate_client_op_id_returns_same_conflict(
    client: AsyncClient, auth: dict,
    assessment: Assessment, student: Student,
    db_session: AsyncSession, school: School, school_admin,
):
    """A retried submission of a client_op_id that resulted in a conflict must
    return that same conflict_id, not create a second OfflineSyncConflict row."""
    from sqlalchemy import select
    from app.models.documents import OfflineSyncConflict

    score = Score(
        school_id=school.id, assessment_id=assessment.id, student_id=student.id,
        raw_score=Decimal("55.00"), entered_by_id=school_admin.id,
        submitted_at=datetime.now(timezone.utc) - timedelta(minutes=30),
    )
    db_session.add(score)
    await db_session.flush()

    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    payload = _outbox_payload(assessment, student, "90.00", "ob-idem-2", offline_ts, client_op_id="op-idem-2")

    first = await client.post("/sync/outbox", json=payload, headers=auth)
    conflict_id = first.json()[0]["conflict_id"]
    assert conflict_id is not None

    second = await client.post("/sync/outbox", json=payload, headers=auth)
    assert second.json()[0]["status"] == "conflict"
    assert second.json()[0]["conflict_id"] == conflict_id

    conflicts = (await db_session.scalars(
        select(OfflineSyncConflict).where(OfflineSyncConflict.outbox_id == "ob-idem-2")
    )).all()
    assert len(conflicts) == 1, "duplicate submission must not create a second conflict row"


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


# ── Cross-school FK rejection ────────────────────────────────────────────────
# assessment_id/student_id come straight from the offline outbox payload with
# no ownership check before this fix — a lookup that found no existing Score
# at this school (because the ids belonged to a different school) fell
# through to CREATING a new Score row stamped with the caller's own
# school_id but pointing at another school's real Assessment/Student.

async def _other_school(db_session: AsyncSession) -> School:
    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    other = School(
        name="Other Sync School", school_code="OTHER_SYNC", school_type=SchoolType.SHS,
        region_id=region.id, district_id=district.id, is_active=True,
    )
    db_session.add(other)
    await db_session.flush()
    return other


@pytest.mark.asyncio
async def test_outbox_rejects_cross_school_assessment_id(
    client: AsyncClient, auth: dict, student: Student, db_session: AsyncSession,
):
    other = await _other_school(db_session)
    from app.models.academic import AcademicTerm as _AT, AcademicYear, Class as _Cls
    from app.models.academic import SubjectCatalogue, SubjectType, Subject, SchoolLevel

    year = AcademicYear(school_id=other.id, name="2024/2025", start_date=date(2024, 9, 1), end_date=date(2025, 7, 31), is_current=True)
    db_session.add(year)
    await db_session.flush()
    term = _AT(school_id=other.id, academic_year_id=year.id, term_number=1, name="Term 1",
               start_date=date(2024, 9, 1), end_date=date(2024, 12, 15), is_current=True)
    cls = _Cls(school_id=other.id, level="SHS", year_group=1, stream="A", is_active=True)
    cat = SubjectCatalogue(name="Foreign Subj", code="FOR_SYNC", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add_all([term, cls, cat])
    await db_session.flush()
    subj = Subject(school_id=other.id, catalogue_id=cat.id, code="FORSUB", name="Foreign Subj", is_active=True)
    atype = AssessmentType(school_id=other.id, name="Foreign Test", code="FT_SYNC", weight=Decimal("30.00"))
    db_session.add_all([subj, atype])
    await db_session.flush()
    foreign_assessment = Assessment(
        school_id=other.id, class_id=cls.id, subject_id=subj.id, assessment_type_id=atype.id,
        academic_term_id=term.id, description="Foreign", recorded_date=date.today(),
        max_score=Decimal("100.00"),
    )
    db_session.add(foreign_assessment)
    await db_session.flush()

    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = await client.post("/sync/outbox",
        json=_outbox_payload(foreign_assessment, student, "78.00", "ob-xschool-1", offline_ts),
        headers=auth,
    )
    assert resp.status_code == 422

    leaked = await db_session.scalar(
        select(Score).where(Score.assessment_id == foreign_assessment.id, Score.student_id == student.id)
    )
    assert leaked is None


@pytest.mark.asyncio
async def test_outbox_rejects_cross_school_student_id(
    client: AsyncClient, auth: dict, assessment: Assessment, db_session: AsyncSession,
):
    other = await _other_school(db_session)
    foreign_student = Student(
        school_id=other.id, admission_number="FOR-001",
        first_name="Foreign", last_name="Student", is_active=True,
    )
    db_session.add(foreign_student)
    await db_session.flush()

    offline_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = await client.post("/sync/outbox",
        json=_outbox_payload(assessment, foreign_student, "78.00", "ob-xschool-2", offline_ts),
        headers=auth,
    )
    assert resp.status_code == 422

    leaked = await db_session.scalar(
        select(Score).where(Score.assessment_id == assessment.id, Score.student_id == foreign_student.id)
    )
    assert leaked is None


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
