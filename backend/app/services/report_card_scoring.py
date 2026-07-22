"""
Weighted score aggregation — shared by report_card.py (a student's own
subject totals) and report_card_rank.py (every student's totals, for class
ranking). Split out when report_card.py went over the 300-line cap.
"""
from __future__ import annotations
from decimal import Decimal


def _compute_weighted_scores(scores: list[dict]) -> dict[str, Decimal]:
    """
    For each subject, compute the weighted score out of 100.

    Per type: contribution = (sum_raw / sum_max) * type_weight
    Subject total = sum of contributions across all types.

    If weights don't sum to 100 the total is proportional — callers display
    whatever the school configured.
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
                "sum_raw": Decimal("0"),
                "sum_max": Decimal("0"),
            }
        subjects[subj][typ]["sum_raw"] += Decimal(str(row["raw_score"]))
        subjects[subj][typ]["sum_max"] += Decimal(str(row["max_score"]))

    result: dict[str, Decimal] = {}
    for subj, types in subjects.items():
        total = Decimal("0")
        for t in types.values():
            if t["sum_max"] > 0:
                total += (t["sum_raw"] / t["sum_max"]) * t["weight"]
        result[subj] = total.quantize(Decimal("0.01"))
    return result
