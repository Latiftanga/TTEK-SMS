"""
Promotion programme/stream/direction validation — services/class_progression.py.
Split out of test_student_lifecycle.py, matching this project's precedent of
keeping lock/override tests in their own file (test_scoring_lock.py,
test_behaviour_lock.py).

Run inside Docker: docker compose exec api pytest app/tests/test_promotion_validation.py -v
"""
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicYear, Class, SHSProgramme
from app.models.documents import GraduationRecord
from app.models.school import School
from app.services.class_progression import (
    class_ordinal, expected_graduation_type, level_rank, programme_mismatch, stream_mismatch,
)


async def _make_programme(db_session: AsyncSession, school: School, code: str, name: str) -> SHSProgramme:
    prog = SHSProgramme(school_id=school.id, code=code, name=name, is_active=True)
    db_session.add(prog)
    await db_session.flush()
    return prog


async def _make_class(
    db_session: AsyncSession, school: School, level: str, year_group: int,
    stream: str | None = "A", programme_id=None,
) -> Class:
    cls = Class(
        school_id=school.id, level=level, year_group=year_group,
        stream=stream, programme_id=programme_id, is_active=True,
    )
    db_session.add(cls)
    await db_session.flush()
    return cls


async def _create_student(client: AsyncClient, auth: dict, num: str) -> str:
    resp = await client.post("/students", json={
        "admission_number": num, "first_name": "Test", "last_name": "Student",
    }, headers=auth)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _assign_class(client: AsyncClient, auth: dict, student_id: str, cls: Class, year: AcademicYear):
    resp = await client.post("/students/class-assignments", json={
        "student_id": student_id, "class_id": str(cls.id), "academic_year_id": str(year.id),
    }, headers=auth)
    assert resp.status_code == 201, resp.text


@pytest.fixture
async def next_year(db_session: AsyncSession, school: School) -> AcademicYear:
    year = AcademicYear(
        school_id=school.id, name="2099/2100",
        start_date=date(2099, 9, 1), end_date=date(2100, 7, 31), is_current=False,
    )
    db_session.add(year)
    await db_session.flush()
    return year


def _promote_payload(next_year: AcademicYear, student_id: str, target: Class, gtype: str, reason: str | None = None):
    payload = {
        "academic_year_id": str(next_year.id),
        "records": [{"student_id": student_id, "graduation_type": gtype, "class_id": str(target.id)}],
    }
    if reason is not None:
        payload["override_reason"] = reason
    return payload


# ── Pure unit tests: class_progression.py helpers ─────────────────────────────

def test_level_rank_orders_the_ladder():
    assert level_rank("Creche") < level_rank("Nursery") < level_rank("KG") < level_rank("Basic") < level_rank("SHS")


def test_level_rank_unknown_returns_negative_one():
    assert level_rank("Nonsense") == -1


class _Fake:
    def __init__(self, level, year_group, programme_id=None, stream=None):
        self.level, self.year_group, self.programme_id, self.stream = level, year_group, programme_id, stream


def test_class_ordinal_kg_to_basic_is_forward():
    """KG 2 -> Basic 1 is a real promotion with a *decreasing* year_group —
    the ladder must compare level first, not raw year_group."""
    kg2 = _Fake("KG", 2)
    basic1 = _Fake("Basic", 1)
    assert class_ordinal(basic1) > class_ordinal(kg2)


def test_expected_graduation_type_kg_to_basic_is_promoted():
    from app.models.documents import GraduationType
    assert expected_graduation_type(_Fake("KG", 2), _Fake("Basic", 1)) == GraduationType.PROMOTED


def test_programme_mismatch_both_none_is_not_a_mismatch():
    assert programme_mismatch(_Fake("Basic", 5), _Fake("Basic", 6)) is False


def test_stream_mismatch_normalizes_empty_string_to_none():
    assert stream_mismatch(_Fake("SHS", 2, stream=""), _Fake("SHS", 3, stream=None)) is False


# ── Integration: real HTTP layer ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_matching_programme_and_stream_needs_no_reason(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, next_year: AcademicYear,
):
    business = await _make_programme(db_session, school, "BUS", "Business")
    source = await _make_class(db_session, school, "SHS", 2, "A", business.id)
    target = await _make_class(db_session, school, "SHS", 3, "A", business.id)
    sid = await _create_student(client, auth, "MATCH01")
    await _assign_class(client, auth, sid, source, academic_year)

    resp = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, sid, target, "PROMOTED"), headers=auth,
    )
    assert resp.status_code == 201, resp.text
    rec = resp.json()["records"][0]
    assert rec["override_reason"] is None
    assert rec["source_class_id"] == source.id.__str__()


