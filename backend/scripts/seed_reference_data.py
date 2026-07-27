"""
Seed reference data: GhanaRegion, GhanaDistrict, GhanaPublicHoliday,
StaffPosition templates with PositionPermission,
StaffCategory + StaffRank GES templates,
GES Standard Grading Scale (shared default — see resolve_grade()).

Run from backend/ directory:
    python scripts/seed_reference_data.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from sqlalchemy import select, tuple_
from app.core.database import AsyncSessionLocal
# Import all models so SQLAlchemy resolves FK references
from app.models import school, auth, staff, staff_history, academic, students, housing, attendance, assessments, fees, documents  # noqa: F401
from app.models.school import GhanaRegion, GhanaDistrict
from app.models.attendance import GhanaPublicHoliday
from app.models.auth import StaffPosition, PositionPermission
from app.models.staff import StaffCategory, StaffRank, StaffType
from app.models.assessments import GradingScale, Grade
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

# Authority roles — system permissions only.
# These are POSITIONS (what gives you system access), not job classes.
# code, name, permissions: list of (module, action)
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
        ("students", "view"), ("students", "edit"),
        ("academic", "view"), ("academic", "edit"),
        ("attendance", "view"), ("attendance", "record"),
        ("assessments", "view"), ("assessments", "enter_scores"), ("assessments", "approve_scores"),
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
    ("HOUSEMASTER", "Housemaster / Housemistress", [
        ("school", "view"),
        ("students", "view"),
        ("housing", "view"), ("housing", "assign"), ("housing", "manage"),
        ("attendance", "view"), ("attendance", "record"),
        ("reports", "view"),
    ]),
    ("EXAM_OFFICER", "Examination Officer", [
        ("school", "view"),
        ("students", "view"),
        ("academic", "view"), ("academic", "edit"),
        ("assessments", "view"), ("assessments", "enter_scores"), ("assessments", "approve_scores"),
        ("reports", "view"), ("reports", "generate"),
    ]),
    ("BURSAR", "Bursar / Finance Officer", [
        ("school", "view"),
        ("students", "view"),
        ("fees", "view"), ("fees", "collect"), ("fees", "manage"),
        ("reports", "view"), ("reports", "generate"),
    ]),
]

# GES staff category templates — what a person is employed to do.
# (code, display_name, staff_type)
GES_STAFF_CATEGORIES = [
    ("TEACHING",       "Teaching Staff",                     "TEACHING"),
    ("ACCOUNTING",     "Accounting Class",                   "NON_TEACHING"),
    ("ADMINISTRATIVE", "Administrative Class",               "NON_TEACHING"),
    ("INTERNAL_AUDIT", "Internal Audit Class",               "NON_TEACHING"),
    ("CATERING",       "Catering Class",                     "NON_TEACHING"),
    ("HOUSE_MOTHERS",  "House Mothers",                      "NON_TEACHING"),
    ("LIBRARY",        "Library Class",                      "NON_TEACHING"),
    ("LABORATORY",     "Laboratory Class",                   "NON_TEACHING"),
    ("SECRETARY",      "Secretary Class",                    "NON_TEACHING"),
    ("ROTA_PRINT",     "Rota Print Class",                   "NON_TEACHING"),
    ("TECHNICAL",      "Technical Class",                    "NON_TEACHING"),
    ("TRADESMAN",      "Tradesman Class",                    "NON_TEACHING"),
    ("AGRICULTURE",    "Agriculture Class",                  "NON_TEACHING"),
    ("RECEPTION",      "Reception/Telephone Operator Class", "NON_TEACHING"),
    ("MESSENGER",      "Messengers Class",                   "NON_TEACHING"),
    ("SUPPLIES",       "Supplies Class",                     "NON_TEACHING"),
    ("SECURITY",       "Security Class",                     "NON_TEACHING"),
    ("PORTER",         "Porter Class",                       "NON_TEACHING"),
    ("CARETAKER",      "Caretaker Class",                    "NON_TEACHING"),
    ("WATCHMAN",       "Watchman/Gateman Class",             "NON_TEACHING"),
    ("DRIVER",         "Driver Class",                       "NON_TEACHING"),
    ("CONSERVANCY",    "Conservancy Labourers Class",        "NON_TEACHING"),
    ("GENERAL_LABOUR", "General Labourer Class",             "NON_TEACHING"),
]

# GES rank templates — (category_code, rank_title)
GES_RANKS = [
    # Teaching Staff
    ("TEACHING", "Director General"),
    ("TEACHING", "Dep. Director General"),
    ("TEACHING", "Director I"),
    ("TEACHING", "Director II"),
    ("TEACHING", "Director II Principal"),
    ("TEACHING", "Deputy Director SHS Head"),
    ("TEACHING", "Deputy Director Vice Principal"),
    ("TEACHING", "Deputy Director Basic Head"),
    ("TEACHING", "Dep. Director Asst. Head SHS"),
    ("TEACHING", "Dep. Director Snr. House Master"),
    ("TEACHING", "Dep. Director Hse/Frm Mster/HOD/Chaplain/Imam/G&C Cord"),
    ("TEACHING", "Dep. Director Unit Head"),
    ("TEACHING", "Dep. Director Basic Grade"),
    ("TEACHING", "Dep. Director Non-Prof"),
    ("TEACHING", "Asst. Director I Head SHS"),
    ("TEACHING", "Asst. Director I Vice Principal"),
    ("TEACHING", "Asst. Director I Unit Head"),
    ("TEACHING", "Asst. Director I Snr Hse Master"),
    ("TEACHING", "Asst. Director I Asst. Head SHS"),
    ("TEACHING", "Asst. Director I Hse/Frm Mster/HOD/Chaplain/Imam/G&C Cord"),
    ("TEACHING", "Asst. Director I Hqtrs, Region, District"),
    ("TEACHING", "Asst. Director I Basic Grade"),
    ("TEACHING", "Asst. Director I Non-Prof"),
    ("TEACHING", "Asst. Director II Head Basic"),
    ("TEACHING", "Asst. Director II Asst. Head SHS"),
    ("TEACHING", "Asst. Director II Snr. House Master"),
    ("TEACHING", "Asst. Director II Hse/Frm Mster/HOD/Chaplain/Imam/G&C Cord"),
    ("TEACHING", "Asst. Director II Hqtrs, Region, District"),
    ("TEACHING", "Asst. Director II Basic Grade"),
    ("TEACHING", "Asst. Director II Non-Prof"),
    ("TEACHING", "Prin. Superintendent Head Basic"),
    ("TEACHING", "Prin. Supt. Hse/Frm Mster/HOD/Chaplain/Imam/G&C Cord"),
    ("TEACHING", "Prin. Supt Professional"),
    ("TEACHING", "Prin. Supt. Non-Professional"),
    ("TEACHING", "Senior Supt. I Professional"),
    ("TEACHING", "Senior Supt. I Non-Professional"),
    ("TEACHING", "Senior Supt. II Professional"),
    ("TEACHING", "Snr. Supervisor Instructor"),
    ("TEACHING", "Snr. Supt. II Non-Professional"),
    ("TEACHING", "Supervisor Instructor"),
    ("TEACHING", "Superintendent I Professional"),
    ("TEACHING", "Principal Technical Instructor"),
    ("TEACHING", "Superintendent I Non-Professional"),
    ("TEACHING", "Snr. Technical Instructor"),
    ("TEACHING", "Superintendent II Professional"),
    ("TEACHING", "Technical Instructor I"),
    ("TEACHING", "Superintendent II Non-Professional"),
    ("TEACHING", "Technical Instructor II"),
    ("TEACHING", "Snr. Craft Instructor"),
    ('TEACHING', 'Pupil Teacher WASSCE/GCE "A" Level'),
    ("TEACHING", "Trainee Teacher"),
    ("TEACHING", "Craft Instructor"),
    ('TEACHING', 'Pupil Teacher GCE "O" Level'),
    # Accounting Class
    ("ACCOUNTING", "Chief Accountant"),
    ("ACCOUNTING", "Chief Accountant II"),
    ("ACCOUNTING", "Deputy Chief Accountant"),
    ("ACCOUNTING", "Deputy Chief Accountant II"),
    ("ACCOUNTING", "Principal Accountant (Chartered)"),
    ("ACCOUNTING", "Principal Accountant (Unit Head)"),
    ("ACCOUNTING", "Principal Accountant (Basic Grade)"),
    ("ACCOUNTING", "Senior Accountant"),
    ("ACCOUNTING", "Accountant"),
    ("ACCOUNTING", "Assistant Accountant"),
    ("ACCOUNTING", "Accountant Assistant"),
    # Administrative Class
    ("ADMINISTRATIVE", "Chief Admin Officer"),
    ("ADMINISTRATIVE", "Chief Admin Officer II"),
    ("ADMINISTRATIVE", "Deputy Chief Admin Officer"),
    ("ADMINISTRATIVE", "Deputy Chief Admin Officer II"),
    ("ADMINISTRATIVE", "Principal Admin Officer (Chartered)"),
    ("ADMINISTRATIVE", "Principal Admin Officer (Unit Head)"),
    ("ADMINISTRATIVE", "Principal Admin Officer (Basic Grade)"),
    ("ADMINISTRATIVE", "Senior Admin Officer"),
    ("ADMINISTRATIVE", "Administrative Officer"),
    ("ADMINISTRATIVE", "Assistant Admin Officer"),
    ("ADMINISTRATIVE", "Senior Clerk"),
    ("ADMINISTRATIVE", "Clerk Grade I"),
    ("ADMINISTRATIVE", "Clerk Grade II"),
    # Internal Audit Class
    ("INTERNAL_AUDIT", "Chief Internal Auditor"),
    ("INTERNAL_AUDIT", "Chief Internal Auditor II"),
    ("INTERNAL_AUDIT", "Deputy Chief Auditor"),
    ("INTERNAL_AUDIT", "Deputy Chief Auditor II"),
    ("INTERNAL_AUDIT", "Principal Internal Auditor (Chartered)"),
    ("INTERNAL_AUDIT", "Principal Internal Auditor (Unit Head)"),
    ("INTERNAL_AUDIT", "Principal Internal Auditor (Basic Grade)"),
    ("INTERNAL_AUDIT", "Senior Internal Auditor"),
    ("INTERNAL_AUDIT", "Internal Auditor"),
    ("INTERNAL_AUDIT", "Assistant Internal Auditor"),
    ("INTERNAL_AUDIT", "Internal Audit Asst. Gd. I"),
    ("INTERNAL_AUDIT", "Internal Audit Asst. Gd. II"),
    ("INTERNAL_AUDIT", "Internal Audit Asst. Gd. III"),
    # Catering Class
    ("CATERING", "Chief Domestic Bursar"),
    ("CATERING", "Deputy Chief Domestic Bursar"),
    ("CATERING", "Principal Domestic Bursar"),
    ("CATERING", "Senior Domestic Bursar"),
    ("CATERING", "Domestic Bursar"),
    ("CATERING", "Assistant Domestic Bursar"),
    ("CATERING", "Senior Matron"),
    ("CATERING", "Matron"),
    ("CATERING", "Chief Cook"),
    ("CATERING", "Cook"),
    ("CATERING", "Assistant Cook"),
    ("CATERING", "Head Steward"),
    ("CATERING", "Steward"),
    ("CATERING", "Head Laundry Man"),
    ("CATERING", "Laundry Man"),
    ("CATERING", "Head Pantry Hand"),
    ("CATERING", "Pantry Hand"),
    # House Mothers
    ("HOUSE_MOTHERS", "Snr House Mother"),
    ("HOUSE_MOTHERS", "House Mother"),
    # Library Class
    ("LIBRARY", "Chief Librarian"),
    ("LIBRARY", "Deputy Chief Librarian"),
    ("LIBRARY", "Principal Library"),
    ("LIBRARY", "Senior Library"),
    ("LIBRARY", "Library"),
    ("LIBRARY", "Assistant Library"),
    ("LIBRARY", "Senior Library Assistant"),
    ("LIBRARY", "Library Assistant"),
    ("LIBRARY", "Junior Library Assistant"),
    # Laboratory Class
    ("LABORATORY", "Chief Laboratory Technician"),
    ("LABORATORY", "Deputy Chief Lab Technician"),
    ("LABORATORY", "Principal Lab Technician"),
    ("LABORATORY", "Senior Lab Technician"),
    ("LABORATORY", "Laboratory Technician"),
    ("LABORATORY", "Assistant Lab Technician"),
    ("LABORATORY", "Senior Lab Assistant"),
    ("LABORATORY", "Laboratory Assistant Gd 1"),
    ("LABORATORY", "Laboratory Assistant Gd 2"),
    # Secretary Class
    ("SECRETARY", "Principal Private Secretary"),
    ("SECRETARY", "Senior Private Secretary"),
    ("SECRETARY", "Private Secretary"),
    ("SECRETARY", "Stenographer Secretary"),
    ("SECRETARY", "Stenographer Gd I"),
    ("SECRETARY", "Stenographer Gd II"),
    ("SECRETARY", "Principal Typist"),
    ("SECRETARY", "Senior Typist"),
    ("SECRETARY", "Typist Grade I"),
    ("SECRETARY", "Typist Grade II"),
    ("SECRETARY", "Ungraded Typist"),
    # Rota Print Class
    ("ROTA_PRINT", "Senior Rota Print Operator"),
    ("ROTA_PRINT", "Rota Print Operator"),
    ("ROTA_PRINT", "Rota Print"),
    # Technical Class
    ("TECHNICAL", "Chief Technical Officer"),
    ("TECHNICAL", "Deputy Chief Tech. Officer"),
    ("TECHNICAL", "Principal Technical Officer"),
    ("TECHNICAL", "Senior Technical Officer"),
    ("TECHNICAL", "Technical Officer"),
    ("TECHNICAL", "Asst. Technical Officer"),
    ("TECHNICAL", "Senior Technical Assistant"),
    ("TECHNICAL", "Technical Assistant Grade I"),
    ("TECHNICAL", "Technical Assistant Grade II"),
    # Tradesman Class
    ("TRADESMAN", "Workshop Supervisor"),
    ("TRADESMAN", "Foreman"),
    ("TRADESMAN", "Junior Foreman"),
    ("TRADESMAN", "Artisan"),
    ("TRADESMAN", "Supervisory Tradesman"),
    ("TRADESMAN", "Tradesman Gd I"),
    ("TRADESMAN", "Tradesman Gd II"),
    # Agriculture Class
    ("AGRICULTURE", "Senior Farm Supervisor"),
    ("AGRICULTURE", "Farm Supervisor"),
    ("AGRICULTURE", "Farm Assistant"),
    ("AGRICULTURE", "Senior Farm Hand"),
    ("AGRICULTURE", "Farm Hand"),
    # Reception/Telephone Operator Class
    ("RECEPTION", "Receptionist"),
    ("RECEPTION", "Telephonist"),
    ("RECEPTION", "Telephone Operator"),
    # Messengers Class
    ("MESSENGER", "Chief Messenger"),
    ("MESSENGER", "Messenger"),
    # Supplies Class
    ("SUPPLIES", "Chief Supply Officer"),
    ("SUPPLIES", "Deputy Chief Supply Officer"),
    ("SUPPLIES", "Principal Supply Officer"),
    ("SUPPLIES", "Senior Supply Officer"),
    ("SUPPLIES", "Supply Officer"),
    ("SUPPLIES", "Principal Storekeeper"),
    ("SUPPLIES", "Senior Storekeeper"),
    ("SUPPLIES", "Storekeeper"),
    ("SUPPLIES", "Assistant Storekeeper"),
    ("SUPPLIES", "Store Assistant"),
    # Security Class
    ("SECURITY", "Chief Security Officer"),
    ("SECURITY", "Deputy Chief Security Officer"),
    ("SECURITY", "Principal Security Officer"),
    ("SECURITY", "Senior Security Officer"),
    ("SECURITY", "Security Officer"),
    ("SECURITY", "Assistant Security Officer"),
    # Porter Class
    ("PORTER", "Head Porter"),
    ("PORTER", "Principal Porter"),
    ("PORTER", "Senior Porter"),
    ("PORTER", "Porter"),
    ("PORTER", "Asst. Porter"),
    ("PORTER", "Junior Porter"),
    # Caretaker Class
    ("CARETAKER", "Supervising Caretaker"),
    ("CARETAKER", "Senior Caretaker"),
    ("CARETAKER", "Caretaker"),
    # Watchman/Gateman Class
    ("WATCHMAN", "Head Watchman/Gateman"),
    ("WATCHMAN", "Senior Watchman/Gateman"),
    ("WATCHMAN", "Night Watchman/Gateman"),
    ("WATCHMAN", "Day Watchman/Gateman"),
    # Driver Class
    ("DRIVER", "Yard Foreman"),
    ("DRIVER", "Chief Driver"),
    ("DRIVER", "Principal Driver"),
    ("DRIVER", "Senior Driver"),
    ("DRIVER", "Driver Gd I / Driver Mechanic"),
    ("DRIVER", "Driver Gd II"),
    ("DRIVER", "Tractor Operator"),
    # Conservancy Labourers Class
    ("CONSERVANCY", "Chief Conservancy Headman"),
    ("CONSERVANCY", "Conservancy Headman"),
    ("CONSERVANCY", "Snr Conservancy Labourer"),
    ("CONSERVANCY", "Conservancy Labourer"),
    # General Labourer Class
    ("GENERAL_LABOUR", "Chief Headman"),
    ("GENERAL_LABOUR", "Labourer Headman"),
    ("GENERAL_LABOUR", "Senior Labourer/Cleaner"),
    ("GENERAL_LABOUR", "General Labourer"),
    ("GENERAL_LABOUR", "Cleaner"),
]

# GES Standard Grading Scale — shared default (school_id=NULL). resolve_grade()
# falls back to this when a school hasn't created its own default scale.
# (min_score, max_score, letter_grade, label)
GES_GRADING_SCALE_NAME = "GES Standard Grading Scale"
GES_GRADING_SCALE_BANDS = [
    (Decimal("80.00"), Decimal("100.00"), "A1", "Excellent"),
    (Decimal("75.00"), Decimal("79.99"),  "B2", "Very Good"),
    (Decimal("70.00"), Decimal("74.99"),  "B3", "Good"),
    (Decimal("65.00"), Decimal("69.99"),  "C4", "Credit"),
    (Decimal("60.00"), Decimal("64.99"),  "C5", "Credit"),
    (Decimal("55.00"), Decimal("59.99"),  "C6", "Credit"),
    (Decimal("50.00"), Decimal("54.99"),  "D7", "Pass"),
    (Decimal("45.00"), Decimal("49.99"),  "E8", "Pass"),
    (Decimal("0.00"),  Decimal("44.99"),  "F9", "Fail"),
]


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

        # Staff position templates (authority roles with permissions)
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

        await db.commit()
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
