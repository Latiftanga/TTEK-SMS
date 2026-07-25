"""
Seed GES national reference data: SHS programmes and subject catalogue.

Safe to run multiple times — skips rows that already exist (match on code).

Usage:
    docker compose exec api python scripts/seed_ges_data.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
# All models must be imported so SQLAlchemy can resolve cross-file FK references
from app.models import academic, assessments, attendance, auth, documents, fees, housing, school, staff, staff_history, students  # noqa: F401
from app.models.academic import SchoolLevel, SHSProgramme, SubjectCatalogue, SubjectType

# ── GES SHS Programmes ────────────────────────────────────────────────────────
# school_id=None means system-wide (available to all SHS schools)

GES_PROGRAMMES = [
    {"code": "SCI",   "name": "General Science"},
    {"code": "ARTS",  "name": "General Arts"},
    {"code": "BUS",   "name": "Business"},
    {"code": "TECH",  "name": "Technical"},
    {"code": "VARTS", "name": "Visual Arts"},
    {"code": "HOME",  "name": "Home Economics"},
    {"code": "AGRIC", "name": "Agricultural Science"},
]

# ── GES Subject Catalogue ─────────────────────────────────────────────────────
# Format: (code, name, subject_type, level)

GES_SUBJECTS: list[tuple[str, str, SubjectType, SchoolLevel]] = [
    # SHS Core (all students)
    ("ENG",    "English Language",      SubjectType.CORE,     SchoolLevel.SHS),
    ("CMATH",  "Core Mathematics",      SubjectType.CORE,     SchoolLevel.SHS),
    ("INTSCI", "Integrated Science",    SubjectType.CORE,     SchoolLevel.SHS),
    ("SOCSCI", "Social Studies",        SubjectType.CORE,     SchoolLevel.SHS),

    # SHS Elective — General Science
    ("EMATH",  "Elective Mathematics",  SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("PHY",    "Physics",               SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("CHEM",   "Chemistry",             SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("BIO",    "Biology",               SubjectType.ELECTIVE, SchoolLevel.SHS),

    # SHS Elective — General Arts
    ("LIT",    "Literature in English", SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("HIST",   "History",               SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("GOVT",   "Government",            SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("ECON",   "Economics",             SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("FREN",   "French",                SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("GEOG",   "Geography",             SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("CRS",    "Christian Religious Studies", SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("IRS",    "Islamic Religious Studies",   SubjectType.ELECTIVE, SchoolLevel.SHS),

    # SHS Elective — Business
    ("BMGT",   "Business Management",   SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("FACCT",  "Financial Accounting",  SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("CACCT",  "Cost Accounting",       SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("BIT",    "Business Information Technology", SubjectType.ELECTIVE, SchoolLevel.SHS),

    # SHS Elective — Technical
    ("TDRAW",  "Technical Drawing",     SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("AUTOM",  "Auto Mechanics",        SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("BLDG",   "Building Construction", SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("ELEC",   "Applied Electricity",   SubjectType.ELECTIVE, SchoolLevel.SHS),

    # SHS Elective — Visual Arts
    ("GDES",   "Graphic Design",        SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("TXTL",   "Textiles",              SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("CERX",   "Ceramics",              SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("SCUL",   "Sculpture",             SubjectType.ELECTIVE, SchoolLevel.SHS),

    # SHS Elective — Home Economics
    ("FNU",    "Foods and Nutrition",   SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("MLV",    "Management in Living",  SubjectType.ELECTIVE, SchoolLevel.SHS),
    ("CTXT",   "Clothing and Textiles", SubjectType.ELECTIVE, SchoolLevel.SHS),

    # SHS Elective — Agricultural Science
    ("AGRSCI", "Agricultural Science (Elective)", SubjectType.ELECTIVE, SchoolLevel.SHS),

    # BASIC Core
    ("BENG",   "English Language",      SubjectType.CORE,     SchoolLevel.BASIC),
    ("BMATH",  "Mathematics",           SubjectType.CORE,     SchoolLevel.BASIC),
    ("BINTSCI","Integrated Science",    SubjectType.CORE,     SchoolLevel.BASIC),
    ("BSOC",   "Social Studies",        SubjectType.CORE,     SchoolLevel.BASIC),
    ("RME",    "Religious and Moral Education", SubjectType.CORE, SchoolLevel.BASIC),
    ("ICT",    "ICT / Computing",       SubjectType.CORE,     SchoolLevel.BASIC),
    ("CARTS",  "Creative Arts and Design", SubjectType.CORE,  SchoolLevel.BASIC),
    ("PE",     "Physical Education and Health", SubjectType.CORE, SchoolLevel.BASIC),
    ("CTECH",  "Career Technology",     SubjectType.CORE,     SchoolLevel.BASIC),
    ("GHL",    "Ghanaian Language",     SubjectType.ELECTIVE, SchoolLevel.BASIC),
    ("BFREN",  "French",               SubjectType.ELECTIVE,  SchoolLevel.BASIC),
]


async def seed() -> None:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        session = AsyncSession(bind=conn)

        # Seed programmes
        prog_added = 0
        for p in GES_PROGRAMMES:
            exists = await session.scalar(
                select(SHSProgramme).where(
                    SHSProgramme.code == p["code"], SHSProgramme.school_id.is_(None)
                )
            )
            if not exists:
                session.add(SHSProgramme(code=p["code"], name=p["name"], is_active=True))
                prog_added += 1
        print(f"Programmes: {prog_added} added, {len(GES_PROGRAMMES) - prog_added} already exist")

        # Seed subject catalogue
        subj_added = 0
        for code, name, s_type, level in GES_SUBJECTS:
            exists = await session.scalar(
                select(SubjectCatalogue).where(SubjectCatalogue.code == code)
            )
            if not exists:
                session.add(SubjectCatalogue(
                    code=code, name=name, subject_type=s_type, level=level, is_active=True
                ))
                subj_added += 1
        print(f"Subject catalogue: {subj_added} added, {len(GES_SUBJECTS) - subj_added} already exist")

        await session.flush()
    await engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(seed())
