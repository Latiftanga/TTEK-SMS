"""
Curriculum material upload/list/delete + text extraction + full-text search
— the grounding data source for the AI lesson-planning chat assistant.

Run inside Docker: docker compose exec api pytest app/tests/test_curriculum_materials.py -v
"""
import io

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from weasyprint import HTML

from app.models.academic import Class, ClassSubject, SchoolLevel, Subject, SubjectCatalogue, SubjectType
from app.models.curriculum_materials import CurriculumMaterial, CurriculumMaterialChunk, ExtractionStatus
from app.models.school import School
from app.services import curriculum_extraction
from app.services.curriculum_search import search_curriculum


def _real_pdf_bytes(paragraphs: list[str]) -> bytes:
    body = "".join(f"<p>{p}</p>" for p in paragraphs)
    return HTML(string=f"<html><body>{body}</body></html>").write_pdf()


def _blank_pdf_bytes() -> bytes:
    return HTML(string="<html><body></body></html>").write_pdf()


@pytest.fixture
async def class_subject(db_session: AsyncSession, school: School, school_class: Class) -> ClassSubject:
    cat = SubjectCatalogue(name="Mathematics", code="MATH_CM", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code="MATH_CM", name="Mathematics", is_active=True)
    db_session.add(subj)
    await db_session.flush()
    cs = ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subj.id, is_active=True)
    db_session.add(cs)
    await db_session.flush()
    return cs


