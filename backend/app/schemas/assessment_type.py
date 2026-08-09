from __future__ import annotations
import uuid
from decimal import Decimal

from pydantic import BaseModel, field_validator, model_validator

from app.models.assessments import AggregationStrategy, AssessmentCategory


class AssessmentTypeCreate(BaseModel):
    name: str
    code: str
    weight: Decimal
    category: AssessmentCategory = AssessmentCategory.FORMATIVE
    allow_multiple_entries: bool = True
    aggregation_strategy: AggregationStrategy = AggregationStrategy.SUM_NORMALIZE

    @field_validator("weight")
    @classmethod
    def weight_range(cls, v: Decimal) -> Decimal:
        if v <= 0 or v > 100:
            raise ValueError("weight must be between 0.01 and 100")
        return v

    @model_validator(mode="after")
    def strategy_matches_multiplicity(self) -> "AssessmentTypeCreate":
        _check_strategy_matches_multiplicity(self.allow_multiple_entries, self.aggregation_strategy)
        return self


class AssessmentTypeUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    weight: Decimal | None = None
    category: AssessmentCategory | None = None
    allow_multiple_entries: bool | None = None
    aggregation_strategy: AggregationStrategy | None = None

    @field_validator("weight")
    @classmethod
    def weight_range(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and (v <= 0 or v > 100):
            raise ValueError("weight must be between 0.01 and 100")
        return v

    @model_validator(mode="after")
    def strategy_matches_multiplicity(self) -> "AssessmentTypeUpdate":
        # Only meaningful when both fields are present in the same request —
        # a partial update touching just one of the two is checked against
        # the existing row's other value at the service layer instead, since
        # this schema alone can't see what's already stored.
        if self.allow_multiple_entries is not None and self.aggregation_strategy is not None:
            _check_strategy_matches_multiplicity(self.allow_multiple_entries, self.aggregation_strategy)
        return self


def _check_strategy_matches_multiplicity(allow_multiple: bool, strategy: AggregationStrategy) -> None:
    if not allow_multiple and strategy != AggregationStrategy.NONE:
        raise ValueError("aggregation_strategy must be NONE when allow_multiple_entries is False")
    if allow_multiple and strategy == AggregationStrategy.NONE:
        raise ValueError("aggregation_strategy must not be NONE when allow_multiple_entries is True")


class AssessmentTypeRead(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    weight: Decimal
    category: AssessmentCategory
    allow_multiple_entries: bool
    aggregation_strategy: AggregationStrategy
    is_active: bool
    model_config = {"from_attributes": True}
