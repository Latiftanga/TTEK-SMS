"""
Static assessment-type presets — a convenience pre-fill layer only, exactly
per the aggregation engine's own non-goal: "no hardcoded exam-board numbers,
no special-cased code paths." A preset is just a list of AssessmentTypeCreate-
shaped values a school can review, edit, and adopt via the normal
POST /assessments/types — the engine has no notion afterward that a type
"came from" a preset; nothing anywhere branches on which preset (if any) was
used, mirroring the same convention already used for the SMTP host/port
quick-fill presets on the Email setup tab (frontend/EmailTab.svelte).
"""
from __future__ import annotations

from app.models.assessments import AggregationStrategy, AssessmentCategory

TYPE_PRESETS: dict[str, list[dict]] = {
    "waec_ges_shs": [
        {
            "name": "Class Assessment",
            "code": "CAT",
            "weight": "30",
            "category": AssessmentCategory.FORMATIVE,
            "allow_multiple_entries": True,
            "aggregation_strategy": AggregationStrategy.AVERAGE,
        },
        {
            "name": "End of Term Exam",
            "code": "EXAM",
            "weight": "70",
            "category": AssessmentCategory.SUMMATIVE,
            "allow_multiple_entries": False,
            "aggregation_strategy": AggregationStrategy.NONE,
        },
    ],
}
