"""Shared constants for student import template generation and processing."""
from __future__ import annotations

# (column_letter, header_label, field_key, is_required, col_width)
_COLS: list[tuple[str, str, str, bool, int]] = [
    ("A", "Admission Number*",    "admission_number",    True,  18),
    ("B", "First Name*",          "first_name",          True,  18),
    ("C", "Middle Name",          "middle_name",         False, 15),
    ("D", "Last Name*",           "last_name",           True,  18),
    ("E", "Date of Birth",        "date_of_birth",       False, 16),
    ("F", "Gender",               "gender",              False, 12),
    ("G", "Nationality",          "nationality",         False, 14),
    ("H", "Religion",             "religion",            False, 12),
    ("I", "Hometown",             "hometown",            False, 14),
    ("J", "Residential Address",  "residential_address", False, 30),
]

HEADER_ROW = 3
SAMPLE_ROW = 4
DATA_START = 5
NUM_ROWS   = 200

_DATA_START = DATA_START
_NUM_ROWS   = NUM_ROWS


def make_sentinel(school_code: str) -> str:
    """Return the sentinel embedded in N1 of the student import template."""
    return f"TTEK_STUDENT_IMPORT_{school_code.upper()}"
