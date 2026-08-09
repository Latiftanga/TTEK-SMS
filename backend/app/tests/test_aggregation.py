"""
services/aggregation.py — pure unit tests, no DB. Run inside Docker:
docker compose exec api pytest app/tests/test_aggregation.py -v
"""
from decimal import Decimal

import pytest

from app.models.assessments import AggregationStrategy
from app.services.aggregation import resolve_type_score


def test_no_entries_returns_none():
    assert resolve_type_score([], [], AggregationStrategy.SUM_NORMALIZE) is None


def test_sum_normalize_matches_old_always_sum_math():
    """SUM_NORMALIZE must be byte-identical to the pre-aggregation-engine
    behavior: sum raw scores, sum max scores, normalize — this is the
    migration's own backfill default, so existing report cards can't change."""
    result = resolve_type_score(
        [Decimal("18"), Decimal("15")], [Decimal("20"), Decimal("20")], AggregationStrategy.SUM_NORMALIZE,
    )
    assert result == Decimal("82.50")  # (18+15)/(20+20) * 100


def test_best_of_takes_the_highest_percentage():
    result = resolve_type_score(
        [Decimal("12"), Decimal("18")], [Decimal("20"), Decimal("20")], AggregationStrategy.BEST_OF,
    )
    assert result == Decimal("90.00")  # 18/20, not 12/20


def test_average_takes_the_mean_percentage():
    result = resolve_type_score(
        [Decimal("10"), Decimal("20")], [Decimal("20"), Decimal("20")], AggregationStrategy.AVERAGE,
    )
    assert result == Decimal("75.00")  # mean(50%, 100%)


def test_none_strategy_passes_through_a_single_entry():
    result = resolve_type_score([Decimal("18")], [Decimal("20")], AggregationStrategy.NONE)
    assert result == Decimal("90.00")


def test_none_strategy_rejects_more_than_one_entry():
    """A type with allow_multiple_entries=False should never accumulate more
    than one Assessment row of that type (services/assessment.py::
    create_assessment enforces this at write time) — resolve_type_score
    raises rather than silently picking one, so a bug upstream fails loudly."""
    with pytest.raises(ValueError, match="expects exactly one"):
        resolve_type_score(
            [Decimal("18"), Decimal("15")], [Decimal("20"), Decimal("20")], AggregationStrategy.NONE,
        )


def test_zero_max_score_entries_excluded_from_best_of_and_average():
    result = resolve_type_score(
        [Decimal("10"), Decimal("5")], [Decimal("20"), Decimal("0")], AggregationStrategy.BEST_OF,
    )
    assert result == Decimal("50.00")


def test_all_zero_max_scores_returns_none_for_average():
    result = resolve_type_score(
        [Decimal("5")], [Decimal("0")], AggregationStrategy.AVERAGE,
    )
    assert result is None
