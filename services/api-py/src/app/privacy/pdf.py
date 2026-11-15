"""A dependency-free text PDF for the export summary.

Why not Chromium: exports run in the worker for every request and must not depend
on a browser being installed. This writes a plain multi-page A4 document using the
built-in Helvetica font. Limitation: WinAnsi only, so Devanagari and other scripts
print as "?" in the PDF; the JSON files in the same ZIP hold the exact text.
"""

from __future__ import annotations

import textwrap

PAGE_W, PAGE_H = 595, 842
MARGIN = 54
LEADING = 13
LINES_PER_PAGE = (PAGE_H - 2 * MARGIN) // LEADING


def _esc(s: str) -> bytes:
    b = s.encode("cp1252", errors="replace")
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def text_pdf(title: str, lines: list[str], width: int = 92) -> bytes:
    wrapped: list[tuple[str, bool]] = [(title, True), ("", False)]
    for line in lines:
        if not line:
            wrapped.append(("", False))
            continue
        bold = line.startswith("## ")
        content = line[3:] if bold else line
        for i, part in enumerate(textwrap.wrap(content, width, subsequent_indent="    ",
                                               break_long_words=True) or [""]):
            wrapped.append((part, bold and i == 0))
    pages = [wrapped[i:i + LINES_PER_PAGE] for i in range(0, len(wrapped), LINES_PER_PAGE)]

    objs: list[bytes] = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                         b"/Encoding /WinAnsiEncoding >>",
                         b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
                         b"/Encoding /WinAnsiEncoding >>"]
    kids = []
    for page in pages:
        ops = [b"BT", f"{MARGIN} {PAGE_H - MARGIN} Td".encode(), f"{LEADING} TL".encode()]
        for text, bold in page:
            font = b"/F2 11" if bold else b"/F1 9.5"
            ops.append(font + b" Tf (" + _esc(text) + b") '")
        ops.append(b"ET")
        stream = b"\n".join(ops)
        content_id = len(objs) + 2  # objects are 1-indexed; page object comes first
        page_id = len(objs) + 1
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_id} 0 R >>"
            .encode())
        objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream
                    + b"\nendstream")
        kids.append(page_id)
    objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[1] = (b"<< /Type /Pages /Count " + str(len(kids)).encode() + b" /Kids ["
               + b" ".join(f"{k} 0 R".encode() for k in kids) + b"] >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
            .encode())
    return bytes(out)
