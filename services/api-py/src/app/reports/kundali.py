"""South Indian kundali as inline SVG: signs are fixed in the grid, the lagna
sign is marked, planets are listed in their sign boxes."""

from __future__ import annotations

from html import escape

from .i18n import PLANET_ABBR, SIGNS

# sign index (0=Aries) -> (col, row) in the 4x4 grid; centre 2x2 is empty.
_POS = {
    11: (0, 0), 0: (1, 0), 1: (2, 0), 2: (3, 0),
    10: (0, 1), 3: (3, 1),
    9: (0, 2), 4: (3, 2),
    8: (0, 3), 7: (1, 3), 6: (2, 3), 5: (3, 3),
}


def south_indian_svg(artifact: dict, lang: str, primary: str, size: int = 420) -> str:
    cell = size / 4
    abbr = PLANET_ABBR[lang]
    by_sign: dict[int, list[str]] = {i: [] for i in range(12)}
    by_sign[artifact["ascendant"]["signIndex"]].append(abbr["asc"])
    for p in artifact["planets"]:
        label = abbr[p["planet"]] + ("ʳ" if p.get("retrograde") else "")
        by_sign[p["signIndex"]].append(label)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
             f'width="{size}" height="{size}" class="kundali">']
    for sign, (c, r) in _POS.items():
        x, y = c * cell, r * cell
        is_lagna = sign == artifact["ascendant"]["signIndex"]
        fill = "#ffe7e1" if is_lagna else "#ffffff"
        parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{fill}" '
                     f'stroke="{escape(primary)}" stroke-width="1.5"/>')
        parts.append(f'<text x="{x + 6}" y="{y + 15}" font-size="10" fill="#6c6866">'
                     f'{escape(SIGNS[lang][sign])}</text>')
        items = by_sign[sign]
        for i, label in enumerate(items):
            col, row = i % 3, i // 3
            parts.append(
                f'<text x="{x + 12 + col * 30}" y="{y + 42 + row * 22}" font-size="15" '
                f'font-weight="600" fill="{escape(primary)}">{escape(label)}</text>')
    parts.append(f'<text x="{size / 2}" y="{size / 2}" text-anchor="middle" font-size="16" '
                 f'font-weight="700" fill="{escape(primary)}">{"राशि" if lang == "hi" else "Rashi"}</text>')
    parts.append("</svg>")
    return "".join(parts)
