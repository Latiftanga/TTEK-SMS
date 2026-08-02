"""
Student collection listing/search/sort/filter — split out of student.py
(was over the 300-line cap).
"""
from __future__ import annotations
import uuid

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import GraduationRecord, GraduationType
from app.models.academic import Class
from app.models.students import Student, TermEnrollment
from app.schemas.students import StudentSummary
from app.services.student import _to_summary
from app.services.student_display import _active_class_assignment_subquery, _get_class_map

# Pedagogical order — Class.level is a free-text column, not a DB-enforced enum,
# so plain alphabetical ORDER BY would put "Basic" before "Creche".
_CLASS_LEVEL_ORDER = ["Creche", "Nursery", "KG", "Basic", "SHS"]


async def list_students(
    school_id: uuid.UUID,
    db: AsyncSession,
    *,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 50,
    search: str | None = None,
    class_id: uuid.UUID | None = None,
    term_id: uuid.UUID | None = None,
    gender: str | None = None,
    level: str | None = None,
    year_group: int | None = None,
    scope: set[uuid.UUID] | None = None,
    graduated: bool | None = None,
    sort_by: str = "name",
    sort_dir: str = "asc",
) -> tuple[list[StudentSummary], int]:
    q = select(Student).where(Student.school_id == school_id)

    if graduated is not None:
        graduated_ids = select(GraduationRecord.student_id).where(
            GraduationRecord.school_id == school_id,
            GraduationRecord.graduation_type == GraduationType.GRADUATED,
        )
        # Lifetime check, not scoped to one academic year — a student graduated
        # in any past year should still surface under this filter.
        q = q.where(Student.id.in_(graduated_ids) if graduated else Student.id.not_in(graduated_ids))

    if scope is not None:
        # Restrict to students the caller is directly responsible for — see
        # core/student_scope.py::resolve_student_view_scope() for how `scope`
        # is computed (ClassTeacher/SubjectTeacher/HouseMaster assignment).
        q = q.where(Student.id.in_(scope))

    if active_only:
        q = q.where(Student.is_active == True)  # noqa: E712
    if gender:
        q = q.where(Student.gender == gender)

    # Class filter/sort share one dedup'd active-assignment join so a student with
    # 2+ active StudentClassAssignment rows (promoted, not graduated) can't fan out
    # the result — see student_display.py::_active_class_assignment_subquery().
    class_filtered = bool(class_id or level or year_group)
    class_sorted = sort_by == "class"
    active_sca = _active_class_assignment_subquery()
    if class_filtered:
        q = q.join(active_sca, active_sca.c.student_id == Student.id)
        if class_id:
            q = q.where(active_sca.c.class_id == class_id)
        if level or year_group or class_sorted:
            q = q.join(Class, Class.id == active_sca.c.class_id)
            if level:
                q = q.where(Class.level == level)
            if year_group:
                q = q.where(Class.year_group == year_group)
    elif class_sorted:
        # No class filter active — outer join so students with no current class
        # assignment still appear in an otherwise-unfiltered list.
        q = q.outerjoin(active_sca, active_sca.c.student_id == Student.id)
        q = q.outerjoin(Class, Class.id == active_sca.c.class_id)

    if term_id:
        q = q.join(TermEnrollment, TermEnrollment.student_id == Student.id).where(
            TermEnrollment.is_active == True,  # noqa: E712
            TermEnrollment.academic_term_id == term_id,
        )
    if search:
        s = f"%{search}%"
        q = q.where(or_(
            Student.first_name.ilike(s),
            Student.last_name.ilike(s),
            Student.admission_number.ilike(s),
        ))

    total = await db.scalar(select(func.count()).select_from(q.subquery()))

    desc = sort_dir == "desc"
    if sort_by == "admission":
        order_cols = [Student.admission_number.desc() if desc else Student.admission_number.asc()]
    elif sort_by == "class":
        level_rank = case(
            {lvl: i for i, lvl in enumerate(_CLASS_LEVEL_ORDER)},
            value=Class.level,
            else_=len(_CLASS_LEVEL_ORDER),
        )
        order_cols = [
            c.desc().nulls_last() if desc else c.asc().nulls_last()
            for c in (level_rank, Class.year_group, Class.stream)
        ]
    else:
        order_cols = (
            [Student.last_name.desc(), Student.first_name.desc()] if desc
            else [Student.last_name.asc(), Student.first_name.asc()]
        )
    order_cols.append(Student.id)  # deterministic tiebreaker — none of the above are unique keys

    q = q.order_by(*order_cols).offset(skip).limit(limit)
    students = list(await db.scalars(q))
    class_map = await _get_class_map([s.id for s in students], db)
    return [_to_summary(s, class_map.get(s.id)) for s in students], total
