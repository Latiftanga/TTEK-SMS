"""
Structured curriculum-unit extraction (services/curriculum_unit_extraction.py)
— map-reduce AI extraction over CurriculumMaterialChunk pages into
CurriculumUnit rows. Not regex/heading matching, so these tests stub the AI
driver's JSON responses directly rather than depending on any particular
document format.

Run inside Docker: docker compose exec api pytest app/tests/test_curriculum_unit_extraction.py -v
"""
import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import Class, ClassSubject, SchoolLevel, Subject, SubjectCatalogue, SubjectType
from app.models.curriculum_materials import CurriculumMaterial, CurriculumMaterialChunk, ExtractionStatus
from app.models.curriculum_units import CurriculumUnit
from app.models.school import AiConfig, AiProvider, School
from app.services import ai_config as ai_config_module
from app.services import curriculum_unit_extraction
from sqlalchemy import select


@pytest.fixture
async def class_subject(db_session: AsyncSession, school: School, school_class: Class) -> ClassSubject:
    cat = SubjectCatalogue(name="Computing", code="COMP_CUE", subject_type=SubjectType.CORE, level=SchoolLevel.SHS)
    db_session.add(cat)
    await db_session.flush()
    subj = Subject(school_id=school.id, catalogue_id=cat.id, code="COMP_CUE", name="Computing", is_active=True)
    db_session.add(subj)
    await db_session.flush()
    cs = ClassSubject(school_id=school.id, class_id=school_class.id, subject_id=subj.id, is_active=True)
    db_session.add(cs)
    await db_session.flush()
    return cs


@pytest.fixture
async def material(db_session: AsyncSession, school: School, class_subject: ClassSubject, school_admin) -> CurriculumMaterial:
    mat = CurriculumMaterial(
        id=uuid.uuid4(), school_id=school.id, class_subject_id=class_subject.id,
        document_type="TEACHER_MANUAL", file_path="x.pdf", file_name="x.pdf",
        file_size=1, mime_type="application/pdf", uploaded_by_id=school_admin.id,
        created_at=datetime.now(timezone.utc), extraction_status=ExtractionStatus.DONE,
    )
    db_session.add(mat)
    await db_session.flush()
    return mat


async def _add_chunk(db_session: AsyncSession, school: School, material: CurriculumMaterial, page: int, text: str) -> None:
    from sqlalchemy import func, insert
    await db_session.execute(insert(CurriculumMaterialChunk).values(
        id=uuid.uuid4(), school_id=school.id, material_id=material.id,
        page_number=page, chunk_text=text, search_vector=func.to_tsvector("english", text),
    ))
    await db_session.flush()


class _SequenceStubDriver:
    """Returns a different canned response per call, in order — unlike
    _StubDriver (test_lesson_plan_generation.py) which always returns the
    same one. Needed here since multi-batch extraction makes several real
    sequential calls that must each return different content."""
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    async def generate(self, prompt: str, system: str = "") -> str:
        return self._responses.pop(0)


def _patch_sequence(monkeypatch, responses: list[str]) -> None:
    monkeypatch.setattr(ai_config_module, "build_ai_driver", lambda *a, **kw: _SequenceStubDriver(responses))


def _batch_json(units: list[dict]) -> str:
    return json.dumps({"units": units})


async def _with_ai_config(db_session: AsyncSession, school: School) -> None:
    db_session.add(AiConfig(school_id=school.id, provider=AiProvider.GEMINI, api_key="fake-key", daily_limit_per_teacher=100, is_active=True))
    await db_session.flush()


@pytest.mark.asyncio
async def test_extraction_merges_batches_and_assigns_sequence_numbers(
    db_session: AsyncSession, school: School, material: CurriculumMaterial, monkeypatch,
):
    await _with_ai_config(db_session, school)
    # Two chunks, one page each — small enough to stay in one batch together
    # (well under the page/char caps), so both units come from a single call.
    await _add_chunk(db_session, school, material, 1, "Week 1 content about logic gates.")
    await _add_chunk(db_session, school, material, 2, "Week 2 content about boolean expressions.")

    _patch_sequence(monkeypatch, [_batch_json([
        {"unit_label": "Week 1", "strand": "Computer Architecture", "sub_strand": "Data Storage",
         "content_standard": "Demonstrate understanding of logic.", "indicator": "Determine logic operations.",
         "topics": "Logic gates", "start_page": 1, "end_page": 1},
        {"unit_label": "Week 2", "strand": "Computer Architecture", "sub_strand": "Data Storage",
         "content_standard": "Demonstrate understanding of logic.", "indicator": "Apply boolean expressions.",
         "topics": "Boolean expressions", "start_page": 2, "end_page": 2},
    ])])

    result = await curriculum_unit_extraction._run(db_session, material.id, uuid.uuid4())
    assert result["status"] == "done"
    assert result["units_extracted"] == 2

    await db_session.refresh(material)
    assert material.unit_extraction_status == ExtractionStatus.DONE

    units = list(await db_session.scalars(
        select(CurriculumUnit).where(CurriculumUnit.material_id == material.id).order_by(CurriculumUnit.sequence_number)
    ))
    assert [u.sequence_number for u in units] == [1, 2]
    assert units[0].unit_label == "Week 1"
    assert units[1].unit_label == "Week 2"
    assert units[0].strand == "Computer Architecture"


