"""
Programme-level summary — "how many classes run General Science, how many
students total" — aggregated across every class in the school with that
programme, mirroring services/subject_summary.py's shape but simpler: a
programme has no teacher-assignment or student-registration concept of its
own (Class.programme_id is the only link, no join table), and
StudentClassAssignment is year-scoped, not term-scoped, so this keys off
academic_year_id rather than a term. Read-only — editing a class's
programme still only happens on the class detail page.
"""
from __future__ import annotations
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import Class, SHSProgramme
from app.models.students import Student, StudentClassAssignment
from app.schemas.academic import ProgrammeClassSummary, ProgrammeSummary


async def get_programme_summary(
    programme_id: uuid.UUID,
    academic_year_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> ProgrammeSummary:
    # Class.programme_id can only ever point to the calling school's own
    # adopted SHSProgramme row (create_class/update_class both enforce
    # SHSProgramme.school_id == school_id at write time) — never the shared
    # catalogue row directly, so a plain school-scoped match is correct and
    # naturally 404s for a catalogue id this school never adopted.
    programme = await db.scalar(
        select(SHSProgramme).where(SHSProgramme.id == programme_id, SHSProgramme.school_id == school_id)
    )
    if not programme:
        raise HTTPException(status_code=404, detail="Programme not found.")

    class_rows = (await db.scalars(
        select(Class)
        .where(Class.programme_id == programme_id, Class.school_id == school_id)
        .order_by(Class.year_group, Class.stream)
    )).all()
    if not class_rows:
        return ProgrammeSummary(
            programme_id=programme.id, programme_name=programme.name,
            total_classes=0, total_students=0, classes=[],
        )
    class_ids = [c.id for c in class_rows]

    count_by_class: dict[uuid.UUID, int] = dict((await db.execute(
        select(StudentClassAssignment.class_id, func.count(StudentClassAssignment.id))
        .join(Student, Student.id == StudentClassAssignment.student_id)
        .where(
            StudentClassAssignment.class_id.in_(class_ids),
            StudentClassAssignment.academic_year_id == academic_year_id,
            StudentClassAssignment.school_id == school_id,
            StudentClassAssignment.is_active.is_(True),
            Student.is_active.is_(True),
        )
        .group_by(StudentClassAssignment.class_id)
    )).all())

    classes = [
        ProgrammeClassSummary(
            class_id=c.id,
            # The programme name is constant across every row here (it's the
            # query filter) — reusing _class_display_name verbatim would just
            # repeat "General Science" on every line. But a bare year_group
            # digit ("1") reads as ambiguous right under a "N classes" count —
            # easily misread as another number, not a label — so it still
            # needs a "Year" prefix to stand alone clearly.
            display_name=f"Year {c.year_group}" + (f" · {c.stream}" if c.stream else ""),
            student_count=count_by_class.get(c.id, 0),
        )
        for c in class_rows
    ]
    return ProgrammeSummary(
        programme_id=programme.id,
        programme_name=programme.name,
        total_classes=len(classes),
        total_students=sum(cl.student_count for cl in classes),
        classes=classes,
    )
