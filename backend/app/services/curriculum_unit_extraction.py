"""
ARQ job: extract_curriculum_units

Second, independent pipeline stage from extract_curriculum_material (page-
text extraction) — a map-reduce AI extraction over the material's already-
extracted CurriculumMaterialChunk rows, producing structured CurriculumUnit
rows (strand/sub-strand/content-standard/indicator per teaching-time
subdivision). Deliberately NOT regex/heading-pattern matching (no "WEEK X"
string search) — the model is asked to find whatever subdivision the source
document actually uses, so this generalizes across differently organized
curricula/schools/subjects (see the plan this was built from).

Admin-triggered (POST /curriculum-materials/{id}/extract-units), not
auto-chained after upload: a 100+ page document can cost 10-30 sequential
AI calls, and many schools share the platform's daily AI budget — this
should be a conscious action, not a surprise side effect of every upload.

A large document is batched into several sequential AI calls (page-count AND
char-count bounded, since generate_json() has no token counting). Each
batch's units are merged into one ordered list, collapsing a batch-boundary-
spanning unit into the previous batch's last entry rather than duplicating
it. A batch failure keeps whatever earlier batches already produced —
partial coverage is more useful than none, and the admin-facing error names
exactly which pages are missing.

Mirrors services/curriculum_extraction.py's ARQ-entrypoint/_run() split.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum_materials import CurriculumMaterial, CurriculumMaterialChunk, ExtractionStatus
from app.models.curriculum_units import CurriculumUnit
from app.schemas.curriculum_units import ExtractedTeachingUnit, ExtractedUnitBatch
from app.services import ai_config
from app.services.ai_driver import generate_json

_MAX_BATCH_PAGES = 15
_MAX_BATCH_CHARS = 12_000

_SYSTEM_GUARDRAILS = (
    "You are analyzing a real school curriculum/teacher-manual document to "
    "identify its teaching-time structure. Find whatever unit the document "
    "actually uses to organize weekly/periodic teaching content — it might "
    "be called a Week, Unit, Module, Lesson, or have no explicit label at "
    "all (in which case infer boundaries from clear topic changes). For "
    "each unit, extract only what the text actually states — never invent "
    "a strand, sub-strand, content standard, or indicator that isn't "
    "present. If a strand/sub-strand/content-standard is stated once for a "
    "group of units (e.g. at the start of a section covering several "
    "weeks), repeat it on every one of those smaller units individually — "
    "never emit it once for the whole group. If a unit's content plainly "
    "continues from text you were not shown (i.e. it started before the "
    "excerpt below begins), mark it starts_mid_batch=true."
)


class _Batch:
    __slots__ = ("start_page", "end_page", "text")

    def __init__(self, start_page: int, end_page: int, text: str) -> None:
        self.start_page = start_page
        self.end_page = end_page
        self.text = text


def _flush_batch(pages: list[tuple[int, str]]) -> _Batch:
    text = "\n\n".join(f"[Page {n}]\n{t}" for n, t in pages)
    return _Batch(start_page=pages[0][0], end_page=pages[-1][0], text=text)


def _build_batches(chunks: list[CurriculumMaterialChunk]) -> list[_Batch]:
    batches: list[_Batch] = []
    cur_pages: list[tuple[int, str]] = []
    cur_chars = 0
    for c in chunks:
        piece_len = len(c.chunk_text)
        would_exceed = cur_pages and (
            len(cur_pages) >= _MAX_BATCH_PAGES or cur_chars + piece_len > _MAX_BATCH_CHARS
        )
        if would_exceed:
            batches.append(_flush_batch(cur_pages))
            cur_pages, cur_chars = [], 0
        cur_pages.append((c.page_number, c.chunk_text))
        cur_chars += piece_len
    if cur_pages:
        batches.append(_flush_batch(cur_pages))
    return batches


def _merge(existing: list[ExtractedTeachingUnit], new_units: list[ExtractedTeachingUnit]) -> None:
    """Appends new_units onto existing in place, collapsing a leading
    starts_mid_batch unit into existing's last entry instead of appending a
    duplicate row."""
    for i, u in enumerate(new_units):
        if i == 0 and u.starts_mid_batch and existing:
            prev = existing[-1]
            existing[-1] = prev.model_copy(update={
                "end_page": u.end_page,
                "topics": "\n".join(x for x in (prev.topics, u.topics) if x) or None,
                "learning_objectives": "\n".join(x for x in (prev.learning_objectives, u.learning_objectives) if x) or None,
                "strand": prev.strand or u.strand,
                "sub_strand": prev.sub_strand or u.sub_strand,
                "content_standard": prev.content_standard or u.content_standard,
                "indicator": prev.indicator or u.indicator,
                "unit_label": prev.unit_label or u.unit_label,
            })
        else:
            existing.append(u)


async def extract_curriculum_units(ctx: dict, material_id: str, triggered_by_user_id: str) -> dict:
    """ARQ job — runs in the worker process."""
    AsyncSessionLocal = ctx["db"]
    async with AsyncSessionLocal() as db:
        result = await _run(db, uuid.UUID(material_id), uuid.UUID(triggered_by_user_id))
        await db.commit()
        return result


async def _run(db: AsyncSession, material_id: uuid.UUID, triggered_by_user_id: uuid.UUID) -> dict:
    mat = await db.get(CurriculumMaterial, material_id)
    if not mat:
        return {"material_id": str(material_id), "status": "not_found", "units_extracted": 0}

    chunks = list(await db.scalars(
        select(CurriculumMaterialChunk)
        .where(CurriculumMaterialChunk.material_id == material_id)
        .order_by(CurriculumMaterialChunk.page_number)
    ))
    if not chunks:
        mat.unit_extraction_status = ExtractionStatus.EMPTY
        mat.unit_extraction_error = "No extracted page text to work from — run text extraction first."
        await db.flush()
        return {"material_id": str(material_id), "status": "empty", "units_extracted": 0}

    try:
        driver, cfg = await ai_config.resolve_driver_for_generation(mat.school_id, db)
    except Exception as exc:
        mat.unit_extraction_status = ExtractionStatus.FAILED
        mat.unit_extraction_error = f"No AI provider available: {exc}"
        await db.flush()
        return {"material_id": str(material_id), "status": "failed", "units_extracted": 0}

    batches = _build_batches(chunks)
    merged: list[ExtractedTeachingUnit] = []
    failed_at_page: int | None = None
    quota_error: str | None = None
    for batch in batches:
        try:
            await ai_config.check_daily_limit(mat.school_id, triggered_by_user_id, cfg, db)
        except HTTPException as exc:
            failed_at_page = batch.start_page
            quota_error = str(exc.detail)
            break
        try:
            prompt = (
                f"Curriculum document excerpt, pages {batch.start_page}-{batch.end_page}:\n\n{batch.text}\n\n"
                "Extract every teaching unit found in this excerpt."
            )
            result = await generate_json(driver, prompt, _SYSTEM_GUARDRAILS, ExtractedUnitBatch)
            await ai_config.increment_usage(mat.school_id, triggered_by_user_id, cfg)
        except Exception:
            failed_at_page = batch.start_page
            break
        _merge(merged, result.units)

    # Clear any prior units first — a re-run must not accumulate stale rows.
    await db.execute(delete(CurriculumUnit).where(CurriculumUnit.material_id == material_id))
    for i, u in enumerate(merged):
        db.add(CurriculumUnit(
            school_id=mat.school_id, material_id=mat.id, sequence_number=i + 1,
            unit_label=u.unit_label, strand=u.strand, sub_strand=u.sub_strand,
            content_standard=u.content_standard, indicator=u.indicator,
            learning_objectives=u.learning_objectives, topics=u.topics,
            source_page_start=u.start_page, source_page_end=u.end_page,
        ))
    await db.flush()

    if failed_at_page is not None:
        last_page = merged[-1].end_page if merged else 0
        mat.unit_extraction_status = ExtractionStatus.FAILED
        if quota_error is not None:
            mat.unit_extraction_error = (
                f"{quota_error} Extraction stopped at page {failed_at_page} "
                f"(covered through page {last_page}) — re-run to continue once the limit resets. "
                "Full-text search grounding is unaffected."
            )
        else:
            mat.unit_extraction_error = (
                f"Could not extract past page {failed_at_page} — pages {failed_at_page}-{chunks[-1].page_number} "
                f"have no extracted units (covered through page {last_page}). Full-text search grounding is unaffected."
            )
        await db.flush()
        return {"material_id": str(material_id), "status": "failed", "units_extracted": len(merged)}

    if not merged:
        mat.unit_extraction_status = ExtractionStatus.EMPTY
        mat.unit_extraction_error = "No structured teaching units could be identified in this document."
        await db.flush()
        return {"material_id": str(material_id), "status": "empty", "units_extracted": 0}

    mat.unit_extraction_status = ExtractionStatus.DONE
    mat.unit_extraction_error = None
    await db.flush()
    return {"material_id": str(material_id), "status": "done", "units_extracted": len(merged)}
