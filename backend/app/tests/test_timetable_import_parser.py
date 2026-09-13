"""
Pure parser unit tests — no DB, no fixtures — for
services/timetable_import_parser.py. Covers header validation, day-token
normalization, and multi-value cell expansion in isolation from the
DB-aware orchestration tested in test_timetable_import.py.

Run inside Docker: docker compose exec api pytest app/tests/test_timetable_import_parser.py -v
"""
import pytest
from fastapi import HTTPException

from app.services.timetable_import_parser import parse_fet_csv

_HEADER = "Day,Hour,Subject,Teacher(s),Students/Class(es)\n"


def _csv(*lines: str) -> bytes:
    return (_HEADER + "\n".join(lines)).encode("utf-8")


def test_valid_row_parses():
    rows = parse_fet_csv(_csv("Monday,1,Mathematics,Mr Mensah,2 A"))
    assert len(rows) == 1
    r = rows[0]
    assert r.day_code == "MON"
    assert r.subject_name == "Mathematics"
    assert r.class_label == "2 A"
    assert r.teacher_name == "Mr Mensah"
    assert r.extra_teacher_names == []


def test_wrong_headers_raise_422_with_clear_message():
    bad_csv = "Foo,Bar\nMon,1\n".encode("utf-8")
    with pytest.raises(HTTPException) as exc:
        parse_fet_csv(bad_csv)
    assert exc.value.status_code == 422
    assert "Unexpected CSV columns" in exc.value.detail


def test_empty_file_raises_422():
    with pytest.raises(HTTPException) as exc:
        parse_fet_csv(b"")
    assert exc.value.status_code == 422


@pytest.mark.parametrize("day_token,expected", [
    ("Monday", "MON"), ("MON", "MON"), ("mon", "MON"),
    ("Tuesday", "TUE"), ("Wed", "WED"), ("Thursday", "THU"),
    ("Fri", "FRI"), ("Saturday", "SAT"), ("Sunday", "SUN"),
])
def test_day_token_normalization(day_token, expected):
    rows = parse_fet_csv(_csv(f"{day_token},1,Math,Teacher,2 A"))
    assert rows[0].day_code == expected


def test_unrecognized_day_token_yields_none_day_code():
    rows = parse_fet_csv(_csv("Someday,1,Math,Teacher,2 A"))
    assert rows[0].day_code is None
    assert rows[0].day_raw == "Someday"


def test_multi_class_cell_expands_to_multiple_rows():
    rows = parse_fet_csv(_csv("Mon,1,Math,Teacher,2 A;2 B"))
    assert len(rows) == 2
    assert {r.class_label for r in rows} == {"2 A", "2 B"}
    assert all(r.row_number == 2 for r in rows)  # same source CSV line


def test_multi_class_cell_comma_separated_also_expands():
    rows = parse_fet_csv(_csv("Mon,1,Math,Teacher,2 A, 2 B"))
    assert {r.class_label for r in rows} == {"2 A", "2 B"}


def test_multi_teacher_cell_keeps_first_and_lists_the_rest():
    rows = parse_fet_csv(_csv("Mon,1,Math,Mr A;Mr B,2 A"))
    assert len(rows) == 1
    assert rows[0].teacher_name == "Mr A"
    assert rows[0].extra_teacher_names == ["Mr B"]


def test_blank_lines_are_skipped():
    rows = parse_fet_csv(_csv("Mon,1,Math,Teacher,2 A", ",,,,"))
    assert len(rows) == 1


def test_header_matching_is_case_and_punctuation_insensitive():
    csv_bytes = "day,hour,subject,teacher,class\nMon,1,Math,Teacher,2 A\n".encode("utf-8")
    rows = parse_fet_csv(csv_bytes)
    assert len(rows) == 1
    assert rows[0].subject_name == "Math"
