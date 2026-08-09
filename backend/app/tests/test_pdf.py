"""
Report card PDF rendering — the fit-to-page density tier loop.
Run inside Docker: docker compose exec api pytest app/tests/test_pdf.py -v

render_report_card() renders at "normal" density first and only re-renders
at a more compact tier if the actual output overflows 2 pages (report
content + the Grade Interpretation page, which always starts a fresh page
via CSS). These tests build synthetic contexts directly — no DB needed,
since rendering only depends on the plain dict services/report_card.py
already assembles — to prove the loop actually measures and shrinks rather
than just always picking the first tier.
"""
from decimal import Decimal
from unittest import mock

import weasyprint

from app.services import pdf as pdf_module


def _subject_group(name: str, n_rows: int) -> dict:
    rows = [
        {
            "type_name": f"Category {i}", "subject_name": name,
            "raw_score": Decimal("15.00"), "max_score": Decimal("20.00"),
            "cached_grade_label": "B2",
        }
        for i in range(n_rows)
    ]
    return {"subject_name": name, "rows": rows, "total": Decimal("75.00"), "grade": "B2"}


def _context(subject_groups: list[dict]) -> dict:
    return {
        "enrollment_id": "test-enrollment",
        "student_name": "Test Student",
        "admission_number": "TEST001",
        "class_name": "SHS 1 A",
        "term_name": "Term 1",
        "academic_year_name": "2025/2026",
        "class_teacher_name": "Test Teacher",
        "school_name": "Test School",
        "school_phone": None,
        "school_email": None,
        "school_address": None,
        "brand_color": "#1e40af",
        "logo_url": None,
        "photo_url": None,
        "is_early_years": False,
        "grade_legend": [
            {"letter_grade": "A1", "gpa_points": None, "min_score": Decimal("80"), "max_score": Decimal("100"), "label": "Excellent"},
            {"letter_grade": "F9", "gpa_points": None, "min_score": Decimal("0"), "max_score": Decimal("44.99"), "label": "Fail"},
        ],
        "subject_groups": subject_groups,
        "scores": [],
        "subject_weighted": {},
        "total_score": Decimal("0"),
        "max_possible": Decimal("0"),
        "rank": 1,
        "class_size": 1,
        "days_present": 0,
        "total_school_days": 0,
        "behaviour_records": [],
        "qr_token": "test-token",
        "qr_image": (
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
            "AAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        ),
    }


def _spy_html_class(page_counts: list[int]) -> type:
    """A weasyprint.HTML subclass that records each render()'s page count —
    lets a test observe how many density tiers render_report_card() tried
    without needing a separate PDF-parsing dependency."""
    real_render = weasyprint.HTML.render

    class _SpyHTML(weasyprint.HTML):
        def render(self, *args, **kwargs):
            document = real_render(self, *args, **kwargs)
            page_counts.append(len(document.pages))
            return document

    return _SpyHTML


def test_render_report_card_small_content_fits_in_one_pass():
    context = _context([_subject_group("Mathematics", 4), _subject_group("English", 3)])
    page_counts: list[int] = []
    with mock.patch.object(pdf_module, "HTML", _spy_html_class(page_counts)):
        pdf_bytes = pdf_module.render_report_card(context)

    assert pdf_bytes.startswith(b"%PDF")
    assert page_counts == [2], "a normal subject load must fit in 2 pages on the first (normal-density) attempt"


def test_render_report_card_shrinks_density_for_large_content():
    # 40 subjects x 5 categories each — enough to overflow one A4 page at
    # normal density, forcing the loop to try a more compact tier.
    context = _context([_subject_group(f"Subject {i}", 5) for i in range(40)])
    page_counts: list[int] = []
    with mock.patch.object(pdf_module, "HTML", _spy_html_class(page_counts)):
        pdf_bytes = pdf_module.render_report_card(context)

    assert pdf_bytes.startswith(b"%PDF")
    assert page_counts[0] > 2, "this synthetic content must genuinely overflow normal density for the test to prove anything"
    assert len(page_counts) > 1, "must have tried a denser tier rather than giving up after the first attempt"
