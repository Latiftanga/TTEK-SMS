"""
Weighted score aggregation — shared by report_card.py (a student's own
subject totals) and report_card_rank.py (every student's totals, for class
ranking). Split out when report_card.py went over the 300-line cap.
"""
from __future__ import annotations
from decimal import Decimal

from app.models.assessments import AggregationStrategy
from app.services.aggregation import resolve_type_score


def _group_scores_by_subject_type(scores: list[dict]) -> dict[str, dict[str, dict]]:
    """Group raw score rows by subject → assessment-type code, ready for
    resolve_type_score(). Shared by _compute_weighted_scores (the term total)
    and _compute_type_breakdown (report_card.py's per-type column values) so
    the two can never drift apart on what counts as "this type's entries"."""
    subjects: dict[str, dict[str, dict]] = {}
    for row in scores:
        subj = row["subject_name"]
        typ  = row["type_code"]
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
    return subjects


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
    subjects = _group_scores_by_subject_type(scores)
    result: dict[str, Decimal] = {}
    for subj, types in subjects.items():
        total = Decimal("0")
        for t in types.values():
            pct = resolve_type_score(t["raw_scores"], t["max_scores"], t["strategy"])
            if pct is not None:
                total += (pct / 100) * t["weight"]
        result[subj] = total.quantize(Decimal("0.01"))
    return result


def _compute_type_breakdown(scores: list[dict]) -> dict[str, dict[str, Decimal]]:
    """Per subject, per assessment-type-code weighted contribution — the
    value report_card.py's unified subject table shows in each type column.

    Deliberately the contribution (resolved_pct / 100 * type_weight), not the
    raw resolved percentage: a bare "%" per category read as confusing to
    parents, since it doesn't visibly relate to the subject Total shown next
    to it (90% and 76% don't obviously sum to a weighted 80.20). Contribution
    values do — CT's 27.0 + EOT's 53.2 literally add up to the Total's 80.20
    — the same arithmetic _compute_weighted_scores already performs, just
    kept per-type here instead of only returning the sum. Quantized to 1dp:
    plenty of precision for "points toward this subject's 100," without the
    2dp noise the underlying percentage math would otherwise show."""
    subjects = _group_scores_by_subject_type(scores)
    result: dict[str, dict[str, Decimal]] = {}
    for subj, types in subjects.items():
        contributions: dict[str, Decimal] = {}
        for typ, t in types.items():
            pct = resolve_type_score(t["raw_scores"], t["max_scores"], t["strategy"])
            if pct is not None:
                contributions[typ] = ((pct / 100) * t["weight"]).quantize(Decimal("0.1"))
        result[subj] = contributions
    return result
