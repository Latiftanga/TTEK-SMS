from __future__ import annotations
import uuid

from pydantic import BaseModel, Field

# ── LLM-facing shapes only (never returned directly to the client) ─────────
# Per-batch structured extraction — see services/curriculum_unit_extraction.py.
# Deliberately generic: the model names whatever teaching-time subdivision
# the source document actually uses (or infers boundaries from topic changes
# if there's no label at all), never a hardcoded "WEEK X" pattern match.


class ExtractedTeachingUnit(BaseModel):
    unit_label: str | None = None
    strand: str | None = None
    sub_strand: str | None = None
    content_standard: str | None = None
    indicator: str | None = None
    learning_objectives: str | None = None
    topics: str | None = None
    start_page: int
    end_page: int
    # True only for a batch's first unit, when its content clearly continues
    # from before this batch's first page — the merge step uses this to
    # collapse it into the previous batch's last unit instead of appending
    # a duplicate row.
    starts_mid_batch: bool = False


class ExtractedUnitBatch(BaseModel):
    units: list[ExtractedTeachingUnit] = Field(default_factory=list)


# ── API-facing shapes ────────────────────────────────────────────────────────

class CurriculumUnitRead(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    material_id: uuid.UUID
    sequence_number: int
    unit_label: str | None
    strand: str | None
    sub_strand: str | None
    content_standard: str | None
    indicator: str | None
    learning_objectives: str | None
    topics: str | None
    source_page_start: int
    source_page_end: int
    model_config = {"from_attributes": True}


class CurriculumUnitUpdate(BaseModel):
    """Manual correction of a bad extraction — every field optional, only
    what's provided is changed. No re-run of the extraction job needed."""
    unit_label: str | None = Field(default=None, max_length=100)
    strand: str | None = None
    sub_strand: str | None = None
    content_standard: str | None = None
    indicator: str | None = None
    learning_objectives: str | None = None
    topics: str | None = None