@pytest.mark.asyncio
async def test_extraction_collapses_mid_batch_boundary_unit(
    db_session: AsyncSession, school: School, material: CurriculumMaterial, monkeypatch,
):
    """Force two separate batches (page-count cap = 15, so 16 one-page
    chunks split into two calls) — the second batch's first unit claims
    starts_mid_batch, which must merge into the first batch's last unit
    instead of becoming a third row."""
    await _with_ai_config(db_session, school)
    for i in range(1, 17):
        await _add_chunk(db_session, school, material, i, f"Page {i} content.")

    batch1 = _batch_json([
        {"unit_label": "Week 1", "topics": "Intro", "start_page": 1, "end_page": 15},
    ])
    batch2 = _batch_json([
        {"unit_label": None, "topics": "continued discussion", "start_page": 16, "end_page": 16, "starts_mid_batch": True},
    ])
    _patch_sequence(monkeypatch, [batch1, batch2])

    result = await curriculum_unit_extraction._run(db_session, material.id, uuid.uuid4())
    assert result["status"] == "done"
    assert result["units_extracted"] == 1  # collapsed, not 2

    unit = await db_session.scalar(select(CurriculumUnit).where(CurriculumUnit.material_id == material.id))
    assert unit.unit_label == "Week 1"  # kept from the first batch, not overwritten by the mid-batch unit's None
    assert unit.source_page_end == 16  # extended to cover the merged content
    assert "continued discussion" in unit.topics


@pytest.mark.asyncio
async def test_extraction_empty_when_zero_units_returned(
    db_session: AsyncSession, school: School, material: CurriculumMaterial, monkeypatch,
):
    await _with_ai_config(db_session, school)
    await _add_chunk(db_session, school, material, 1, "Some page text.")
    _patch_sequence(monkeypatch, [_batch_json([])])

    result = await curriculum_unit_extraction._run(db_session, material.id, uuid.uuid4())
    assert result["status"] == "empty"
    await db_session.refresh(material)
    assert material.unit_extraction_status == ExtractionStatus.EMPTY
    assert material.unit_extraction_error is not None


@pytest.mark.asyncio
async def test_extraction_no_chunks_is_empty(
    db_session: AsyncSession, school: School, material: CurriculumMaterial,
):
    result = await curriculum_unit_extraction._run(db_session, material.id, uuid.uuid4())
    assert result["status"] == "empty"
    assert result["units_extracted"] == 0


@pytest.mark.asyncio
async def test_extraction_partial_failure_keeps_earlier_batches(
    db_session: AsyncSession, school: School, material: CurriculumMaterial, monkeypatch,
):
    """The second batch's response can't be parsed as valid JSON even after
    generate_json's own retry — the first batch's real unit must still be
    persisted, and the material flagged FAILED (not EMPTY, since something
    real was extracted) naming the gap."""
    await _with_ai_config(db_session, school)
    for i in range(1, 17):
        await _add_chunk(db_session, school, material, i, f"Page {i} content.")

    batch1 = _batch_json([{"unit_label": "Week 1", "start_page": 1, "end_page": 15}])
    # generate_json retries once on bad JSON, so the stub must return two
    # bad responses for the second batch's call to actually exhaust it.
    _patch_sequence(monkeypatch, [batch1, "not json", "still not json"])

    result = await curriculum_unit_extraction._run(db_session, material.id, uuid.uuid4())
    assert result["status"] == "failed"
    assert result["units_extracted"] == 1

    await db_session.refresh(material)
    assert material.unit_extraction_status == ExtractionStatus.FAILED
    assert "page 16" in material.unit_extraction_error

    units = list(await db_session.scalars(select(CurriculumUnit).where(CurriculumUnit.material_id == material.id)))
    assert len(units) == 1
    assert units[0].unit_label == "Week 1"


@pytest.mark.asyncio
async def test_extraction_no_ai_provider_fails_cleanly(
    db_session: AsyncSession, school: School, material: CurriculumMaterial,
):
    await _add_chunk(db_session, school, material, 1, "Some page text.")
    result = await curriculum_unit_extraction._run(db_session, material.id, uuid.uuid4())
    assert result["status"] == "failed"
    await db_session.refresh(material)
    assert material.unit_extraction_status == ExtractionStatus.FAILED
