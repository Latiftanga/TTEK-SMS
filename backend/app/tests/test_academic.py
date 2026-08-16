"""
Academic setup integration tests.
Run inside Docker: docker compose exec api pytest app/tests/test_academic.py -v

Fixtures (school, school_admin, auth) are defined in conftest.py.
"""
import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.models.auth import LoginType, User
from app.models.academic import (
    AcademicTerm, AcademicYear, SchoolLevel, SHSProgramme, SubjectCatalogue, SubjectType,
)
from app.models.school import GhanaDistrict, GhanaRegion, School, SchoolType


# ── Academic Year ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_academic_year(client: AsyncClient, auth: dict):
    resp = await client.post("/academic/years", json={
        "name": "2024/2025",
        "start_date": "2024-09-02",
        "end_date": "2025-07-31",
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "2024/2025"
    assert data["is_current"] is False
    assert data["terms"] == []


@pytest.mark.asyncio
async def test_list_years_empty_then_populated(client: AsyncClient, auth: dict):
    resp = await client.get("/academic/years", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == []

    await client.post("/academic/years", json={
        "name": "2024/2025", "start_date": "2024-09-02", "end_date": "2025-07-31",
    }, headers=auth)

    resp = await client.get("/academic/years", headers=auth)
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_set_current_year_only_one_current(client: AsyncClient, auth: dict):
    r1 = await client.post("/academic/years", json={
        "name": "2023/2024", "start_date": "2023-09-04", "end_date": "2024-07-31",
    }, headers=auth)
    r2 = await client.post("/academic/years", json={
        "name": "2024/2025", "start_date": "2024-09-02", "end_date": "2025-07-31",
    }, headers=auth)
    year1_id = r1.json()["id"]
    year2_id = r2.json()["id"]

    await client.post(f"/academic/years/{year1_id}/set-current", headers=auth)
    await client.post(f"/academic/years/{year2_id}/set-current", headers=auth)

    years = (await client.get("/academic/years", headers=auth)).json()
    current = [y for y in years if y["is_current"]]
    assert len(current) == 1
    assert current[0]["id"] == year2_id


@pytest.mark.asyncio
async def test_duplicate_year_name_rejected(client: AsyncClient, auth: dict):
    payload = {"name": "2024/2025", "start_date": "2024-09-02", "end_date": "2025-07-31"}
    await client.post("/academic/years", json=payload, headers=auth)
    resp = await client.post("/academic/years", json=payload, headers=auth)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_year_rejects_oversized_name(client: AsyncClient, auth: dict):
    """name is String(20) at the DB layer — an oversized value used to hit
    an unhandled IntegrityError (500) instead of a clean 422."""
    resp = await client.post("/academic/years", json={
        "name": "X" * 21, "start_date": "2024-09-02", "end_date": "2025-07-31",
    }, headers=auth)
    assert resp.status_code == 422


# ── Academic Terms ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_terms_for_year(client: AsyncClient, auth: dict):
    year_id = (await client.post("/academic/years", json={
        "name": "2024/2025", "start_date": "2024-09-02", "end_date": "2025-07-31",
    }, headers=auth)).json()["id"]

    for i, (name, start, end) in enumerate([
        ("First Term",  "2024-09-02", "2024-12-13"),
        ("Second Term", "2025-01-13", "2025-04-11"),
        ("Third Term",  "2025-05-05", "2025-07-25"),
    ], start=1):
        resp = await client.post(f"/academic/years/{year_id}/terms", json={
            "term_number": i, "name": name, "start_date": start, "end_date": end,
        }, headers=auth)
        assert resp.status_code == 201

    terms = (await client.get(f"/academic/years/{year_id}/terms", headers=auth)).json()
    assert len(terms) == 3
    assert [t["term_number"] for t in terms] == [1, 2, 3]


@pytest.mark.asyncio
async def test_set_current_term_only_one_current(client: AsyncClient, auth: dict):
    year_id = (await client.post("/academic/years", json={
        "name": "2024/2025", "start_date": "2024-09-02", "end_date": "2025-07-31",
    }, headers=auth)).json()["id"]

    t1 = (await client.post(f"/academic/years/{year_id}/terms", json={
        "term_number": 1, "name": "First Term",
        "start_date": "2024-09-02", "end_date": "2024-12-13",
    }, headers=auth)).json()["id"]

    t2 = (await client.post(f"/academic/years/{year_id}/terms", json={
        "term_number": 2, "name": "Second Term",
        "start_date": "2025-01-13", "end_date": "2025-04-11",
    }, headers=auth)).json()["id"]

    await client.post(f"/academic/terms/{t1}/set-current", headers=auth)
    await client.post(f"/academic/terms/{t2}/set-current", headers=auth)

    terms = (await client.get(f"/academic/years/{year_id}/terms", headers=auth)).json()
    current = [t for t in terms if t["is_current"]]
    assert len(current) == 1
    assert current[0]["id"] == t2


@pytest.mark.asyncio
async def test_set_current_term_in_noncurrent_year_cascades_year(client: AsyncClient, auth: dict):
    """The exact drift shape this codebase's own CLAUDE.md documented but
    never root-caused: setting a term current in a year that isn't itself
    current must flip the year too, atomically — not silently leave the
    real current year pointing at nothing."""
    year_a = (await client.post("/academic/years", json={
        "name": "2023/2024", "start_date": "2023-09-04", "end_date": "2024-07-31",
    }, headers=auth)).json()["id"]
    a1 = (await client.post(f"/academic/years/{year_a}/terms", json={
        "term_number": 1, "name": "First Term",
        "start_date": "2023-09-04", "end_date": "2023-12-15",
    }, headers=auth)).json()["id"]
    await client.post(f"/academic/years/{year_a}/set-current", headers=auth)
    await client.post(f"/academic/terms/{a1}/set-current", headers=auth)

    year_b = (await client.post("/academic/years", json={
        "name": "2024/2025", "start_date": "2024-09-02", "end_date": "2025-07-31",
    }, headers=auth)).json()["id"]
    b1 = (await client.post(f"/academic/years/{year_b}/terms", json={
        "term_number": 1, "name": "First Term",
        "start_date": "2024-09-02", "end_date": "2024-12-13",
    }, headers=auth)).json()["id"]

    # year_b is not current at this point — set-current on its term b1 must
    # still cascade to make year_b current, and cleanly unset year_a/a1.
    resp = await client.post(f"/academic/terms/{b1}/set-current", headers=auth)
    assert resp.status_code == 200

    years = (await client.get("/academic/years", headers=auth)).json()
    current_years = [y for y in years if y["is_current"]]
    assert len(current_years) == 1
    assert current_years[0]["id"] == year_b

    a_terms = (await client.get(f"/academic/years/{year_a}/terms", headers=auth)).json()
    assert all(not t["is_current"] for t in a_terms)
    b_terms = (await client.get(f"/academic/years/{year_b}/terms", headers=auth)).json()
    current_terms = [t for t in b_terms if t["is_current"]]
    assert len(current_terms) == 1
    assert current_terms[0]["id"] == b1


@pytest.mark.asyncio
async def test_set_current_year_unsets_stray_current_term_without_picking_one(
    client: AsyncClient, auth: dict,
):
    """Symmetric case: setting a year current must unset any current term
    that belongs to a different year, but must NOT auto-pick a new current
    term for the newly-current year — a year can legitimately be current
    with zero current term chosen yet."""
    year_a = (await client.post("/academic/years", json={
        "name": "2023/2024", "start_date": "2023-09-04", "end_date": "2024-07-31",
    }, headers=auth)).json()["id"]
    a1 = (await client.post(f"/academic/years/{year_a}/terms", json={
        "term_number": 1, "name": "First Term",
        "start_date": "2023-09-04", "end_date": "2023-12-15",
    }, headers=auth)).json()["id"]
    await client.post(f"/academic/years/{year_a}/set-current", headers=auth)
    await client.post(f"/academic/terms/{a1}/set-current", headers=auth)

    year_b = (await client.post("/academic/years", json={
        "name": "2024/2025", "start_date": "2024-09-02", "end_date": "2025-07-31",
    }, headers=auth)).json()["id"]

    resp = await client.post(f"/academic/years/{year_b}/set-current", headers=auth)
    assert resp.status_code == 200

    a_terms = (await client.get(f"/academic/years/{year_a}/terms", headers=auth)).json()
    assert all(not t["is_current"] for t in a_terms)   # stray term unset

    current_term = (await client.get("/academic/terms/current", headers=auth)).json()
    assert current_term is None   # not auto-picked for year_b

    years = (await client.get("/academic/years", headers=auth)).json()
    current_years = [y for y in years if y["is_current"]]
    assert len(current_years) == 1
    assert current_years[0]["id"] == year_b


@pytest.mark.asyncio
async def test_duplicate_current_year_rejected_at_db_level(
    db_session: AsyncSession, school: School,
):
    """Proves the partial unique index itself holds, independent of the
    service layer's own unset-first logic — bypasses the service entirely."""
    db_session.add(AcademicYear(
        school_id=school.id, name="Year A",
        start_date=date(2023, 9, 4), end_date=date(2024, 7, 31), is_current=True,
    ))
    await db_session.flush()

    db_session.add(AcademicYear(
        school_id=school.id, name="Year B",
        start_date=date(2024, 9, 2), end_date=date(2025, 7, 31), is_current=True,
    ))
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_duplicate_current_term_rejected_at_db_level(
    db_session: AsyncSession, school: School, academic_year: AcademicYear,
):
    """Same proof for AcademicTerm — two terms in the SAME year, both
    is_current=True, must be rejected by the DB, not just the service."""
    db_session.add(AcademicTerm(
        school_id=school.id, academic_year_id=academic_year.id,
        term_number=1, name="First Term",
        start_date=date(2024, 9, 2), end_date=date(2024, 12, 13), is_current=True,
    ))
    await db_session.flush()

    db_session.add(AcademicTerm(
        school_id=school.id, academic_year_id=academic_year.id,
        term_number=2, name="Second Term",
        start_date=date(2025, 1, 13), end_date=date(2025, 4, 11), is_current=True,
    ))
    with pytest.raises(IntegrityError):
        await db_session.flush()


# ── Date validation ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_year_end_before_start_rejected(client: AsyncClient, auth: dict):
    resp = await client.post("/academic/years", json={
        "name": "Bad Year", "start_date": "2024-09-02", "end_date": "2024-08-01",
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_year_end_before_start_rejected(client: AsyncClient, auth: dict):
    year_id = (await client.post("/academic/years", json={
        "name": "2024/2025", "start_date": "2024-09-02", "end_date": "2025-07-31",
    }, headers=auth)).json()["id"]
    resp = await client.patch(f"/academic/years/{year_id}", json={
        "end_date": "2024-01-01",
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_term_end_before_start_rejected(client: AsyncClient, auth: dict):
    year_id = (await client.post("/academic/years", json={
        "name": "2024/2025", "start_date": "2024-09-02", "end_date": "2025-07-31",
    }, headers=auth)).json()["id"]
    resp = await client.post(f"/academic/years/{year_id}/terms", json={
        "term_number": 1, "name": "First Term",
        "start_date": "2024-12-13", "end_date": "2024-09-02",
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_term_outside_year_bounds_rejected(client: AsyncClient, auth: dict):
    year_id = (await client.post("/academic/years", json={
        "name": "2024/2025", "start_date": "2024-09-02", "end_date": "2025-07-31",
    }, headers=auth)).json()["id"]
    resp = await client.post(f"/academic/years/{year_id}/terms", json={
        "term_number": 1, "name": "First Term",
        "start_date": "2024-08-01", "end_date": "2024-12-13",   # starts before the year
    }, headers=auth)
    assert resp.status_code == 422
    assert "range" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_term_overlapping_sibling_rejected(client: AsyncClient, auth: dict):
    year_id = (await client.post("/academic/years", json={
        "name": "2024/2025", "start_date": "2024-09-02", "end_date": "2025-07-31",
    }, headers=auth)).json()["id"]
    await client.post(f"/academic/years/{year_id}/terms", json={
        "term_number": 1, "name": "First Term",
        "start_date": "2024-09-02", "end_date": "2024-12-13",
    }, headers=auth)
    resp = await client.post(f"/academic/years/{year_id}/terms", json={
        "term_number": 2, "name": "Second Term",
        "start_date": "2024-11-01", "end_date": "2025-01-31",   # overlaps First Term
    }, headers=auth)
    assert resp.status_code == 422
    assert "overlap" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_term_outside_year_bounds_rejected(client: AsyncClient, auth: dict):
    year_id = (await client.post("/academic/years", json={
        "name": "2024/2025", "start_date": "2024-09-02", "end_date": "2025-07-31",
    }, headers=auth)).json()["id"]
    term_id = (await client.post(f"/academic/years/{year_id}/terms", json={
        "term_number": 1, "name": "First Term",
        "start_date": "2024-09-02", "end_date": "2024-12-13",
    }, headers=auth)).json()["id"]
    resp = await client.patch(f"/academic/terms/{term_id}", json={
        "end_date": "2025-08-15",   # past the year's own end_date
    }, headers=auth)
    assert resp.status_code == 422


# ── Classes ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_class_display_name(client: AsyncClient, auth: dict):
    year_id = (await client.post("/academic/years", json={
        "name": "2024/2025", "start_date": "2024-09-02", "end_date": "2025-07-31",
    }, headers=auth)).json()["id"]

    # Create a school-specific programme for this test
    prog_id = (await client.post("/academic/programmes", json={
        "code": "GSCI_TEST", "name": "General Science",
    }, headers=auth)).json()["id"]

    resp = await client.post("/academic/classes", json={
        "level": "SHS",
        "year_group": 2,
        "programme_id": prog_id,
        "stream": "A",
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["display_name"] == "2 General Science A"
    assert data["programme_name"] == "General Science"


@pytest.mark.asyncio
async def test_create_basic_class_no_programme(client: AsyncClient, auth: dict):
    year_id = (await client.post("/academic/years", json={
        "name": "2024/2025", "start_date": "2024-09-02", "end_date": "2025-07-31",
    }, headers=auth)).json()["id"]

    resp = await client.post("/academic/classes", json={
        "level": "JHS",
        "year_group": 2,
        "stream": "B",
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["display_name"] == "JHS 2 B"
    assert data["programme_id"] is None


@pytest.mark.asyncio
async def test_create_creche_class_has_no_numbered_year(client: AsyncClient, auth: dict):
    """Creche is a single, undifferentiated group — display_name must never
    show a year number ("Creche 1"), unlike Nursery/KG/Basic."""
    await client.post("/academic/years", json={
        "name": "2024/2025", "start_date": "2024-09-02", "end_date": "2025-07-31",
    }, headers=auth)

    resp = await client.post("/academic/classes", json={
        "level": "Creche",
        "year_group": 1,
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["display_name"] == "Creche"

    # A second Creche group is still possible via stream, just never via year_group.
    resp2 = await client.post("/academic/classes", json={
        "level": "Creche",
        "year_group": 1,
        "stream": "A",
    }, headers=auth)
    assert resp2.status_code == 201
    assert resp2.json()["display_name"] == "Creche A"


@pytest.mark.asyncio
async def test_create_creche_class_rejects_nonone_year_group(client: AsyncClient, auth: dict):
    await client.post("/academic/years", json={
        "name": "2024/2025", "start_date": "2024-09-02", "end_date": "2025-07-31",
    }, headers=auth)

    resp = await client.post("/academic/classes", json={
        "level": "Creche",
        "year_group": 2,
    }, headers=auth)
    assert resp.status_code == 422
    assert "year_group" in resp.json()["detail"].lower() or "creche" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_duplicate_class_rejected_at_db_level(
    db_session: AsyncSession, school: School,
):
    """Proves the COALESCE'd unique index itself holds (a TOCTOU race could
    otherwise slip past create_class()'s own pre-insert SELECT), not just the
    service layer's check — same shape as the AcademicYear/AcademicTerm
    "one current" DB-level tests above. Both rows share the Basic-school
    shape (programme_id=NULL, stream=NULL) specifically, since that's the
    case a plain UniqueConstraint would silently fail to catch (NULL != NULL)."""
    from app.models.academic import Class

    db_session.add(Class(school_id=school.id, level="JHS", year_group=1, is_active=True))
    await db_session.flush()

    db_session.add(Class(school_id=school.id, level="JHS", year_group=1, is_active=True))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def _second_shs_school_auth(client: AsyncClient, db_session: AsyncSession) -> dict:
    """Create a second SHS school + superadmin and return their auth headers."""
    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    school = School(
        name="Second SHS Test School", school_code="SHS002",
        school_type=SchoolType.SHS,
        region_id=region.id, district_id=district.id, is_active=True,
    )
    db_session.add(school)
    await db_session.flush()
    user = User(
        login_type=LoginType.EMAIL, email="second-shs-admin@test.gh",
        password_hash=hash_password("pw"), is_active=True,
        is_superadmin=True, school_id=school.id,
    )
    db_session.add(user)
    await db_session.flush()
    resp = await client.post("/auth/superadmin-login", json={
        "identifier": "second-shs-admin@test.gh", "password": "pw",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_programmes_not_offered_until_adopted(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
):
    """A shared catalogue programme must not appear in a school's own list —
    or be assignable to a class — until explicitly adopted."""
    db_session.add(SHSProgramme(school_id=None, code="SCI_T", name="General Science", is_active=True))
    await db_session.flush()

    progs = (await client.get("/academic/programmes", headers=auth)).json()
    assert not any(p["code"] == "SCI_T" for p in progs)

    catalogue = (await client.get("/academic/programmes/catalogue", headers=auth)).json()
    catalogue_entry = next(c for c in catalogue if c["code"] == "SCI_T")

    class_resp = await client.post("/academic/classes", json={
        "level": "SHS", "year_group": 1, "programme_id": catalogue_entry["id"], "stream": "A",
    }, headers=auth)
    assert class_resp.status_code == 422


@pytest.mark.asyncio
async def test_adopt_programme_from_catalogue(
    client: AsyncClient, auth: dict, db_session: AsyncSession, school: School,
):
    db_session.add(SHSProgramme(school_id=None, code="BUS_T", name="Business", is_active=True))
    await db_session.flush()
    catalogue = (await client.get("/academic/programmes/catalogue", headers=auth)).json()
    entry = next(c for c in catalogue if c["code"] == "BUS_T")

    resp = await client.post("/academic/programmes/adopt", json={
        "catalogue_programme_id": entry["id"],
    }, headers=auth)
    assert resp.status_code == 201
    adopted = resp.json()
    assert adopted["id"] != entry["id"]
    assert adopted["school_id"] == str(school.id)
    assert adopted["name"] == "Business"

    progs = (await client.get("/academic/programmes", headers=auth)).json()
    assert any(p["code"] == "BUS_T" for p in progs)

    # Now assignable to a class.
    class_resp = await client.post("/academic/classes", json={
        "level": "SHS", "year_group": 1, "programme_id": adopted["id"], "stream": "A",
    }, headers=auth)
    assert class_resp.status_code == 201
    assert class_resp.json()["programme_name"] == "Business"


@pytest.mark.asyncio
async def test_adopting_same_programme_twice_rejected(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
):
    db_session.add(SHSProgramme(school_id=None, code="TECH_T", name="Technical", is_active=True))
    await db_session.flush()
    catalogue = (await client.get("/academic/programmes/catalogue", headers=auth)).json()
    entry = next(c for c in catalogue if c["code"] == "TECH_T")

    first = await client.post("/academic/programmes/adopt", json={
        "catalogue_programme_id": entry["id"],
    }, headers=auth)
    assert first.status_code == 201

    second = await client.post("/academic/programmes/adopt", json={
        "catalogue_programme_id": entry["id"],
    }, headers=auth)
    assert second.status_code == 409

    # Already-adopted, so it must no longer be offered in the catalogue.
    catalogue_after = (await client.get("/academic/programmes/catalogue", headers=auth)).json()
    assert not any(c["code"] == "TECH_T" for c in catalogue_after)


@pytest.mark.asyncio
async def test_schools_adopt_different_subsets_independently(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
):
    """School A can offer only Business while School B offers everything —
    adopting is per-school and doesn't affect the shared catalogue or any
    other school's own list."""
    db_session.add_all([
        SHSProgramme(school_id=None, code="BUS_I", name="Business", is_active=True),
        SHSProgramme(school_id=None, code="ARTS_I", name="General Arts", is_active=True),
    ])
    await db_session.flush()
    school_b_auth = await _second_shs_school_auth(client, db_session)

    catalogue = (await client.get("/academic/programmes/catalogue", headers=auth)).json()
    business = next(c for c in catalogue if c["code"] == "BUS_I")
    arts = next(c for c in catalogue if c["code"] == "ARTS_I")

    # School A adopts only Business.
    await client.post("/academic/programmes/adopt", json={"catalogue_programme_id": business["id"]}, headers=auth)

    # School B adopts both.
    await client.post("/academic/programmes/adopt", json={"catalogue_programme_id": business["id"]}, headers=school_b_auth)
    await client.post("/academic/programmes/adopt", json={"catalogue_programme_id": arts["id"]}, headers=school_b_auth)

    school_a_progs = {p["code"] for p in (await client.get("/academic/programmes", headers=auth)).json()}
    school_b_progs = {p["code"] for p in (await client.get("/academic/programmes", headers=school_b_auth)).json()}
    assert school_a_progs == {"BUS_I"}
    assert school_b_progs == {"BUS_I", "ARTS_I"}

    # The shared catalogue entries themselves are untouched by either adoption.
    shared = await db_session.scalar(select(SHSProgramme).where(SHSProgramme.code == "BUS_I", SHSProgramme.school_id.is_(None)))
    assert shared is not None


@pytest.mark.asyncio
async def test_cannot_edit_unadopted_catalogue_programme(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
):
    """The shared catalogue is read-only — PATCH on a not-yet-adopted
    programme id must 404, not silently fork or mutate the shared row."""
    global_prog = SHSProgramme(school_id=None, code="VARTS_T", name="Visual Arts", is_active=True)
    db_session.add(global_prog)
    await db_session.flush()

    resp = await client.patch(f"/academic/programmes/{global_prog.id}", json={
        "name": "Renamed",
    }, headers=auth)
    assert resp.status_code == 404

    await db_session.refresh(global_prog)
    assert global_prog.name == "Visual Arts"


@pytest.mark.asyncio
async def test_list_classes_by_year(client: AsyncClient, auth: dict):
    year_id = (await client.post("/academic/years", json={
        "name": "2024/2025", "start_date": "2024-09-02", "end_date": "2025-07-31",
    }, headers=auth)).json()["id"]

    for stream in ("A", "B"):
        await client.post("/academic/classes", json={
            "academic_year_id": year_id, "level": "SHS 1",
            "year_group": 2024, "stream": stream,
        }, headers=auth)

    resp = await client.get(f"/academic/classes?year_id={year_id}", headers=auth)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ── Subjects ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_and_list_subjects(client: AsyncClient, auth: dict):
    await client.post("/academic/subjects", json={
        "code": "ENG", "name": "English Language",
    }, headers=auth)
    await client.post("/academic/subjects", json={
        "code": "MATH", "name": "Core Mathematics",
    }, headers=auth)

    resp = await client.get("/academic/subjects", headers=auth)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_create_subject_rejects_bogus_catalogue_id(client: AsyncClient, auth: dict):
    """A nonexistent catalogue_id previously skipped the electives/SHS guard
    silently and fell through to an unhandled IntegrityError (500) on
    insert — must be a clean 404 instead."""
    resp = await client.post("/academic/subjects", json={
        "catalogue_id": str(uuid.uuid4()), "code": "BOGUS", "name": "Bogus Catalogue Link",
    }, headers=auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_subject_rejects_oversized_code(client: AsyncClient, auth: dict):
    """code is String(20) at the DB layer — an oversized value used to hit an
    unhandled IntegrityError (500) instead of a clean 422."""
    resp = await client.post("/academic/subjects", json={
        "code": "X" * 21, "name": "Whatever",
    }, headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_deactivated_subject_still_listed_for_reactivation(client: AsyncClient, auth: dict):
    """A hardcoded active-only filter would make Deactivate a one-way trip —
    list_subjects must still return an inactive subject so the UI can find
    and reactivate it."""
    subj_id = (await client.post("/academic/subjects", json={
        "code": "HIST_T", "name": "History",
    }, headers=auth)).json()["id"]

    await client.patch(f"/academic/subjects/{subj_id}", json={"is_active": False}, headers=auth)

    resp = await client.get("/academic/subjects", headers=auth)
    listed = next(s for s in resp.json() if s["id"] == subj_id)
    assert listed["is_active"] is False

    reactivated = await client.patch(f"/academic/subjects/{subj_id}", json={"is_active": True}, headers=auth)
    assert reactivated.json()["is_active"] is True


@pytest.mark.asyncio
async def test_assign_subject_rejects_other_schools_subject(
    client: AsyncClient, auth: dict, db_session: AsyncSession,
):
    """Subject rows are private per school (unlike the shared SubjectCatalogue)
    — a subject_id belonging to a different school must not be attachable to
    this school's class."""
    other_auth = await _basic_school_auth(client, db_session)
    other_subj_resp = await client.post("/academic/subjects", json={
        "code": "OTH", "name": "Other School's Subject",
    }, headers=other_auth)
    assert other_subj_resp.status_code == 201
    other_subject_id = other_subj_resp.json()["id"]

    class_resp = await client.post("/academic/classes", json={
        "level": "JHS", "year_group": 1, "stream": "A",
    }, headers=auth)
    assert class_resp.status_code == 201
    class_id = class_resp.json()["id"]

    resp = await client.post(f"/academic/classes/{class_id}/subjects", json={
        "subject_ids": [other_subject_id],
    }, headers=auth)
    assert resp.status_code == 404


# ── Inactive class blocks new structural writes ─────────────────────────────────
# A class marked is_active=False is a retired class group — attaching new
# curriculum/teacher assignments to it makes no more sense than editing a
# locked term. Read/list endpoints stay unaffected; only mutations that would
# grow a retired class's data are blocked (get_active_class, academic_class.py).

async def _deactivate(client: AsyncClient, auth: dict, class_id: str) -> None:
    resp = await client.patch(f"/academic/classes/{class_id}", json={"is_active": False}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_assign_subjects_rejected_on_inactive_class(client: AsyncClient, auth: dict):
    class_id = (await client.post("/academic/classes", json={
        "level": "JHS", "year_group": 1, "stream": "A",
    }, headers=auth)).json()["id"]
    subject_id = (await client.post("/academic/subjects", json={
        "code": "ENG", "name": "English",
    }, headers=auth)).json()["id"]
    await _deactivate(client, auth, class_id)

    resp = await client.post(f"/academic/classes/{class_id}/subjects", json={
        "subject_ids": [subject_id],
    }, headers=auth)
    assert resp.status_code == 422
    assert "inactive" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_assign_class_teacher_rejected_on_inactive_class(
    client: AsyncClient, auth: dict, staff_member, academic_year,
):
    class_id = (await client.post("/academic/classes", json={
        "level": "JHS", "year_group": 2, "stream": "A",
    }, headers=auth)).json()["id"]
    await _deactivate(client, auth, class_id)

    resp = await client.post(f"/academic/classes/{class_id}/class-teacher", json={
        "staff_member_id": str(staff_member.id), "academic_year_id": str(academic_year.id),
    }, headers=auth)
    assert resp.status_code == 422
    assert "inactive" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_assign_subject_teacher_rejected_on_inactive_class(
    client: AsyncClient, auth: dict, staff_member, academic_year,
):
    class_id, subject_id = await _class_with_subject(client, auth)
    await _deactivate(client, auth, class_id)

    resp = await client.post(f"/academic/classes/{class_id}/subject-teachers", json={
        "subject_id": subject_id, "staff_member_id": str(staff_member.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)
    assert resp.status_code == 422
    assert "inactive" in resp.json()["detail"].lower()


# ── Subject teachers ──────────────────────────────────────────────────────────
# SubjectTeacher is scoped to academic_year_id, matching ClassTeacher — one
# assignment per class+subject+year, not re-done every term.

async def _class_with_subject(client: AsyncClient, auth: dict) -> tuple[str, str]:
    class_id = (await client.post("/academic/classes", json={
        "level": "SHS", "year_group": 1, "stream": "A",
    }, headers=auth)).json()["id"]
    subject_id = (await client.post("/academic/subjects", json={
        "code": "PHY", "name": "Physics",
    }, headers=auth)).json()["id"]
    resp = await client.post(f"/academic/classes/{class_id}/subjects", json={
        "subject_ids": [subject_id],
    }, headers=auth)
    assert resp.status_code == 201
    return class_id, subject_id


@pytest.mark.asyncio
async def test_assign_subject_teacher_scoped_to_year(
    client: AsyncClient, auth: dict, staff_member, academic_year,
):
    class_id, subject_id = await _class_with_subject(client, auth)

    resp = await client.post(f"/academic/classes/{class_id}/subject-teachers", json={
        "subject_id": subject_id, "staff_member_id": str(staff_member.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["academic_year_id"] == str(academic_year.id)

    listed = await client.get(
        f"/academic/classes/{class_id}/subject-teachers?year_id={academic_year.id}", headers=auth,
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["staff_member_id"] == str(staff_member.id)


@pytest.mark.asyncio
async def test_reassign_subject_teacher_same_year_updates_in_place(
    client: AsyncClient, auth: dict, staff_member, academic_year, db_session: AsyncSession, school,
):
    """A mid-year teacher change updates the existing row rather than
    creating a second one for the same class+subject+year."""
    from app.models.staff import StaffMember
    class_id, subject_id = await _class_with_subject(client, auth)

    other = StaffMember(school_id=school.id, staff_number="TCH002", first_name="Ama", last_name="Boateng", is_active=True)
    db_session.add(other)
    await db_session.flush()

    await client.post(f"/academic/classes/{class_id}/subject-teachers", json={
        "subject_id": subject_id, "staff_member_id": str(staff_member.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)
    resp = await client.post(f"/academic/classes/{class_id}/subject-teachers", json={
        "subject_id": subject_id, "staff_member_id": str(other.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)
    assert resp.status_code == 201
    assert resp.json()["staff_member_id"] == str(other.id)

    listed = await client.get(
        f"/academic/classes/{class_id}/subject-teachers?year_id={academic_year.id}", headers=auth,
    )
    assert len(listed.json()) == 1
    assert listed.json()[0]["staff_member_id"] == str(other.id)


@pytest.mark.asyncio
async def test_list_subject_teachers_filters_by_year(
    client: AsyncClient, auth: dict, staff_member, academic_year, db_session: AsyncSession, school,
):
    from app.models.academic import AcademicYear
    class_id, subject_id = await _class_with_subject(client, auth)

    other_year = AcademicYear(school_id=school.id, name="2099/2100", start_date=date(2099, 9, 1), end_date=date(2100, 7, 31), is_current=False)
    db_session.add(other_year)
    await db_session.flush()

    await client.post(f"/academic/classes/{class_id}/subject-teachers", json={
        "subject_id": subject_id, "staff_member_id": str(staff_member.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)

    same_year = await client.get(
        f"/academic/classes/{class_id}/subject-teachers?year_id={academic_year.id}", headers=auth,
    )
    other_year_resp = await client.get(
        f"/academic/classes/{class_id}/subject-teachers?year_id={other_year.id}", headers=auth,
    )
    assert len(same_year.json()) == 1
    assert other_year_resp.json() == []


@pytest.mark.asyncio
async def test_responsibilities_shows_subject_assignment_by_year(
    client: AsyncClient, auth: dict, staff_member, academic_year,
):
    class_id, subject_id = await _class_with_subject(client, auth)
    await client.post(f"/academic/classes/{class_id}/subject-teachers", json={
        "subject_id": subject_id, "staff_member_id": str(staff_member.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)

    resp = await client.get(f"/staff/{staff_member.id}/responsibilities", headers=auth)
    assert resp.status_code == 200
    assignment = resp.json()["subject_assignments"][0]
    assert assignment["academic_year_id"] == str(academic_year.id)
    assert assignment["academic_year_name"] == academic_year.name
    assert "academic_term_id" not in assignment


# ── Removing a class/subject teacher ────────────────────────────────────────────
# Previously the only way to change who holds one of these roles was handing it
# to someone else (an upsert) — there was no way to plainly unassign it.

@pytest.mark.asyncio
async def test_remove_class_teacher(
    client: AsyncClient, auth: dict, staff_member, academic_year, redis_permissions: None,
):
    class_id = (await client.post("/academic/classes", json={
        "level": "JHS", "year_group": 1, "stream": "A",
    }, headers=auth)).json()["id"]
    await client.post(f"/academic/classes/{class_id}/class-teacher", json={
        "staff_member_id": str(staff_member.id), "academic_year_id": str(academic_year.id),
    }, headers=auth)

    resp = await client.delete(
        f"/academic/classes/{class_id}/class-teacher?year_id={academic_year.id}", headers=auth,
    )
    assert resp.status_code == 204

    listed = await client.get(
        f"/academic/classes/{class_id}/class-teacher?year_id={academic_year.id}", headers=auth,
    )
    assert listed.json() is None


@pytest.mark.asyncio
async def test_remove_class_teacher_404_when_nothing_to_remove(
    client: AsyncClient, auth: dict, academic_year,
):
    class_id = (await client.post("/academic/classes", json={
        "level": "JHS", "year_group": 1, "stream": "B",
    }, headers=auth)).json()["id"]

    resp = await client.delete(
        f"/academic/classes/{class_id}/class-teacher?year_id={academic_year.id}", headers=auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_remove_subject_teacher(
    client: AsyncClient, auth: dict, staff_member, academic_year,
):
    class_id, subject_id = await _class_with_subject(client, auth)
    await client.post(f"/academic/classes/{class_id}/subject-teachers", json={
        "subject_id": subject_id, "staff_member_id": str(staff_member.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)

    resp = await client.delete(
        f"/academic/classes/{class_id}/subject-teachers/{subject_id}?year_id={academic_year.id}",
        headers=auth,
    )
    assert resp.status_code == 204

    listed = await client.get(
        f"/academic/classes/{class_id}/subject-teachers?year_id={academic_year.id}", headers=auth,
    )
    assert listed.json() == []


@pytest.mark.asyncio
async def test_remove_subject_teacher_404_when_nothing_to_remove(
    client: AsyncClient, auth: dict, academic_year,
):
    class_id, subject_id = await _class_with_subject(client, auth)

    resp = await client.delete(
        f"/academic/classes/{class_id}/subject-teachers/{subject_id}?year_id={academic_year.id}",
        headers=auth,
    )
    assert resp.status_code == 404


# ── Cross-school ownership on teacher assignment ────────────────────────────────
# assign_class_teacher/assign_subject_teacher previously trusted
# staff_member_id/academic_year_id (and, for the latter, subject_id) from the
# client with zero ownership check — the same bug shape already closed for
# assign_subjects()'s subject_ids (test_assign_subject_rejects_other_schools_subject
# above). Also closes a permission-escalation side effect: core/permissions.py's
# CLASS_TEACHER/HOUSEMASTER auto-derivation only ever filtered by
# staff_member_id, so a planted cross-school ClassTeacher row would have
# granted the victim staff member CLASS_TEACHER's permissions at a school
# they don't work for.

@pytest.mark.asyncio
async def test_assign_class_teacher_rejects_other_schools_staff(
    client: AsyncClient, auth: dict, db_session: AsyncSession, academic_year,
):
    other_auth = await _basic_school_auth(client, db_session)
    other_staff_id = (await client.post("/staff", json={
        "staff_number": "OTH-CT", "first_name": "Other", "last_name": "Teacher",
    }, headers=other_auth)).json()["id"]

    class_id = (await client.post("/academic/classes", json={
        "level": "JHS", "year_group": 1, "stream": "A",
    }, headers=auth)).json()["id"]

    resp = await client.post(f"/academic/classes/{class_id}/class-teacher", json={
        "staff_member_id": other_staff_id, "academic_year_id": str(academic_year.id),
    }, headers=auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_assign_class_teacher_rejects_other_schools_year(
    client: AsyncClient, auth: dict, db_session: AsyncSession, staff_member,
):
    other_auth = await _second_shs_school_auth(client, db_session)
    other_year_id = (await client.post("/academic/years", json={
        "name": "2030/2031", "start_date": "2030-09-01", "end_date": "2031-07-31",
    }, headers=other_auth)).json()["id"]

    class_id = (await client.post("/academic/classes", json={
        "level": "JHS", "year_group": 1, "stream": "B",
    }, headers=auth)).json()["id"]

    resp = await client.post(f"/academic/classes/{class_id}/class-teacher", json={
        "staff_member_id": str(staff_member.id), "academic_year_id": other_year_id,
    }, headers=auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_assign_subject_teacher_rejects_other_schools_staff(
    client: AsyncClient, auth: dict, db_session: AsyncSession, academic_year,
):
    other_auth = await _basic_school_auth(client, db_session)
    other_staff_id = (await client.post("/staff", json={
        "staff_number": "OTH-ST", "first_name": "Other", "last_name": "Teacher",
    }, headers=other_auth)).json()["id"]
    class_id, subject_id = await _class_with_subject(client, auth)

    resp = await client.post(f"/academic/classes/{class_id}/subject-teachers", json={
        "subject_id": subject_id, "staff_member_id": other_staff_id,
        "academic_year_id": str(academic_year.id),
    }, headers=auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_assign_subject_teacher_rejects_subject_not_on_curriculum(
    client: AsyncClient, auth: dict, staff_member, academic_year,
):
    """subject_id must be an active ClassSubject on this class — mirrors
    register_subjects/create_assessment's same guard, and as a side effect
    closes the same cross-school subject_id gap assign_subjects() already
    had fixed (a cross-school subject_id can never be an active ClassSubject
    on a class it doesn't belong to)."""
    class_id = (await client.post("/academic/classes", json={
        "level": "SHS", "year_group": 1, "stream": "C",
    }, headers=auth)).json()["id"]
    # Real subject, same school, but never attached to this class's curriculum.
    subject_id = (await client.post("/academic/subjects", json={
        "code": "UNATT", "name": "Unattached Subject",
    }, headers=auth)).json()["id"]

    resp = await client.post(f"/academic/classes/{class_id}/subject-teachers", json={
        "subject_id": subject_id, "staff_member_id": str(staff_member.id),
        "academic_year_id": str(academic_year.id),
    }, headers=auth)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_school_class_teacher_does_not_leak_permission(
    client: AsyncClient, auth: dict, db_session: AsyncSession, academic_year, school,
    redis_permissions: None,
):
    """Even bypassing the ownership check entirely (simulating the exact
    planted-row scenario the fix above prevents from happening via the API),
    resolve_permissions()'s CLASS_TEACHER auto-derivation must not grant the
    position's permissions to a staff member for a ClassTeacher row that
    belongs to a DIFFERENT school than the one they're logging into."""
    from app.models.academic import Class, ClassTeacher
    from app.models.staff import StaffMember

    other_auth = await _second_shs_school_auth(client, db_session)
    other_school = await db_session.scalar(
        select(School).where(School.school_code == "SHS002")
    )

    # A real staff member at THIS school, with no ClassTeacher row here at all.
    staff_resp = await client.post("/staff", json={
        "staff_number": "LEAK-CT", "first_name": "Leak", "last_name": "Target",
    }, headers=auth)
    staff_id = staff_resp.json()["id"]

    victim_email = "leak-target@presec-test.edu.gh"
    db_session.add(User(
        school_id=school.id, login_type=LoginType.EMAIL, email=victim_email,
        password_hash=hash_password("Whatever123!"), is_active=True, staff_member_id=staff_id,
    ))
    await db_session.flush()

    # Directly plant a ClassTeacher row belonging to the OTHER school,
    # pointing at this staff member's real id — bypassing the API's own
    # ownership check on purpose, to prove the derivation itself is safe
    # even if some other path ever let this data exist.
    other_class = Class(school_id=other_school.id, level="SHS", year_group=1, stream="Z", is_active=True)
    db_session.add(other_class)
    await db_session.flush()
    db_session.add(ClassTeacher(
        school_id=other_school.id, class_id=other_class.id,
        staff_member_id=uuid.UUID(staff_id), academic_year_id=academic_year.id, is_active=True,
    ))
    await db_session.flush()

    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL", "identifier": victim_email, "password": "Whatever123!",
        "school_code": school.school_code,
    })
    assert resp.status_code == 200, resp.text
    victim_auth = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    # CLASS_TEACHER grants students.create — a plain staff member with zero
    # legitimate permissions must not be able to create a student.
    resp = await client.post("/students", json={
        "first_name": "Should", "last_name": "Fail",
    }, headers=victim_auth)
    assert resp.status_code == 403


# ── SHS / BASIC guards ────────────────────────────────────────────────────────

async def _basic_school_auth(client: AsyncClient, db_session: AsyncSession) -> dict:
    """Create a BASIC school + superadmin and return their auth headers."""
    region = await db_session.scalar(select(GhanaRegion).limit(1))
    district = await db_session.scalar(select(GhanaDistrict).limit(1))
    school = School(
        name="Basic Test School", school_code="BASIC001",
        school_type=SchoolType.BASIC,
        region_id=region.id, district_id=district.id, is_active=True,
    )
    db_session.add(school)
    await db_session.flush()
    user = User(
        login_type=LoginType.EMAIL, email="basic-admin@test.gh",
        password_hash=hash_password("pw"), is_active=True,
        is_superadmin=True, school_id=school.id,
    )
    db_session.add(user)
    await db_session.flush()
    resp = await client.post("/auth/superadmin-login", json={
        "identifier": "basic-admin@test.gh", "password": "pw",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_basic_school_cannot_create_programme(
    client: AsyncClient, db_session: AsyncSession
):
    basic_auth = await _basic_school_auth(client, db_session)
    resp = await client.post("/academic/programmes", json={
        "code": "GEN", "name": "General Arts",
    }, headers=basic_auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_basic_school_list_programmes_returns_empty(
    client: AsyncClient, db_session: AsyncSession
):
    basic_auth = await _basic_school_auth(client, db_session)
    resp = await client.get("/academic/programmes", headers=basic_auth)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_basic_school_cannot_create_elective_subject(
    client: AsyncClient, db_session: AsyncSession
):
    basic_auth = await _basic_school_auth(client, db_session)
    cat = SubjectCatalogue(
        code="ELEC001", name="Elective Maths",
        subject_type=SubjectType.ELECTIVE, level=SchoolLevel.SHS, is_active=True,
    )
    db_session.add(cat)
    await db_session.flush()
    resp = await client.post("/academic/subjects", json={
        "catalogue_id": str(cat.id), "code": "ELEC001", "name": "Elective Maths",
    }, headers=basic_auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_shs_school_can_create_elective_subject(
    client: AsyncClient, auth: dict, db_session: AsyncSession
):
    """The SHS school fixture can freely create elective subjects."""
    cat = SubjectCatalogue(
        code="ELEC002", name="Physics",
        subject_type=SubjectType.ELECTIVE, level=SchoolLevel.SHS, is_active=True,
    )
    db_session.add(cat)
    await db_session.flush()
    resp = await client.post("/academic/subjects", json={
        "catalogue_id": str(cat.id), "code": "ELEC002", "name": "Physics",
    }, headers=auth)
    assert resp.status_code == 201
