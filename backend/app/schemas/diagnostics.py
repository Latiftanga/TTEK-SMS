from __future__ import annotations
import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class DiagnosticRecordRead(BaseModel):
    """One approved score against a category=DIAGNOSTIC assessment — see
    services/diagnostics.py. Deliberately has no letter grade: diagnostics
    were never meant to be graded like coursework, they're a raw record of
    what was found."""
    id: uuid.UUID
    assessment_name: str
    subject_name: str
    recorded_date: date
    raw_score: Decimal
    max_score: Decimal
    notes: str | None
