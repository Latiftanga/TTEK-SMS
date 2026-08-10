"""
Read-only history of a student's diagnostic-category assessments —
category=DIAGNOSTIC scores are already fully excluded from term totals,
class rank, and the transcript (services/report_card.py, report_card_rank.py,
transcript.py), so this is the only place that history is visible at all.

No letter grade — diagnostics were never meant to be graded like coursework,
this is a raw record of what was found (assessment name, subject, date,
score, and the assessment's own description as free-text notes).

Only approved scores are included, matching the same convention every other
score-display surface in this codebase follows (report card, transcript,
rank). Not filtered on Assessment.is_published — that flag specifically
gates parent-portal visibility of term report cards, which doesn't apply to
this internal, staff-facing view.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.student_scope import assert_can_view_student
from app.models.academic import Subject
from app.models.assessments import Assessment, AssessmentCategory, AssessmentType, Score
from app.models.students import Student
from app.schemas.diagnostics import DiagnosticRecordRead


async def list_diagnostic_records(
    student_id: uuid.UUID, school_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> list[DiagnosticRecordRead]:
    student = await db.scalar(
        select(Student).where(Student.id == student_id, Student.school_id == school_id)
    )
    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found.")
    # Same "can this caller view this student" boundary as the rest of the
    # Students module (core/student_scope.py) — assessments.view alone (the
    # permission gating this route) doesn't imply cross-class visibility.
    await assert_can_view_student(user_id, student_id, school_id, db)

    rows = (await db.execute(
        select(
            Score.id,
            AssessmentType.name.label("assessment_name"),
            Subject.name.label("subject_name"),
            Assessment.recorded_date,
            Score.raw_score,
            Assessment.max_score,
            Assessment.description.label("notes"),
        )
        .join(Assessment, Assessment.id == Score.assessment_id)
        .join(AssessmentType, AssessmentType.id == Assessment.assessment_type_id)
        .join(Subject, Subject.id == Assessment.subject_id)
        .where(
            Score.student_id == student_id,
            Score.school_id == school_id,
            Score.is_approved.is_(True),
            AssessmentType.category == AssessmentCategory.DIAGNOSTIC,
        )
        .order_by(Assessment.recorded_date.desc())
    )).mappings().all()
    return [DiagnosticRecordRead(**r) for r in rows]
