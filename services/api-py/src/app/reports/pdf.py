"""HTML -> PDF with Python Playwright (Chromium).

Isolation: JavaScript is disabled and every network request is aborted, so the
renderer can only see the self-contained HTML it was given (fonts and logo are
embedded). One browser per render; the worker caps concurrency.
"""

from __future__ import annotations

from html import escape

from .branding import Branding

AGPL_LINE = "Prepared with Ankana · open source under AGPL-3.0"


def footer_template(branding: Branding) -> str:
    left = escape(branding.footer or branding.name)
    colour = escape(branding.primary)
    return (
        '<div style="width:100%;padding:0 12mm;font-size:8px;color:#64748b;'
        'font-family:sans-serif;display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="color:{colour};font-weight:600;">{left}</span>'
        f'<span>{escape(AGPL_LINE)}</span>'
        '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span>'
        "</div>"
    )


def header_template(branding: Branding, title: str) -> str:
    return (
        '<div style="width:100%;padding:0 12mm;font-size:8px;font-family:sans-serif;'
        f'color:{escape(branding.primary)};">{escape(branding.name)} · {escape(title)}</div>'
    )


def _stub_pdf(title: str) -> bytes:
    """Minimal valid one-page PDF for hermetic CI (REPORT_RENDERER=stub); no Chromium needed."""
    safe = "".join(c for c in title if c.isascii() and c not in "()\\") or "Report"
    stream = f"BT /F1 18 Tf 72 760 Td ({safe}) Tj ET".encode("ascii")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def html_to_pdf(html: str, branding: Branding, title: str) -> bytes:
    import os

    if os.environ.get("REPORT_RENDERER") == "stub":
        return _stub_pdf(title)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"] if _in_container() else [])
        try:
            context = browser.new_context(java_script_enabled=False)
            page = context.new_page()
            page.route("**/*", lambda route: route.continue_()
                       if route.request.url.startswith(("data:", "about:"))
                       else route.abort())
            page.set_content(html, wait_until="load")
            return page.pdf(
                format="A4", print_background=True, display_header_footer=True,
                header_template=header_template(branding, title),
                footer_template=footer_template(branding),
                margin={"top": "16mm", "bottom": "18mm", "left": "14mm", "right": "14mm"},
            )
        finally:
            browser.close()


def _in_container() -> bool:
    import os

    return os.path.exists("/.dockerenv")