# ── upload / list / delete ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_rejects_non_pdf(client: AsyncClient, auth: dict, class_subject: ClassSubject):
    resp = await client.post(
        f"/curriculum-materials/{class_subject.id}", params={"document_type": "TEXTBOOK"}, headers=auth,
        files={"file": ("notes.docx", io.BytesIO(b"PK\x03\x04fake"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_upload_rejects_mismatched_content(client: AsyncClient, auth: dict, class_subject: ClassSubject):
    resp = await client.post(
        f"/curriculum-materials/{class_subject.id}", params={"document_type": "TEXTBOOK"}, headers=auth,
        files={"file": ("fake.pdf", io.BytesIO(b"<html>not a pdf</html>"), "application/pdf")},
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_upload_success_and_list_and_delete(client: AsyncClient, auth: dict, class_subject: ClassSubject):
    pdf_bytes = _real_pdf_bytes(["Chapter 1: Fractions are parts of a whole number."])
    created = await client.post(
        f"/curriculum-materials/{class_subject.id}", params={"document_type": "TEXTBOOK"}, headers=auth,
        files={"file": ("textbook.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["document_type"] == "TEXTBOOK"
    assert data["extraction_status"] == "PENDING"

    listed = await client.get(f"/curriculum-materials/{class_subject.id}", headers=auth)
    assert listed.status_code == 200
    assert [m["id"] for m in listed.json()] == [data["id"]]

    deleted = await client.delete(f"/curriculum-materials/{data['id']}", headers=auth)
    assert deleted.status_code == 204
    listed_again = await client.get(f"/curriculum-materials/{class_subject.id}", headers=auth)
    assert listed_again.json() == []


@pytest.mark.asyncio
async def test_upload_404_for_cross_school_class_subject(client: AsyncClient, auth: dict):
    import uuid
    resp = await client.post(
        f"/curriculum-materials/{uuid.uuid4()}", params={"document_type": "TEXTBOOK"}, headers=auth,
        files={"file": ("x.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    assert resp.status_code == 404


# ── extraction ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_extraction_produces_chunks_for_real_text_pdf(
    db_session: AsyncSession, school: School, class_subject: ClassSubject, school_admin,
):
    pdf_bytes = _real_pdf_bytes([
        "Chapter 1: Fractions are parts of a whole number, written as one integer over another.",
        "Chapter 2: Decimals represent fractions with a denominator that is a power of ten.",
    ])
    import uuid
    from datetime import datetime, timezone
    from pathlib import Path
    from app.core.config import settings

    mat = CurriculumMaterial(
        id=uuid.uuid4(), school_id=school.id, class_subject_id=class_subject.id,
        document_type="TEXTBOOK", file_path=f"curriculum_materials/{school.id}/{class_subject.id}/test.pdf",
        file_name="test.pdf", file_size=len(pdf_bytes), mime_type="application/pdf",
        uploaded_by_id=school_admin.id, created_at=datetime.now(timezone.utc),
        extraction_status=ExtractionStatus.PENDING,
    )
    db_session.add(mat)
    await db_session.flush()

    dest = Path(settings.secure_upload_dir) / mat.file_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(pdf_bytes)
    try:
        result = await curriculum_extraction._run(db_session, mat.id)
        assert result["status"] == "done"
        assert result["pages_extracted"] >= 1

        await db_session.refresh(mat)
        assert mat.extraction_status == ExtractionStatus.DONE

        chunks = list(await db_session.scalars(
            select(CurriculumMaterialChunk).where(CurriculumMaterialChunk.material_id == mat.id)
        ))
        assert len(chunks) >= 1
        assert "Fractions" in chunks[0].chunk_text or "Decimals" in chunks[0].chunk_text
    finally:
        dest.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_extraction_flags_empty_for_no_text_pdf(
    db_session: AsyncSession, school: School, class_subject: ClassSubject, school_admin,
):
    import uuid
    from datetime import datetime, timezone
    from pathlib import Path
    from app.core.config import settings

    pdf_bytes = _blank_pdf_bytes()
    mat = CurriculumMaterial(
        id=uuid.uuid4(), school_id=school.id, class_subject_id=class_subject.id,
        document_type="SYLLABUS", file_path=f"curriculum_materials/{school.id}/{class_subject.id}/blank.pdf",
        file_name="blank.pdf", file_size=len(pdf_bytes), mime_type="application/pdf",
        uploaded_by_id=school_admin.id, created_at=datetime.now(timezone.utc),
        extraction_status=ExtractionStatus.PENDING,
    )
    db_session.add(mat)
    await db_session.flush()

    dest = Path(settings.secure_upload_dir) / mat.file_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(pdf_bytes)
    try:
        result = await curriculum_extraction._run(db_session, mat.id)
        assert result["status"] == "empty"

        await db_session.refresh(mat)
        assert mat.extraction_status == ExtractionStatus.EMPTY
        assert mat.extraction_error is not None

        chunks = list(await db_session.scalars(
            select(CurriculumMaterialChunk).where(CurriculumMaterialChunk.material_id == mat.id)
        ))
        assert chunks == []
    finally:
        dest.unlink(missing_ok=True)


# ── search ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_returns_relevant_chunk_only(
    db_session: AsyncSession, school: School, class_subject: ClassSubject, school_admin,
):
    import uuid
    from datetime import datetime, timezone
    from pathlib import Path
    from app.core.config import settings

    pdf_bytes = _real_pdf_bytes([
        "Photosynthesis is the process by which plants convert sunlight into energy.",
    ])
    mat = CurriculumMaterial(
        id=uuid.uuid4(), school_id=school.id, class_subject_id=class_subject.id,
        document_type="TEXTBOOK", file_path=f"curriculum_materials/{school.id}/{class_subject.id}/bio.pdf",
        file_name="bio.pdf", file_size=len(pdf_bytes), mime_type="application/pdf",
        uploaded_by_id=school_admin.id, created_at=datetime.now(timezone.utc),
        extraction_status=ExtractionStatus.PENDING,
    )
    db_session.add(mat)
    await db_session.flush()

    dest = Path(settings.secure_upload_dir) / mat.file_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(pdf_bytes)
    try:
        await curriculum_extraction._run(db_session, mat.id)

        hits = await search_curriculum(class_subject.id, "photosynthesis energy", school.id, db_session)
        assert len(hits) == 1
        assert "Photosynthesis" in hits[0].chunk_text

        misses = await search_curriculum(class_subject.id, "trigonometry", school.id, db_session)
        assert misses == []
    finally:
        dest.unlink(missing_ok=True)
