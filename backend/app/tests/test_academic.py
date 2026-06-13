"""
Academic setup integration tests.
Run inside Docker: docker compose exec api pytest app/tests/test_academic.py -v

Fixtures (school, school_admin, auth) are defined in conftest.py.
"""
import pytest
from httpx import AsyncClient
from app.models.school import School


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
        "academic_year_id": year_id,
        "level": "SHS 2",
        "year_group": 2023,
        "programme_id": prog_id,
        "stream": "A",
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["display_name"] == "SHS 2 General Science A (2023)"
    assert data["programme_name"] == "General Science"


@pytest.mark.asyncio
async def test_create_basic_class_no_programme(client: AsyncClient, auth: dict):
    year_id = (await client.post("/academic/years", json={
        "name": "2024/2025", "start_date": "2024-09-02", "end_date": "2025-07-31",
    }, headers=auth)).json()["id"]

    resp = await client.post("/academic/classes", json={
        "academic_year_id": year_id,
        "level": "JHS 2",
        "year_group": 2023,
        "stream": "B",
    }, headers=auth)
    assert resp.status_code == 201
    data = resp.json()
    assert data["display_name"] == "JHS 2 B (2023)"
    assert data["programme_id"] is None


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
