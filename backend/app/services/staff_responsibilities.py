"""Staff responsibilities — class teacher, subject, and house assignments."""
from __future__ import annotations
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import (
    AcademicYear, Class, ClassTeacher,
    SHSProgramme, Subject, SubjectTeacher,
)
from app.models.housing import House, HouseMaster
from app.schemas.staff import (
    ClassTeacherAssignment, HouseAssignment,
    StaffResponsibilities, SubjectAssignment,
)


def _class_name(level: str, year_group: int, programme_name: str | None, stream: str | None) -> str:
    if level.upper() == "SHS":
        parts = [str(year_group)]
        if programme_name:
            parts.append(programme_name)
    else:
        parts = [level, str(year_group)]
    if stream:
        parts.append(stream)
    return " ".join(parts)


async def get_responsibilities(
    staff_id: uuid.UUID,
    school_id: uuid.UUID,
    db: AsyncSession,
) -> StaffResponsibilities:
    # This tab shows what a staff member CURRENTLY does, not a full audit
    # history — every branch below filters to is_active rows only. Without
    # this, a removed or reassigned responsibility (services/housing.py::
    # assign_house_master deactivates the old row rather than deleting it,
    # same pattern for class/subject teacher) stays visible forever: the
    # same house showing twice (once active, once as dead history) after a
    # reassignment is exactly the bug this fixes, not a display quirk.
    ct_rows = (await db.execute(
        select(ClassTeacher, Class, AcademicYear, SHSProgramme)
        .join(Class, ClassTeacher.class_id == Class.id)
        .join(AcademicYear, ClassTeacher.academic_year_id == AcademicYear.id)
        .outerjoin(SHSProgramme, Class.programme_id == SHSProgramme.id)
        .where(
            ClassTeacher.staff_member_id == staff_id,
            ClassTeacher.school_id == school_id,
            ClassTeacher.is_active.is_(True),
        )
        .order_by(AcademicYear.start_date.desc())
    )).all()

    class_teacher: ClassTeacherAssignment | None = None
    if ct_rows:
        ct, cls, year, prog = ct_rows[0]
        class_teacher = ClassTeacherAssignment(
            class_id=ct.class_id,
            class_name=_class_name(cls.level, cls.year_group, prog.name if prog else None, cls.stream),
            academic_year_id=ct.academic_year_id,
            academic_year_name=year.name,
            is_active=ct.is_active,
        )

    # ── Subject assignments ───────────────────────────────────────────────────
    st_rows = (await db.execute(
        select(SubjectTeacher, Class, Subject, AcademicYear, SHSProgramme)
        .join(Class, SubjectTeacher.class_id == Class.id)
        .join(Subject, SubjectTeacher.subject_id == Subject.id)
        .join(AcademicYear, SubjectTeacher.academic_year_id == AcademicYear.id)
        .outerjoin(SHSProgramme, Class.programme_id == SHSProgramme.id)
        .where(
            SubjectTeacher.staff_member_id == staff_id,
            SubjectTeacher.school_id == school_id,
            SubjectTeacher.is_active.is_(True),
        )
        .order_by(AcademicYear.start_date.desc(), Class.year_group)
    )).all()

    subject_assignments = [
        SubjectAssignment(
            class_id=st.class_id,
            class_name=_class_name(cls.level, cls.year_group, prog.name if prog else None, cls.stream),
            subject_id=st.subject_id,
            subject_name=subj.name,
            academic_year_id=st.academic_year_id,
            academic_year_name=year.name,
            is_active=st.is_active,
        )
        for st, cls, subj, year, prog in st_rows
    ]

    # ── House master assignments ──────────────────────────────────────────────
    hm_rows = (await db.execute(
        select(HouseMaster, House, AcademicYear)
        .join(House, HouseMaster.house_id == House.id)
        .join(AcademicYear, HouseMaster.academic_year_id == AcademicYear.id)
        .where(
            HouseMaster.staff_member_id == staff_id,
            HouseMaster.school_id == school_id,
            HouseMaster.is_active.is_(True),
        )
        .order_by(AcademicYear.start_date.desc())
    )).all()

    house_assignments = [
        HouseAssignment(
            house_id=hm.house_id,
            house_name=house.name,
            house_code=house.code,
            academic_year_id=hm.academic_year_id,
            academic_year_name=year.name,
            is_active=hm.is_active,
        )
        for hm, house, year in hm_rows
    ]

    return StaffResponsibilities(
        class_teacher=class_teacher,
        subject_assignments=subject_assignments,
        house_assignments=house_assignments,
    )
