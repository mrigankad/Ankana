"""Invoice HTML and PDF. Reuses the report pipeline: Jinja2 to a self-contained
HTML page (Urbanist embedded), then app.reports.pdf.html_to_pdf (Chromium with
network and JavaScript disabled)."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.reports.branding import Branding
from app.reports.html import _font_css

from .gst import IST, STATE_CODES, financial_year_long
from .models import Invoice, InvoiceLine

_env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"),
                   autoescape=select_autoescape(["html", "j2"]), trim_blocks=True,
                   lstrip_blocks=True)

INK = "#221e1d"
ACCENT = "#d32704"
BRANDING = Branding("Ankana", None, INK, ACCENT, "Ankana")


def inr(paise: int) -> str:
    """12345678 -> '1,23,456.78' (Indian digit grouping)."""
    rupees, p = divmod(abs(int(paise)), 100)
    s = str(rupees)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join([*groups, tail])
    return f"{'-' if paise < 0 else ''}{s}.{p:02d}"


_env.filters["inr"] = inr


def state_name(code: str | None) -> str:
    return f"{STATE_CODES.get(code or '', 'Not provided')} ({code})" if code else "Not provided"


def render_invoice_html(inv: Invoice, lines: list[InvoiceLine]) -> str:
    return _env.get_template("invoice.html.j2").render(
        inv=inv, lines=lines, font_css=_font_css("en"), ink=INK, accent=ACCENT,
        fy_long=financial_year_long(inv.fy),
        issued=inv.issued_at.astimezone(IST).strftime("%d %b %Y"), place_name=state_name(inv.place_of_supply),
        supplier=inv.supplier, recipient=inv.recipient,
        recipient_state=state_name(inv.recipient.get("state_code")))


def invoice_filename(number: str) -> str:
    return "invoice-" + number.replace("/", "-") + ".pdf"
