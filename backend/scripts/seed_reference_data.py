"""
Seed reference data: GhanaRegion, GhanaDistrict, GhanaPublicHoliday,
StaffPosition templates with PositionPermission,
StaffCategory + StaffRank GES templates,
GES Standard Grading Scale (shared default — see resolve_grade()),
GES SHS Programmes + Subject Catalogue (shared defaults — school_id=NULL).

Data tables live in scripts/reference_data.py (kept separate to stay under
the 300-line cap here — this file is the seed() logic only).

Run from backend/ directory:
    python scripts/seed_reference_data.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
# Import all models so SQLAlchemy resolves FK references
from app.models import school, auth, staff, staff_history, academic, students, housing, attendance, assessments, fees, documents  # noqa: F401
from app.models.school import GhanaRegion, GhanaDistrict
from app.models.attendance import GhanaPublicHoliday
from app.models.auth import StaffPosition, PositionPermission
from app.models.staff import StaffCategory, StaffRank, StaffType
from app.models.assessments import GradingScale, Grade
from app.models.academic import SHSProgramme, SubjectCatalogue

from reference_data import (
    REGIONS, DISTRICTS, PUBLIC_HOLIDAYS, STAFF_POSITIONS,
    GES_STAFF_CATEGORIES, GES_RANKS,
    GES_GRADING_SCALE_NAME, GES_GRADING_SCALE_BANDS,
    GES_PROGRAMMES, GES_SUBJECTS,
)


async def seed():
    async with AsyncSessionLocal() as db:
        # Regions — batch load existing
        region_map: dict[str, "GhanaRegion"] = {}
        region_codes = [code for _, code in REGIONS]
        existing_regions = await db.execute(
            select(GhanaRegion).where(GhanaRegion.code.in_(region_codes))
        )
        for r in existing_regions.scalars():
            region_map[r.code] = r

        for name, code in REGIONS:
            if code not in region_map:
                r = GhanaRegion(name=name, code=code)
                db.add(r)
                await db.flush()
                region_map[code] = r
                print(f"  Region: {name}")

        # Districts — batch load existing
        district_codes = [code for _, code, _ in DISTRICTS]
        existing_districts = await db.execute(
            select(GhanaDistrict.code).where(GhanaDistrict.code.in_(district_codes))
        )
        existing_district_codes = {row.code for row in existing_districts}
        added_districts = 0
        for name, code, region_code in DISTRICTS:
            if code not in existing_district_codes:
                db.add(GhanaDistrict(name=name, code=code, region_id=region_map[region_code].id))
                added_districts += 1
        await db.flush()
        print(f"  Districts: {added_districts} new (of {len(DISTRICTS)} total)")

        # Public holidays — batch load existing
        existing_holidays = await db.execute(
            select(GhanaPublicHoliday.date, GhanaPublicHoliday.name)
        )
        existing_holiday_keys = {(row.date, row.name) for row in existing_holidays}
        added_holidays = 0
        for holiday_date, name, recurring in PUBLIC_HOLIDAYS:
            if (holiday_date, name) not in existing_holiday_keys:
                db.add(GhanaPublicHoliday(name=name, date=holiday_date, is_recurring=recurring))
                added_holidays += 1
        await db.flush()
        print(f"  Holidays: {added_holidays} new (of {len(PUBLIC_HOLIDAYS)} total)")

        # Staff position templates (authority roles with permissions).
        # Diffed at the permission level, not just skip-if-position-exists —
        # otherwise a (module, action) added to STAFF_POSITIONS after a
        # school's first seed run would never actually reach any existing
        # database, since these are shared templates (school_id=None), never
        # forked per school like Subject/SHSProgramme adoption.
        for code, name, perms in STAFF_POSITIONS:
            pos = await db.scalar(
                select(StaffPosition).where(StaffPosition.code == code, StaffPosition.school_id.is_(None))
            )
            if not pos:
                pos = StaffPosition(code=code, name=name, is_template=True, school_id=None)
                db.add(pos)
                await db.flush()
            existing_perms = {
                (p.module, p.action) for p in (await db.scalars(
                    select(PositionPermission).where(PositionPermission.position_id == pos.id)
                )).all()
            }
            added = 0
            for module, action in perms:
                if (module, action) not in existing_perms:
                    db.add(PositionPermission(position_id=pos.id, module=module, action=action))
                    added += 1
            await db.flush()
            if added:
                print(f"  Position: {name} ({added} new permission(s) of {len(perms)} total)")

        # GES staff category templates (HR classification — no permissions)
        category_map: dict[str, StaffCategory] = {}
        cat_codes = [code for code, _, _ in GES_STAFF_CATEGORIES]
        existing_cats = await db.execute(
            select(StaffCategory).where(
                StaffCategory.code.in_(cat_codes), StaffCategory.school_id.is_(None)
            )
        )
        for cat in existing_cats.scalars():
            category_map[cat.code] = cat

        added_cats = 0
        for code, name, stype in GES_STAFF_CATEGORIES:
            if code not in category_map:
                cat = StaffCategory(
                    school_id=None, name=name, code=code,
                    staff_type=StaffType(stype), is_template=True, is_active=True,
                )
                db.add(cat)
                await db.flush()
                category_map[code] = cat
                added_cats += 1
        print(f"  Categories: {added_cats} new (of {len(GES_STAFF_CATEGORIES)} total)")

        # GES rank templates — batch existence check (one query for all 210 ranks)
        cat_ids = [c.id for c in category_map.values()]
        existing_ranks: set[tuple] = set()
        if cat_ids:
            rows = await db.execute(
                select(StaffRank.category_id, StaffRank.title).where(
                    StaffRank.category_id.in_(cat_ids),
                    StaffRank.school_id.is_(None),
                )
            )
            existing_ranks = {(r.category_id, r.title) for r in rows}

        added = 0
        for cat_code, title in GES_RANKS:
            cat = category_map.get(cat_code)
            if not cat:
                continue
            if (cat.id, title) not in existing_ranks:
                db.add(StaffRank(
                    school_id=None,
                    category_id=cat.id,
                    title=title,
                    is_template=True,
                    is_active=True,
                ))
                added += 1
        await db.flush()
        print(f"  Ranks seeded: {added} new (of {len(GES_RANKS)} total)")

        # GES Standard Grading Scale — shared default (school_id=NULL)
        scale = await db.scalar(
            select(GradingScale).where(
                GradingScale.name == GES_GRADING_SCALE_NAME, GradingScale.school_id.is_(None),
            )
        )
        if not scale:
            scale = GradingScale(
                school_id=None, name=GES_GRADING_SCALE_NAME, is_default=True, is_active=True,
            )
            db.add(scale)
            await db.flush()
            for min_score, max_score, letter_grade, label in GES_GRADING_SCALE_BANDS:
                db.add(Grade(
                    grading_scale_id=scale.id, min_score=min_score, max_score=max_score,
                    letter_grade=letter_grade, label=label,
                ))
            await db.flush()
            print(f"  Grading scale: {GES_GRADING_SCALE_NAME} ({len(GES_GRADING_SCALE_BANDS)} bands)")
        else:
            print(f"  Grading scale: {GES_GRADING_SCALE_NAME} already exists")

        # GES SHS Programmes — shared default catalogue (school_id=NULL)
        prog_codes = [code for code, _ in GES_PROGRAMMES]
        existing_progs = await db.execute(
            select(SHSProgramme.code).where(
                SHSProgramme.code.in_(prog_codes), SHSProgramme.school_id.is_(None),
            )
        )
        existing_prog_codes = {row.code for row in existing_progs}
        added_progs = 0
        for code, name in GES_PROGRAMMES:
            if code not in existing_prog_codes:
                db.add(SHSProgramme(code=code, name=name, is_active=True))
                added_progs += 1
        await db.flush()
        print(f"  Programmes: {added_progs} new (of {len(GES_PROGRAMMES)} total)")

        # GES Subject Catalogue — shared default (school_id=NULL). Matched by code
        # only (not school_id), same as the original standalone seed script's behaviour.
        subj_codes = [code for code, _, _, _ in GES_SUBJECTS]
        existing_subjs = await db.execute(
            select(SubjectCatalogue.code).where(SubjectCatalogue.code.in_(subj_codes))
        )
        existing_subj_codes = {row.code for row in existing_subjs}
        added_subjs = 0
        for code, name, s_type, level in GES_SUBJECTS:
            if code not in existing_subj_codes:
                db.add(SubjectCatalogue(
                    code=code, name=name, subject_type=s_type, level=level, is_active=True,
                ))
                added_subjs += 1
        await db.flush()
        print(f"  Subject catalogue: {added_subjs} new (of {len(GES_SUBJECTS)} total)")

        await db.commit()
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