@pytest.mark.asyncio
async def test_programme_mismatch_blocked_without_reason(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, next_year: AcademicYear,
):
    business = await _make_programme(db_session, school, "BUS2", "Business")
    science = await _make_programme(db_session, school, "SCI2", "General Science")
    source = await _make_class(db_session, school, "SHS", 2, "A", business.id)
    target = await _make_class(db_session, school, "SHS", 3, "A", science.id)
    sid = await _create_student(client, auth, "PROGMIS01")
    await _assign_class(client, auth, sid, source, academic_year)

    resp = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, sid, target, "PROMOTED"), headers=auth,
    )
    assert resp.status_code == 423, resp.text
    assert "Business" in resp.json()["detail"] and "General Science" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_programme_mismatch_allowed_with_reason(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, next_year: AcademicYear,
):
    business = await _make_programme(db_session, school, "BUS3", "Business")
    science = await _make_programme(db_session, school, "SCI3", "General Science")
    source = await _make_class(db_session, school, "SHS", 2, "A", business.id)
    target = await _make_class(db_session, school, "SHS", 3, "A", science.id)
    sid = await _create_student(client, auth, "PROGOK01")
    await _assign_class(client, auth, sid, source, academic_year)

    resp = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, sid, target, "PROMOTED", "Parent requested switch to Science"),
        headers=auth,
    )
    assert resp.status_code == 201, resp.text
    rec = resp.json()["records"][0]
    assert rec["override_reason"] == "Parent requested switch to Science"
    assert rec["source_class_id"] == source.id.__str__()


@pytest.mark.asyncio
async def test_stream_mismatch_blocked_without_reason(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, next_year: AcademicYear,
):
    source = await _make_class(db_session, school, "SHS", 2, "A")
    target = await _make_class(db_session, school, "SHS", 3, "B")
    sid = await _create_student(client, auth, "STRMIS01")
    await _assign_class(client, auth, sid, source, academic_year)

    resp = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, sid, target, "PROMOTED"), headers=auth,
    )
    assert resp.status_code == 423, resp.text
    assert "stream A" in resp.json()["detail"] and "stream B" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_stream_mismatch_allowed_with_reason(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, next_year: AcademicYear,
):
    source = await _make_class(db_session, school, "SHS", 2, "A")
    target = await _make_class(db_session, school, "SHS", 3, "B")
    sid = await _create_student(client, auth, "STROK01")
    await _assign_class(client, auth, sid, source, academic_year)

    resp = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, sid, target, "PROMOTED", "Rebalancing sections"),
        headers=auth,
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_basic_school_both_null_programme_is_a_match(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, next_year: AcademicYear,
):
    source = await _make_class(db_session, school, "Basic", 5, "A")
    target = await _make_class(db_session, school, "Basic", 6, "A")
    sid = await _create_student(client, auth, "BASIC01")
    await _assign_class(client, auth, sid, source, academic_year)

    resp = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, sid, target, "PROMOTED"), headers=auth,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["records"][0]["override_reason"] is None


