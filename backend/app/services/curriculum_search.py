"""
Full-text retrieval over CurriculumMaterialChunk — grounds the AI lesson-
planning chat/generation prompts in a school's real uploaded curriculum
text. Postgres built-in tsvector/ts_rank, not embeddings/pgvector — a
deliberate scoping decision (see the plan this was built from): no new
Docker image, no per-page embedding API cost, good enough for how a
curriculum topic is normally phrased.
"""
from __future__ import annotations
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum_materials import CurriculumMaterial, CurriculumMaterialChunk
from app.schemas.curriculum_materials import CurriculumChunkResult


async def search_curriculum(
    class_subject_id: uuid.UUID, query_text: str, school_id: uuid.UUID, db: AsyncSession, *, limit: int = 5,
) -> list[CurriculumChunkResult]:
    if not query_text.strip():
        return []

    query = func.plainto_tsquery("english", query_text)
    rank = func.ts_rank(CurriculumMaterialChunk.search_vector, query).label("rank")

    rows = (await db.execute(
        select(
            CurriculumMaterialChunk.material_id, CurriculumMaterialChunk.page_number,
            CurriculumMaterialChunk.chunk_text, CurriculumMaterial.document_type,
            CurriculumMaterial.file_name, rank,
        )
        .join(CurriculumMaterial, CurriculumMaterial.id == CurriculumMaterialChunk.material_id)
        .where(
            CurriculumMaterial.class_subject_id == class_subject_id,
            CurriculumMaterial.school_id == school_id,
            CurriculumMaterialChunk.search_vector.op("@@")(query),
        )
        .order_by(rank.desc())
        .limit(limit)
    )).all()

    return [
        CurriculumChunkResult(
            material_id=material_id, document_type=document_type, file_name=file_name,
            page_number=page_number, chunk_text=chunk_text,
        )
        for material_id, page_number, chunk_text, document_type, file_name, _rank in rows
    ]
