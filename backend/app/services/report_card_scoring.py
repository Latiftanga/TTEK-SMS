"""
Weighted score aggregation — shared by report_card.py (a student's own
subject totals) and report_card_rank.py (every student's totals, for class
ranking). Split out when report_card.py went over the 300-line cap.
"""
from __future__ import annotations
from decimal import Decimal

from app.models.assessments import AggregationStrategy
from app.services.aggregation import resolve_type_score


def _compute_weighted_scores(scores: list[dict]) -> dict[str, Decimal]:
    """
    For each subject, compute the weighted score out of 100.

    Per type: each type's recorded entries are first resolved down to one
    0-100 percentage via services/aggregation.py::resolve_type_score(), using
    that type's own configured aggregation_strategy (SUM_NORMALIZE for every
    pre-existing AssessmentType, by migration — see
    alembic/versions/f8a9b0c1d2e3_*.py — so this is behavior-identical to the
    old "always sum" math for existing data). contribution = resolved_pct *
    type_weight. Subject total = sum of contributions across all types.

    If weights don't sum to 100 the total is proportional — callers display
    whatever the school configured. Diagnostic-category rows never reach this
    function at all (excluded at the query level, see report_card.py::
    _load_scores) — nothing here needs to re-check category.
    """
    # Group by subject → type
    subjects: dict[str, dict[str, dict]] = {}
    for row in scores:
        subj = row["subject_name"]
        typ  = row["type_name"]
        if subj not in subjects:
            subjects[subj] = {}
        if typ not in subjects[subj]:
            subjects[subj][typ] = {
                "weight": Decimal(str(row["type_weight"])),
                "strategy": AggregationStrategy(row["type_aggregation_strategy"]),
                "raw_scores": [],
                "max_scores": [],
            }
        subjects[subj][typ]["raw_scores"].append(Decimal(str(row["raw_score"])))
        subjects[subj][typ]["max_scores"].append(Decimal(str(row["max_score"])))

    result: dict[str, Decimal] = {}
    for subj, types in subjects.items():
        total = Decimal("0")
        for t in types.values():
            pct = resolve_type_score(t["raw_scores"], t["max_scores"], t["strategy"])
            if pct is not None:
                total += (pct / 100) * t["weight"]
        result[subj] = total.quantize(Decimal("0.01"))
    return result
