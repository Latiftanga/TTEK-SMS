"""
Document upload/list/download/delete integration tests.
Run inside Docker: docker compose exec api pytest app/tests/test_documents.py -v
"""
import io
import uuid

import pytest
from httpx import AsyncClient

from app.models.students import Student


@pytest.mark.asyncio
async def test_upload_document(
    client: AsyncClient, auth: dict, student: Student
):
    pdf_bytes = b"%PDF-1.4 test"
    resp = await client.post(
        f"/documents/student/{student.id}?document_type=certificate",
        files={"file": ("cert.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=auth,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["file_name"] == "cert.pdf"
    assert data["entity_type"] == "student"
    assert str(data["entity_id"]) == str(student.id)
    assert data["document_type"] == "certificate"


@pytest.mark.asyncio
async def test_upload_disallowed_mime_type(
    client: AsyncClient, auth: dict, student: Student
):
    resp = await client.post(
        f"/documents/student/{student.id}?document_type=data",
        files={"file": ("data.csv", io.BytesIO(b"a,b,c"), "text/csv")},
        headers=auth,
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_list_documents(
    client: AsyncClient, auth: dict, student: Student
):
    await client.post(
        f"/documents/student/{student.id}?document_type=photo",
        files={"file": ("photo.jpg", io.BytesIO(b"fake-jpeg"), "image/jpeg")},
        headers=auth,
    )
    resp = await client.get(f"/documents/student/{student.id}", headers=auth)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_list_documents_wrong_school(
    client: AsyncClient, auth: dict
):
    """Documents for a random entity_id return empty list, not 404."""
    resp = await client.get(f"/documents/student/{uuid.uuid4()}", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_download_document(
    client: AsyncClient, auth: dict, student: Student
):
    pdf_bytes = b"%PDF-1.4 sample"
    upload = await client.post(
        f"/documents/student/{student.id}?document_type=letter",
        files={"file": ("letter.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=auth,
    )
    doc_id = upload.json()["id"]
    resp = await client.get(f"/documents/{doc_id}/download", headers=auth)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")


@pytest.mark.asyncio
async def test_delete_document(
    client: AsyncClient, auth: dict, student: Student
):
    upload = await client.post(
        f"/documents/student/{student.id}?document_type=form",
        files={"file": ("form.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=auth,
    )
    doc_id = upload.json()["id"]
    del_resp = await client.delete(f"/documents/{doc_id}", headers=auth)
    assert del_resp.status_code == 204
    # Confirm gone
    dl_resp = await client.get(f"/documents/{doc_id}/download", headers=auth)
    assert dl_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_unknown_document(
    client: AsyncClient, auth: dict
):
    resp = await client.delete(f"/documents/{uuid.uuid4()}", headers=auth)
    assert resp.status_code == 404