@pytest.mark.asyncio
async def test_kg_to_basic_promotion_succeeds_despite_lower_year_group(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, next_year: AcademicYear,
):
    """KG 2 -> Basic 1 is a real, common promotion — year_group drops from 2
    to 1, but the level ladder must recognise this as forward progress."""
    source = await _make_class(db_session, school, "KG", 2, "A")
    target = await _make_class(db_session, school, "Basic", 1, "A")
    sid = await _create_student(client, auth, "KGBASIC01")
    await _assign_class(client, auth, sid, source, academic_year)

    resp = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, sid, target, "PROMOTED"), headers=auth,
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_promoted_into_lower_ordinal_rejected(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, next_year: AcademicYear,
):
    source = await _make_class(db_session, school, "SHS", 3, "A")
    target = await _make_class(db_session, school, "SHS", 2, "A")
    sid = await _create_student(client, auth, "WRONGDIR01")
    await _assign_class(client, auth, sid, source, academic_year)

    resp = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, sid, target, "PROMOTED"), headers=auth,
    )
    assert resp.status_code == 422, resp.text
    assert "DEMOTED" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_demoted_into_higher_ordinal_rejected(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, next_year: AcademicYear,
):
    """Corrected version of the old (buggy) test_bulk_promote_demoted_type_accepted
    — a DEMOTED record targeting a *higher* class ordinal must now be rejected,
    not silently accepted."""
    source = await _make_class(db_session, school, "SHS", 2, "A")
    target = await _make_class(db_session, school, "SHS", 3, "A")
    sid = await _create_student(client, auth, "DEMOWRONG01")
    await _assign_class(client, auth, sid, source, academic_year)

    resp = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, sid, target, "DEMOTED"), headers=auth,
    )
    assert resp.status_code == 422, resp.text
    assert "PROMOTED" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_direction_mismatch_not_overridable(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, next_year: AcademicYear,
):
    """A wrong graduation_type is a derived fact, not a judgment call —
    supplying override_reason must not change the outcome."""
    source = await _make_class(db_session, school, "SHS", 2, "A")
    target = await _make_class(db_session, school, "SHS", 3, "A")
    sid = await _create_student(client, auth, "DIRREASON01")
    await _assign_class(client, auth, sid, source, academic_year)

    resp = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, sid, target, "DEMOTED", "I really mean it"),
        headers=auth,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_repeated_into_same_class_succeeds(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, next_year: AcademicYear,
):
    source = await _make_class(db_session, school, "SHS", 2, "A")
    sid = await _create_student(client, auth, "REPEATOK01")
    await _assign_class(client, auth, sid, source, academic_year)

    resp = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, sid, source, "REPEATED"), headers=auth,
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_repeated_into_different_ordinal_rejected(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, next_year: AcademicYear,
):
    source = await _make_class(db_session, school, "SHS", 2, "A")
    target = await _make_class(db_session, school, "SHS", 3, "A")
    sid = await _create_student(client, auth, "REPEATBAD01")
    await _assign_class(client, auth, sid, source, academic_year)

    resp = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, sid, target, "REPEATED"), headers=auth,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_no_active_class_assignment_rejected(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    next_year: AcademicYear,
):
    target = await _make_class(db_session, school, "SHS", 2, "A")
    sid = await _create_student(client, auth, "NOSOURCE01")

    resp = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, sid, target, "PROMOTED"), headers=auth,
    )
    assert resp.status_code == 422, resp.text
    assert "no active class assignment" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_mixed_batch_writes_nothing_on_mismatch(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, next_year: AcademicYear,
):
    """One bad record in a batch blocks the whole batch — no partial writes."""
    source = await _make_class(db_session, school, "SHS", 2, "A")
    matching_target = await _make_class(db_session, school, "SHS", 3, "A")
    mismatched_target = await _make_class(db_session, school, "SHS", 3, "B")
    ok_sid = await _create_student(client, auth, "MIXOK01")
    bad_sid = await _create_student(client, auth, "MIXBAD01")
    await _assign_class(client, auth, ok_sid, source, academic_year)
    await _assign_class(client, auth, bad_sid, source, academic_year)

    resp = await client.post("/students/promotions/bulk", json={
        "academic_year_id": str(next_year.id),
        "records": [
            {"student_id": ok_sid, "graduation_type": "PROMOTED", "class_id": str(matching_target.id)},
            {"student_id": bad_sid, "graduation_type": "PROMOTED", "class_id": str(mismatched_target.id)},
        ],
    }, headers=auth)
    assert resp.status_code == 423, resp.text

    for sid in (ok_sid, bad_sid):
        rec = await db_session.scalar(
            select(GraduationRecord).where(
                GraduationRecord.student_id == sid, GraduationRecord.academic_year_id == next_year.id,
            )
        )
        assert rec is None


@pytest.mark.asyncio
async def test_already_processed_records_exempt_from_stricter_reprocessing(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, next_year: AcademicYear,
):
    """Idempotency survives the stricter rules — re-posting an already
    -processed student must stay a no-op even if the resubmitted target
    class would now mismatch."""
    source = await _make_class(db_session, school, "SHS", 2, "A")
    matching_target = await _make_class(db_session, school, "SHS", 3, "A")
    mismatched_target = await _make_class(db_session, school, "SHS", 3, "B")
    sid = await _create_student(client, auth, "IDEMPOTENT01")
    await _assign_class(client, auth, sid, source, academic_year)

    first = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, sid, matching_target, "PROMOTED"), headers=auth,
    )
    assert first.status_code == 201 and first.json()["processed"] == 1

    second = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, sid, mismatched_target, "PROMOTED"), headers=auth,
    )
    assert second.status_code == 201, second.text
    assert second.json()["processed"] == 0
    assert second.json()["skipped"] == 1


