"""
PDF rendering service.

Flow: Jinja2 renders the context dict into HTML → WeasyPrint converts to PDF bytes.
Templates live in backend/app/templates/.
Report cards are NEVER written to disk — bytes are returned and streamed directly.
"""
from __future__ import annotations
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)

_TEMPLATE_MAP = {
    "BASIC": "report_basic.html",
    "SHS": "report_shs.html",
    "ECM": "report_ecm.html",
}


def render_report_card(context: dict, format: str) -> bytes:
    """
    Render a report card to PDF bytes.

    Args:
        context: The assembled ReportCardData dict (as returned by report_card.assemble).
        format:  "BASIC" | "SHS" | "ECM"

    Returns:
        Raw PDF bytes ready to stream in an HTTP response.

    Raises:
        ValueError: Unknown format string.
    """
    template_name = _TEMPLATE_MAP.get(format.upper())
    if not template_name:
        raise ValueError(f"Unknown report card format: {format!r}. Choose BASIC, SHS, or ECM.")
    tmpl = _env.get_template(template_name)
    html_str = tmpl.render(**context)
    return HTML(string=html_str, base_url=str(TEMPLATE_DIR)).write_pdf()
