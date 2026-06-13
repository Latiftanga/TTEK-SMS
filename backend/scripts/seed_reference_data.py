"""
Seed reference data: GhanaRegion, GhanaDistrict, GhanaPublicHoliday,
StaffPosition templates with PositionPermission.

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
from app.models import school, auth, staff, academic, students, housing, attendance, assessments, fees, documents  # noqa: F401
from app.models.school import GhanaRegion, GhanaDistrict
from app.models.attendance import GhanaPublicHoliday
from app.models.auth import StaffPosition, PositionPermission
from datetime import date


REGIONS = [
    ("Greater Accra", "GA"),
    ("Ashanti", "ASH"),
    ("Western", "WES"),
    ("Western North", "WN"),
    ("Central", "CEN"),
    ("Eastern", "EAS"),
    ("Volta", "VOL"),
    ("Oti", "OTI"),
    ("Northern", "NOR"),
    ("Savannah", "SAV"),
    ("North East", "NE"),
    ("Upper East", "UE"),
    ("Upper West", "UW"),
    ("Bono", "BON"),
    ("Bono East", "BE"),
    ("Ahafo", "AHF"),
]

# (name, code, region_code)
DISTRICTS = [
    # Greater Accra
    ("Accra Metropolitan", "ACC-MET", "GA"),
    ("Tema Metropolitan", "TMA-MET", "GA"),
    ("Ga East Municipal", "GA-EAST", "GA"),
    ("Ga West Municipal", "GA-WEST", "GA"),
    ("Adentan Municipal", "ADEN", "GA"),
    ("Kpone-Katamanso Municipal", "KPONE", "GA"),
    # Ashanti
    ("Kumasi Metropolitan", "KUM-MET", "ASH"),
    ("Oforikrom Municipal", "OFO", "ASH"),
    ("Asante Akim Central Municipal", "AAC", "ASH"),
    ("Ejisu Municipal", "EJI", "ASH"),
    ("Kwabre East Municipal", "KWE", "ASH"),
    # Western
    ("Sekondi-Takoradi Metropolitan", "STK-MET", "WES"),
    ("Ahanta West Municipal", "AHW", "WES"),
    ("Mpohor District", "MPO", "WES"),
    # Western North
    ("Sefwi Wiawso Municipal", "SEF-WIA", "WN"),
    ("Bibiani Anhwiaso Bekwai Municipal", "BIB", "WN"),
    # Central
    ("Cape Coast Metropolitan", "CC-MET", "CEN"),
    ("Mfantsiman Municipal", "MFA", "CEN"),
    ("Effutu Municipal", "EFF", "CEN"),
    # Eastern
    ("New Juaben South Municipal", "NJS", "EAS"),
    ("Kwahu West Municipal", "KWW", "EAS"),
    ("Birim Central Municipal", "BCM", "EAS"),
    # Volta
    ("Ho Municipal", "HO-MUN", "VOL"),
    ("Hohoe Municipal", "HOH", "VOL"),
    ("Keta Municipal", "KET", "VOL"),
    # Oti
    ("Krachi East Municipal", "KRE", "OTI"),
    ("Nkwanta South Municipal", "NKS", "OTI"),
    # Northern
    ("Tamale Metropolitan", "TAM-MET", "NOR"),
    ("Sagnarigu Municipal", "SAG", "NOR"),
    ("Tolon District", "TOL", "NOR"),
    # Savannah
    ("Bole District", "BOL", "SAV"),
    ("Sawla-Tuna-Kalba District", "STK", "SAV"),
    # North East
    ("Nalerigu-Gambaga District", "NAL", "NE"),
    ("Bunkpurugu Nakpayili District", "BUN", "NE"),
    # Upper East
    ("Bolgatanga Municipal", "BOL-MUN", "UE"),
    ("Bawku Municipal", "BAW", "UE"),
    ("Navrongo Municipal", "NAV", "UE"),
    # Upper West
    ("Wa Municipal", "WA-MUN", "UW"),
    ("Lawra Municipal", "LAW", "UW"),
    # Bono
    ("Sunyani Municipal", "SUN", "BON"),
    ("Dormaa Municipal", "DOR", "BON"),
    # Bono East
    ("Techiman Municipal", "TEC", "BE"),
    ("Kintampo North Municipal", "KIN", "BE"),
    # Ahafo
    ("Goaso Municipal", "GOA", "AHF"),
    ("Asunafo South District", "ASS", "AHF"),
]

PUBLIC_HOLIDAYS = [
    (date(2025, 1, 1), "New Year's Day", True),
    (date(2025, 1, 7), "Constitution Day", True),
    (date(2025, 3, 6), "Independence Day", True),
    (date(2025, 4, 18), "Good Friday", False),
    (date(2025, 4, 21), "Easter Monday", False),
    (date(2025, 5, 1), "Labour Day", True),
    (date(2025, 5, 25), "Africa Day", True),
    (date(2025, 7, 1), "Republic Day / Founders Day", True),
    (date(2025, 9, 21), "Kwame Nkrumah Memorial Day", True),
    (date(2025, 12, 25), "Christmas Day", True),
    (date(2025, 12, 26), "Boxing Day", True),
    # Islamic holidays for 2025 (approximate)
    (date(2025, 3, 30), "Eid ul-Fitr", False),
    (date(2025, 6, 7), "Eid ul-Adha", False),
]

# (code, name, permissions)
# permissions: list of (module, action)
STAFF_POSITIONS = [
    ("HEAD", "Headmaster / Headmistress", [
        ("school", "view"), ("school", "edit"), ("school", "manage_users"),
        ("staff", "view"), ("staff", "create"), ("staff", "edit"), ("staff", "delete"),
        ("students", "view"), ("students", "create"), ("students", "edit"), ("students", "delete"),
        ("academic", "view"), ("academic", "create"), ("academic", "edit"), ("academic", "delete"),
        ("attendance", "view"), ("attendance", "record"), ("attendance", "approve"),
        ("assessments", "view"), ("assessments", "enter_scores"), ("assessments", "approve_scores"),
        ("fees", "view"), ("fees", "collect"), ("fees", "manage"),
        ("housing", "view"), ("housing", "assign"), ("housing", "manage"),
        ("reports", "view"), ("reports", "generate"),
    ]),
    ("DEPUTY_HEAD", "Deputy Headmaster", [
        ("school", "view"), ("school", "edit"),
        ("staff", "view"), ("staff", "create"), ("staff", "edit"),
        ("students", "view"), ("students", "create"), ("students", "edit"),
        ("academic", "view"), ("academic", "create"), ("academic", "edit"),
        ("attendance", "view"), ("attendance", "record"), ("attendance", "approve"),
        ("assessments", "view"), ("assessments", "enter_scores"), ("assessments", "approve_scores"),
        ("fees", "view"), ("fees", "collect"),
        ("housing", "view"), ("housing", "assign"),
        ("reports", "view"), ("reports", "generate"),
    ]),
    ("HOD", "Head of Department", [
        ("school", "view"),
        ("staff", "view"),
        ("students", "view"),
        ("academic", "view"), ("academic", "create"), ("academic", "edit"),
        ("attendance", "view"), ("attendance", "record"),
        ("assessments", "view"), ("assessments", "enter_scores"), ("assessments", "approve_scores"),
        ("fees", "view"),
        ("housing", "view"),
        ("reports", "view"), ("reports", "generate"),
    ]),
    ("CLASS_TEACHER", "Class Teacher", [
        ("school", "view"),
        ("students", "view"), ("students", "create"), ("students", "edit"),
        ("academic", "view"),
        ("attendance", "view"), ("attendance", "record"),
        ("assessments", "view"), ("assessments", "enter_scores"),
        ("fees", "view"),
        ("reports", "view"),
    ]),
    ("SUBJECT_TEACHER", "Subject Teacher", [
        ("school", "view"),
        ("students", "view"),
        ("academic", "view"),
        ("attendance", "view"), ("attendance", "record"),
        ("assessments", "view"), ("assessments", "enter_scores"),
        ("reports", "view"),
    ]),
    ("BURSAR", "Bursar", [
        ("school", "view"),
        ("students", "view"),
        ("fees", "view"), ("fees", "collect"), ("fees", "manage"),
        ("reports", "view"), ("reports", "generate"),
    ]),
]


async def seed():
    async with AsyncSessionLocal() as db:
        # Regions
        region_map: dict[str, "GhanaRegion"] = {}
        for name, code in REGIONS:
            existing = await db.scalar(select(GhanaRegion).where(GhanaRegion.code == code))
            if not existing:
                r = GhanaRegion(name=name, code=code)
                db.add(r)
                await db.flush()
                region_map[code] = r
                print(f"  Region: {name}")
            else:
                region_map[code] = existing

        # Districts
        for name, code, region_code in DISTRICTS:
            existing = await db.scalar(select(GhanaDistrict).where(GhanaDistrict.code == code))
            if not existing:
                region = region_map[region_code]
                d = GhanaDistrict(name=name, code=code, region_id=region.id)
                db.add(d)
                print(f"  District: {name}")
        await db.flush()

        # Public holidays
        for holiday_date, name, recurring in PUBLIC_HOLIDAYS:
            existing = await db.scalar(
                select(GhanaPublicHoliday).where(
                    GhanaPublicHoliday.date == holiday_date,
                    GhanaPublicHoliday.name == name,
                )
            )
            if not existing:
                db.add(GhanaPublicHoliday(name=name, date=holiday_date, is_recurring=recurring))
                print(f"  Holiday: {name} ({holiday_date})")
        await db.flush()

        # Staff position templates
        for code, name, perms in STAFF_POSITIONS:
            existing = await db.scalar(
                select(StaffPosition).where(StaffPosition.code == code, StaffPosition.school_id.is_(None))
            )
            if not existing:
                pos = StaffPosition(code=code, name=name, is_template=True, school_id=None)
                db.add(pos)
                await db.flush()
                for module, action in perms:
                    db.add(PositionPermission(position_id=pos.id, module=module, action=action))
                await db.flush()
                print(f"  Position: {name} ({len(perms)} permissions)")

        await db.commit()
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
