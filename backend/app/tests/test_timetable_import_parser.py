"""
Pure parser unit tests — no DB, no fixtures — for
services/timetable_import_parser.py. Covers strict header validation,
day-token normalization, and multi-class cell expansion in isolation from
the DB-aware orchestration tested in test_timetable_import.py.

Run inside Docker: docker compose exec api pytest app/tests/test_timetable_import_parser.py -v
"""
import pytest
from fastapi import HTTPException

from app.services.timetable_import_parser import parse_timetable_csv

_HEADER = "Day,Period,Subject,Classes\n"


def _csv(*lines: str) -> bytes:
    return (_HEADER + "\n".join(lines)).encode("utf-8")


def test_valid_row_parses():
    rows = parse_timetable_csv(_csv("Monday,1,Mathematics,2 A"))
    assert len(rows) == 1
    r = rows[0]
    assert r.day_code == "MON"
    assert r.subject_name == "Mathematics"
    assert r.class_label == "2 A"


def test_wrong_headers_raise_422_with_clear_message():
    bad_csv = "Foo,Bar\nMon,1\n".encode("utf-8")
    with pytest.raises(HTTPException) as exc:
        parse_timetable_csv(bad_csv)
    assert exc.value.status_code == 422
    assert "Day, Period, Subject, Classes" in exc.value.detail


def test_empty_file_raises_422():
    with pytest.raises(HTTPException) as exc:
        parse_timetable_csv(b"")
    assert exc.value.status_code == 422


@pytest.mark.parametrize("day_token,expected", [
    ("Monday", "MON"), ("MON", "MON"), ("mon", "MON"),
    ("Tuesday", "TUE"), ("Wed", "WED"), ("Thursday", "THU"),
    ("Fri", "FRI"), ("Saturday", "SAT"), ("Sunday", "SUN"),
])
def test_day_token_normalization(day_token, expected):
    rows = parse_timetable_csv(_csv(f"{day_token},1,Math,2 A"))
    assert rows[0].day_code == expected


def test_unrecognized_day_token_yields_none_day_code():
    rows = parse_timetable_csv(_csv("Someday,1,Math,2 A"))
    assert rows[0].day_code is None
    assert rows[0].day_raw == "Someday"


def test_multi_class_cell_expands_to_multiple_rows():
    rows = parse_timetable_csv(_csv("Mon,1,Math,2 A;2 B"))
    assert len(rows) == 2
    assert {r.class_label for r in rows} == {"2 A", "2 B"}
    assert all(r.row_number == 2 for r in rows)  # same source CSV line


def test_quoted_multi_class_cell_still_parses():
    """Classes now only ever splits on `;`, never `,` — a quoted cell (which
    real CSV quoting rules already handle natively) needs no comma-based
    splitting at all."""
    rows = parse_timetable_csv(_csv('Mon,1,Math,"2 A;2 B"'))
    assert {r.class_label for r in rows} == {"2 A", "2 B"}


def test_unquoted_comma_in_last_column_is_folded_back_not_dropped():
    """An unquoted comma-separated Classes cell (a plausible mistake — users
    are comma-trained by spreadsheets) makes csv.DictReader dump the
    overflow into a restkey instead of the Classes field. Folding it back
    in means the row still surfaces as an explicit unmatched-class label
    downstream instead of the extra class silently vanishing with no error
    or warning."""
    rows = parse_timetable_csv(_csv("Mon,1,Math,2 A, 2 B"))
    assert len(rows) == 1
    assert rows[0].class_label == "2 A, 2 B"


def test_blank_classes_cell_is_not_silently_dropped():
    """Day/Period/Subject filled in but Classes left blank must still
    surface as a row (with an empty class label so the DB-aware
    orchestrator reports a clear error), not vanish from the results."""
    rows = parse_timetable_csv(_csv("Mon,1,Math,"))
    assert len(rows) == 1
    assert rows[0].class_label == ""


def test_trailing_blank_header_column_is_tolerated():
    """A stray trailing empty header (a common Excel/Sheets export
    artifact) must not reject an otherwise-correct file."""
    csv_bytes = "Day,Period,Subject,Classes,\nMon,1,Math,2 A,\n".encode("utf-8")
    rows = parse_timetable_csv(csv_bytes)
    assert len(rows) == 1
    assert rows[0].class_label == "2 A"


def test_blank_lines_are_skipped():
    rows = parse_timetable_csv(_csv("Mon,1,Math,2 A", ",,,"))
    assert len(rows) == 1


def test_header_case_mismatch_is_rejected():
    """Headers are strict, exact-match only — this is TTEK-SMS's own
    format, not a third-party export we need to leniently accommodate."""
    csv_bytes = "day,period,subject,classes\nMon,1,Math,2 A\n".encode("utf-8")
    with pytest.raises(HTTPException) as exc:
        parse_timetable_csv(csv_bytes)
    assert exc.value.status_code == 422


def test_extra_unrecognized_column_is_rejected():
    """An old FET-shaped export (Teacher(s)/Room(s) columns) must not
    silently partially parse — it's rejected like any other malformed
    file."""
    csv_bytes = "Day,Period,Subject,Classes,Teacher(s)\nMon,1,Math,2 A,Mr X\n".encode("utf-8")
    with pytest.raises(HTTPException) as exc:
        parse_timetable_csv(csv_bytes)
    assert exc.value.status_code == 422
    assert "Day, Period, Subject, Classes" in exc.value.detail
