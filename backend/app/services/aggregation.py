"""
Assessment aggregation strategies.

Pure functions — no DB access — resolving one AssessmentType's recorded
entries down to a single 0-100 percentage score, per its configured
AggregationStrategy. This module's only job is that one resolution step;
turning the resolved percentage into a term grade (applying
AssessmentType.weight, summing across types) stays the existing job of
report_card_scoring.py::_compute_weighted_scores() — this is deliberately
not re-implemented here.

SUM_NORMALIZE is today's only behavior (services/report_card_scoring.py's
original math — sum raw scores, sum max scores, normalize — extracted
verbatim). Every existing AssessmentType row is migrated to this strategy
(see alembic/versions/f8a9b0c1d2e3_*.py) so existing report cards compute
byte-identical totals; BEST_OF/AVERAGE are new. MEDIAN/LOWEST are
deliberately not implemented (the spec marks them "not required for v1") —
resolve_type_score() raises rather than silently mis-computing if either is
ever requested.
"""
from __future__ import annotations
from decimal import Decimal

from app.models.assessments import AggregationStrategy


def _percentage(raw: Decimal, max_score: Decimal) -> Decimal:
    if not max_score or max_score <= 0:
        return Decimal("0")
    return ((raw / max_score) * 100).quantize(Decimal("0.01"))


def resolve_type_score(
    raw_scores: list[Decimal], max_scores: list[Decimal], strategy: AggregationStrategy,
) -> Decimal | None:
    """Collapse one AssessmentType's recorded entries — raw_scores/max_scores,
    same length, paired by index — into a single 0-100 percentage. Returns
    None if there are no entries to resolve (nothing recorded for this type
    yet); callers should treat that as "not shown," not zero."""
    if not raw_scores:
        return None

    if strategy == AggregationStrategy.NONE:
        if len(raw_scores) != 1:
            raise ValueError(
                f"aggregation_strategy=NONE expects exactly one recorded entry, got {len(raw_scores)}. "
                "A type with allow_multiple_entries=False should never accumulate more than one."
            )
        return _percentage(raw_scores[0], max_scores[0])

    if strategy == AggregationStrategy.SUM_NORMALIZE:
        sum_raw = sum(raw_scores, Decimal("0"))
        sum_max = sum(max_scores, Decimal("0"))
        return _percentage(sum_raw, sum_max)

    percentages = [_percentage(r, m) for r, m in zip(raw_scores, max_scores) if m and m > 0]
    if not percentages:
        return None

    if strategy == AggregationStrategy.BEST_OF:
        return max(percentages)

    if strategy == AggregationStrategy.AVERAGE:
        return (sum(percentages, Decimal("0")) / len(percentages)).quantize(Decimal("0.01"))

    raise ValueError(f"aggregation_strategy {strategy!r} is not supported yet.")
