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

# report_card.html's Grade Interpretation section always starts a fresh page
# (CSS `break-before: page`), so a 2-page document means report content fit
# on page 1. Tried in order — "normal" first since it's what almost every
# student's subject load actually needs; "compact"/"dense" only pay their
# extra render cost for the minority whose content overflows.
_DENSITY_TIERS = ("normal", "compact", "dense")


def render_report_card(context: dict) -> bytes:
    """
    Render a report card to PDF bytes.

    Fits the report to exactly 2 pages (report content, then the Grade
    Interpretation legend) when possible: renders at "normal" density,
    and if the actual output comes out longer than 2 pages, re-renders at
    a more compact CSS tier and checks again — measuring the real rendered
    page count rather than guessing from a row-count heuristic. Real
    academic data is never truncated to force a page count: if even the
    densest tier still overflows, that render is returned as-is instead of
    hiding scores or looping forever.

    Args:
        context: The assembled context dict (as returned by report_card.assemble).
                 One unified template regardless of school type — is_early_years in the
                 context switches the milestone-vs-numeric section, not a separate file.

    Returns:
        Raw PDF bytes ready to stream in an HTTP response.
    """
    tmpl = _env.get_template("report_card.html")
    document = None
    for density in _DENSITY_TIERS:
        html_str = tmpl.render(**context, density=density)
        document = HTML(string=html_str, base_url=str(TEMPLATE_DIR)).render()
        if len(document.pages) <= 2:
            break
    return document.write_pdf()


def render_transcript(context: dict) -> bytes:
    """Render a student's full multi-term transcript to PDF bytes.

    Unlike render_report_card, there's no format branching — one unified
    template spans a student's whole history regardless of BASIC/SHS.
    """
    tmpl = _env.get_template("transcript.html")
    html_str = tmpl.render(**context)
    return HTML(string=html_str, base_url=str(TEMPLATE_DIR)).write_pdf()


def render_export_table(
    school, title: str, headers: list[str], rows: list[list[str]], generated_at: str, total: int,
) -> bytes:
    """Render an arbitrary headers/rows table (a custom export's resolved
    field selection) to PDF bytes — shared by the staff and student custom
    export paths so PDF output doesn't need its own entity-specific
    template the way the old fixed staff-only export did."""
    tmpl = _env.get_template("export_table.html")
    html_str = tmpl.render(school=school, title=title, headers=headers, rows=rows, generated_at=generated_at, total=total)
    return HTML(string=html_str, base_url=str(TEMPLATE_DIR)).write_pdf()