@pytest.mark.asyncio
async def test_whitespace_only_reason_treated_as_absent(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, next_year: AcademicYear,
):
    source = await _make_class(db_session, school, "SHS", 2, "A")
    target = await _make_class(db_session, school, "SHS", 3, "B")
    sid = await _create_student(client, auth, "WHITESPACE01")
    await _assign_class(client, auth, sid, source, academic_year)

    resp = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, sid, target, "PROMOTED", "   "), headers=auth,
    )
    assert resp.status_code == 423, resp.text


@pytest.mark.asyncio
async def test_cross_school_target_class_404s(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, next_year: AcademicYear,
):
    from app.models.school import GhanaDistrict, GhanaRegion, SchoolType

    region = await db_session.scalar(select(GhanaRegion))
    district = await db_session.scalar(select(GhanaDistrict))
    other_school = School(
        name="Other School Ltd", school_code="OTHR9", school_type=SchoolType.SHS,
        region_id=region.id, district_id=district.id, is_active=True,
    )
    db_session.add(other_school)
    await db_session.flush()
    source = await _make_class(db_session, school, "SHS", 2, "A")
    other_target = await _make_class(db_session, other_school, "SHS", 3, "A")
    sid = await _create_student(client, auth, "CROSSSCHOOL01")
    await _assign_class(client, auth, sid, source, academic_year)

    resp = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, sid, other_target, "PROMOTED"), headers=auth,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_retired_target_class_404s(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, next_year: AcademicYear,
):
    """A target class that's been retired (Class.is_active=False) must be
    excluded the same way a nonexistent one is — promoting a student into a
    class no longer offered makes no sense."""
    source = await _make_class(db_session, school, "SHS", 2, "A")
    target = await _make_class(db_session, school, "SHS", 3, "A")
    target.is_active = False
    await db_session.flush()
    sid = await _create_student(client, auth, "RETIRED01")
    await _assign_class(client, auth, sid, source, academic_year)

    resp = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, sid, target, "PROMOTED"), headers=auth,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_cross_school_source_student_404s_without_leaking_class_info(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
    academic_year: AcademicYear, next_year: AcademicYear,
):
    """A student_id belonging to a *different* school must never have its
    current class (level/programme/stream) resolved as the promotion
    "source" — that data would otherwise leak into the 422/423 validation
    message even though the eventual write is separately blocked. Mirrors
    test_cross_school_target_class_404s but for the source side of the
    lookup, which previously had no school_id scoping at all."""
    from app.models.school import GhanaDistrict, GhanaRegion, SchoolType
    from app.models.students import Student, StudentClassAssignment

    region = await db_session.scalar(select(GhanaRegion))
    district = await db_session.scalar(select(GhanaDistrict))
    other_school = School(
        name="Other School Ltd", school_code="OTHR8", school_type=SchoolType.SHS,
        region_id=region.id, district_id=district.id, is_active=True,
    )
    db_session.add(other_school)
    await db_session.flush()

    other_class = await _make_class(db_session, other_school, "SHS", 2, "A")
    other_year = AcademicYear(
        school_id=other_school.id, name="2098/2099",
        start_date=date(2098, 9, 1), end_date=date(2099, 7, 31), is_current=False,
    )
    db_session.add(other_year)
    await db_session.flush()
    other_student = Student(
        school_id=other_school.id, admission_number="OTHRSTU01",
        first_name="Foreign", last_name="Student", is_active=True,
    )
    db_session.add(other_student)
    await db_session.flush()
    db_session.add(StudentClassAssignment(
        school_id=other_school.id, student_id=other_student.id, class_id=other_class.id,
        academic_year_id=other_year.id, is_active=True,
    ))
    await db_session.flush()

    target = await _make_class(db_session, school, "SHS", 3, "A")

    resp = await client.post(
        "/students/promotions/bulk",
        json=_promote_payload(next_year, str(other_student.id), target, "PROMOTED"), headers=auth,
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Student not found."
