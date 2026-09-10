"""
Curriculum units — structured, machine-extracted teaching-time subdivisions
(whatever a document calls them: Week/Unit/Module/Lesson, or nothing at all)
pulled from an uploaded CurriculumMaterial, so a teacher never has to retype
a real curriculum's strand/sub-strand/content-standard/indicator by hand.

Deliberately NOT the same table as CurriculumStandard (models/lesson_plans.py)
— that's a manually-curated, short-code GES catalogue; this is machine-
extracted from one specific uploaded document, ordered by our own
sequence_number (not anything the source document numbers itself), and
carries a source-page citation for trust/audit. Both are independent,
optional autofill sources for the same LessonPlan fields — see
services/lesson_plans.py::_resolve_curriculum_unit / _resolve_curriculum_standard.

No automatic mapping from sequence_number to a real calendar week exists,
deliberately: real school pacing drifts too easily (holidays, a rescheduled
lesson, a slow start) for a silent date-based guess to be trustworthy — the
teacher picks the matching unit themselves from a short list instead. See
services/curriculum_unit_extraction.py for how these rows are produced (a
map-reduce AI extraction over the material's page-text chunks, not regex/
heading matching, so it generalizes across differently organized documents).
"""
from __future__ import annotations
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, SchoolScopedMixin, TimestampMixin, UUIDPrimaryKey


class CurriculumUnit(Base, UUIDPrimaryKey, TimestampMixin, SchoolScopedMixin):
    __tablename__ = "curriculum_unit"
    __table_args__ = (
        UniqueConstraint("material_id", "sequence_number", name="uq_curriculum_unit_material_sequence"),
    )

    material_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("curriculum_material.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    # Our own 1..N ordinal over the merged extraction result — display order
    # only, decoupled from whatever (if anything) the source document numbers.
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Verbatim from the source, e.g. "Week 3", "Unit 2" — None if the
    # document has no detectable label for this unit at all.
    unit_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    strand: Mapped[str | None] = mapped_column(Text, nullable=True)
    sub_strand: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_standard: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Full sentence OR a short code — Text, no length assumption either way
    # (unlike CurriculumStandard.indicator_code's String(50), sized only for
    # GES Basic-style short codes).
    indicator: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning_objectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The unit's own specific lesson content ("Focal Area" in a GES manual) —
    # surfaced to the frontend as a suggested LessonPlan.topic, not stored
    # as a LessonPlan column of its own.
    topics: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    source_page_end: Mapped[int] = mapped_column(Integer, nullable=False)
