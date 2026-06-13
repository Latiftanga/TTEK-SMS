"""
Student bulk import integration tests.
Run inside Docker: docker compose exec api pytest app/tests/test_student_import.py -v
"""
import io
import pytest
from httpx import AsyncClient

from app.models.school import School
from app.services.student_import_constants import DATA_START, _COLS, make_sentinel

_XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _make_xlsx(rows: list[list], school_code: str) -> bytes:
    """Build a minimal .xlsx with the school-specific sentinel and supplied data rows."""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Student Data"
    ws["N1"] = make_sentinel(school_code)
    for col, label, *_ in _COLS:
        ws[f"{col}3"] = label
    for r_idx, row_vals in enumerate(rows):
        row_num = DATA_START + r_idx
        for c_idx, val in enumerate(row_vals):
            ws.cell(row=row_num, column=c_idx + 1, value=val)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


_BLANK_ROW = [None] * len(_COLS)


# ── Template download ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_download_template_returns_xlsx(client: AsyncClient, auth: dict):
    resp = await client.get("/students/import/template", headers=auth)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(_XLSX_CT)
    assert len(resp.content) > 3_000


@pytest.mark.asyncio
async def test_template_contains_school_sentinel(client: AsyncClient, auth: dict, school: School):
    from openpyxl import load_workbook
    resp = await client.get("/students/import/template", headers=auth)
    wb = load_workbook(io.BytesIO(resp.content), data_only=True)
    ws = wb["Student Data"]
    assert ws["N1"].value == make_sentinel(school.school_code)


@pytest.mark.asyncio
async def test_template_has_all_headers(client: AsyncClient, auth: dict):
    from openpyxl import load_workbook
    resp = await client.get("/students/import/template", headers=auth)
    wb = load_workbook(io.BytesIO(resp.content), data_only=True)
    ws = wb["Student Data"]
    headers = [ws[f"{col}3"].value for col, *_ in _COLS]
    assert all(h is not None for h in headers)


# ── Upload processing ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_import_all_valid(client: AsyncClient, auth: dict, school: School):
    rows = [
        ["ADM001", "Ama",  None, "Boateng", None, "FEMALE", None, None, None, None],
        ["ADM002", "Kofi", None, "Asante",  None, "MALE",   None, None, None, None],
    ]
    resp = await client.post(
        "/students/import",
        files={"file": ("students.xlsx", _make_xlsx(rows, school.school_code), _XLSX_CT)},
        headers=auth,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 2
    assert data["failed"] == 0
    assert data["errors"] == []
    assert "batch_id" in data


@pytest.mark.asyncio
async def test_import_partial_success(client: AsyncClient, auth: dict, school: School):
    """Two valid rows + one missing last_name → 2 created, 1 failed."""
    rows = [
        ["ADM001", "Ama",  None, "Boateng", None, None, None, None, None, None],
        ["ADM002", "Kofi", None, "Asante",  None, None, None, None, None, None],
        ["ADM003", "Yaw",  None, None,      None, None, None, None, None, None],
    ]
    resp = await client.post(
        "/students/import",
        files={"file": ("students.xlsx", _make_xlsx(rows, school.school_code), _XLSX_CT)},
        headers=auth,
    )
    data = resp.json()
    assert data["created"] == 2
    assert data["failed"] == 1
    assert data["errors"][0]["row"] == DATA_START + 2


@pytest.mark.asyncio
async def test_import_duplicate_admission_number(client: AsyncClient, auth: dict, school: School):
    """Duplicate admission number in same file → first created, second failed."""
    rows = [
        ["ADM001", "Ama",  None, "Boateng", None, None, None, None, None, None],
        ["ADM001", "Akua", None, "Mensah",  None, None, None, None, None, None],
    ]
    resp = await client.post(
        "/students/import",
        files={"file": ("students.xlsx", _make_xlsx(rows, school.school_code), _XLSX_CT)},
        headers=auth,
    )
    data = resp.json()
    assert data["created"] == 1
    assert data["failed"] == 1
    assert "already exists" in data["errors"][0]["error"]


@pytest.mark.asyncio
async def test_import_rejects_existing_admission_number(client: AsyncClient, auth: dict, school: School):
    """Admission number already in DB is rejected."""
    await client.post("/students", json={
        "admission_number": "PRE001", "first_name": "Existing", "last_name": "Student",
    }, headers=auth)
    rows = [["PRE001", "New", None, "Person", None, None, None, None, None, None]]
    resp = await client.post(
        "/students/import",
        files={"file": ("students.xlsx", _make_xlsx(rows, school.school_code), _XLSX_CT)},
        headers=auth,
    )
    data = resp.json()
    assert data["created"] == 0
    assert data["failed"] == 1


@pytest.mark.asyncio
async def test_import_cross_school_sentinel_rejected(client: AsyncClient, auth: dict):
    """Template from a different school returns 422 with a helpful message."""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Student Data"
    ws["N1"] = make_sentinel("OTHER_SCHOOL")
    buf = io.BytesIO()
    wb.save(buf)
    resp = await client.post(
        "/students/import",
        files={"file": ("other.xlsx", buf.getvalue(), _XLSX_CT)},
        headers=auth,
    )
    assert resp.status_code == 422
    assert "OTHER_SCHOOL" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_import_wrong_template_rejected(client: AsyncClient, auth: dict):
    """Generic .xlsx with no sentinel → 422."""
    from openpyxl import Workbook
    wb = Workbook()
    buf = io.BytesIO()
    wb.save(buf)
    resp = await client.post(
        "/students/import",
        files={"file": ("generic.xlsx", buf.getvalue(), _XLSX_CT)},
        headers=auth,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_import_non_xlsx_rejected(client: AsyncClient, auth: dict):
    resp = await client.post(
        "/students/import",
        files={"file": ("students.csv", b"admission_number,first_name\nADM001,Ama", "text/csv")},
        headers=auth,
    )
    assert resp.status_code == 422
