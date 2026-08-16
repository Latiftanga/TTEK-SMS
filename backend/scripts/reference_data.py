"""
Static reference/template data tables for scripts/seed_reference_data.py.

Split out purely to keep seed_reference_data.py's own seed() logic under the
300-line cap — this file has no logic, just data.
"""
from decimal import Decimal
from datetime import date

from app.models.staff import StaffType  # noqa: F401 (re-exported for callers)
from app.models.academic import SchoolLevel, SubjectType


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
# These are POSITIONS (what gives you system access), not job classes — a
# staff member's actual job title/rank (Deputy Headmaster, HOD, Examination
# Officer, Assistant Head, ...) is tracked separately via StaffRank/
# StaffCategory (GES_RANKS below), which already has real fidelity for
# exactly those titles. Deliberately just 5 templates, not a preset per GES
# title: HEAD/BURSAR are manually assigned via the "Authority" picker;
# TEACHER/CLASS_TEACHER/HOUSEMASTER are all auto-derived (never manually
# assigned — see core/permissions.py::resolve_permissions's DERIVED_CODES)
# so their templates must stay even though nobody picks them from a list.
# TEACHER derives from StaffCategory.staff_type == TEACHING (the core role,
# not an optional responsibility); CLASS_TEACHER/HOUSEMASTER derive from
# real ClassTeacher/HouseMaster assignment rows. Anyone whose real delegated
# authority doesn't match one of these 5 (a Deputy Head, an Exam Officer, an
# Assistant Head of any portfolio, ...) gets it via a personal permission
# override on a specific staff member (admin/staff/[id] > Permissions —
# StaffPermission, resolve_permissions()'s Layer 1, beats position defaults)
# rather than a nationwide-fixed permission bundle standing in for a title
# that in practice varies school to school. (Previously seeded 6 more
# templates for exactly those titles — removed as redundant with the
# per-person override path, which already existed and already worked.)
# code, name, permissions: list of (module, action)
STAFF_POSITIONS = [
    ("HEAD", "Headmaster / Headmistress", [
        ("school", "view"), ("school", "edit"), ("school", "manage_users"),
        ("staff", "view"), ("staff", "create"), ("staff", "edit"), ("staff", "delete"),
        ("students", "view"), ("students", "create"), ("students", "edit"), ("students", "delete"),
        ("academic", "view"), ("academic", "create"), ("academic", "edit"), ("academic", "delete"),
        ("attendance", "view"), ("attendance", "record"), ("attendance", "approve"),
        # record_behaviour alongside approve_scores mirrors enter_scores/
        # approve_scores below: require_permission() at the router is a flat
        # check with no scope bypass logic of its own, so a senior position
        # needs the narrow action too to even reach the service layer, where
        # holding approve_scores is what actually makes them unrestricted
        # (core/teacher_scope.py::resolve_report_card_scope).
        ("assessments", "view"), ("assessments", "enter_scores"), ("assessments", "approve_scores"),
        ("assessments", "record_behaviour"),
        ("fees", "view"), ("fees", "collect"), ("fees", "manage"),
        ("housing", "view"), ("housing", "assign"), ("housing", "manage"),
        ("reports", "view"), ("reports", "generate"),
        ("documents", "view"), ("documents", "manage"),
    ]),
    ("CLASS_TEACHER", "Class Teacher", [
        ("school", "view"),
        ("students", "view"), ("students", "create"), ("students", "edit"),
        ("academic", "view"),
        ("attendance", "view"), ("attendance", "record"),
        ("assessments", "view"), ("assessments", "enter_scores"),
        # record_behaviour is a Class Teacher duty specifically (not a plain
        # Subject Teacher's, per the staff-roles spec) — scoped to their own
        # ClassTeacher assignment via core/teacher_scope.py::resolve_report_card_scope.
        ("assessments", "record_behaviour"),
        ("fees", "view"),
        ("reports", "view"),
        ("documents", "view"), ("documents", "manage"),
    ]),
    ("TEACHER", "Teacher", [
        # Subject Teacher's core duty (every teaching staff member) per the
        # staff-roles spec: register students into the subjects they teach,
        # capture scores. students.edit is safe to grant broadly now that
        # core/student_scope.py scopes it — a subject-only teacher (no
        # ClassTeacher row) can only reach the Category B subject-registration
        # path, everything else 404s. Reconciles a pre-existing drift: an old
        # migration (q2r3s4t5u6v7) already created a global TEACHER template
        # directly in the DB, but this script never knew about it until now —
        # seed_reference_data.py's additive-only upsert will backfill any gap
        # against this declared set without touching what that migration
        # already granted (same reconciliation pattern as 12ad/12ag).
        ("school", "view"),
        ("students", "view"), ("students", "edit"),
        ("academic", "view"),
        ("assessments", "view"), ("assessments", "enter_scores"),
        ("reports", "view"),
    ]),
    ("HOUSEMASTER", "Housemaster / Housemistress", [
        ("school", "view"),
        ("students", "view"),
        ("housing", "view"), ("housing", "assign"), ("housing", "manage"),
        ("attendance", "view"), ("attendance", "record"),
        ("reports", "view"),
        ("documents", "view"), ("documents", "manage"),
    ]),
    ("BURSAR", "Bursar / Finance Officer", [
        ("school", "view"),
        ("students", "view"),
        ("fees", "view"), ("fees", "collect"), ("fees", "manage"),
        ("reports", "view"), ("reports", "generate"),
        ("documents", "view"), ("documents", "manage"),
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

# GES SHS Programmes — shared default catalogue (school_id=NULL). Schools
# adopt their own copy via POST /academic/programmes/adopt.
GES_PROGRAMMES = [
    ("SCI",   "General Science"),
    ("ARTS",  "General Arts"),
    ("BUS",   "Business"),
    ("TECH",  "Technical"),
    ("VARTS", "Visual Arts"),
    ("HOME",  "Home Economics"),
    ("AGRIC", "Agricultural Science"),
]

# GES Subject Catalogue — shared default (code, name, subject_type, level).
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
