"""
Shared constants for staff import template generation and processing.
Both staff_import_template.py and staff_import.py import from here.
"""
from __future__ import annotations

# (column_letter, header_label, field_key, is_required, col_width)
_COLS: list[tuple[str, str, str, bool, int]] = [
    ("A", "Staff Number*",   "staff_number",    True,  18),
    ("B", "First Name*",     "first_name",      True,  18),
    ("C", "Middle Name",     "middle_name",     False, 15),
    ("D", "Last Name*",      "last_name",       True,  18),
    ("E", "Gender",          "gender",          False, 12),
    ("F", "Date of Birth",   "date_of_birth",   False, 16),
    ("G", "National ID",     "national_id",     False, 15),
    ("H", "SSNIT Number",    "ssnit_number",    False, 16),
    ("I", "Phone",           "phone",           False, 14),
    ("J", "Email",           "email",           False, 25),
    ("K", "Position",        "position_name",   False, 20),
    ("L", "Staff Category",  "staff_category",  False, 16),
    ("M", "Employment Type", "employment_type", False, 18),
    ("N", "Marital Status",  "marital_status",  False, 15),
    ("O", "Address",         "address",         False, 28),
    ("P", "Date Joined",     "joined_date",     False, 14),
]

HEADER_ROW  = 3
SAMPLE_ROW  = 4
DATA_START  = 5
NUM_ROWS    = 200
SENTINEL_COL = "R"   # always 2 cols right of last data col (P), outside the merged title

# Keep underscore-prefixed aliases used by staff_import_template.py
_DATA_START = DATA_START
_NUM_ROWS   = NUM_ROWS


def make_sentinel(school_code: str) -> str:
    """Return the sentinel value embedded in SENTINEL_COL row-1 of the template.

    Embedding the school code lets the importer detect cross-school uploads:
    "This template was generated for PRESEC — you are logged in as ADISCO."
    """
    return f"TTEK_STAFF_IMPORT_{school_code.upper()}"
