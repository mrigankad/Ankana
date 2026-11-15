"""GST helpers: GSTIN validation, state codes, financial year, tax split.

Money is integer paise everywhere. Rounding rules (also printed on invoices):
1. The provider charges a tax-inclusive amount. The taxable value is recovered
   as round_half_up(total * 10000 / (10000 + rate_bp)); tax = total - taxable,
   so taxable + tax always equals the amount actually paid, to the paisa.
2. Intra-state supply: CGST = tax // 2 and SGST = tax - CGST. They are equal
   whenever tax is even (it is for every catalogue price; asserted in tests);
   an odd paisa, if one ever occurs, goes to SGST.
3. Inter-state supply: IGST = tax.
4. There is no separate round-off line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
SAC_SAAS = "998314"  # TO CONFIRM with a CA: SaaS may be 998314, 998315 or 997331.

STATE_CODES: dict[str, str] = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan",
    "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh",
    "13": "Nagaland", "14": "Manipur", "15": "Mizoram", "16": "Tripura", "17": "Meghalaya",
    "18": "Assam", "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
    "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra",
    "28": "Andhra Pradesh (before division)", "29": "Karnataka", "30": "Goa",
    "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh",
    "38": "Ladakh", "97": "Other Territory", "99": "Centre Jurisdiction",
}

_GSTIN_RE = re.compile(r"^(\d{2})[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class GstError(ValueError):
    pass


def gstin_checksum(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        v = _ALPHABET.index(ch) * (1 if i % 2 == 0 else 2)
        total += v // 36 + v % 36
    return _ALPHABET[(36 - total % 36) % 36]


def validate_gstin(value: str) -> str:
    """Return the normalised GSTIN or raise GstError (format, state code, checksum)."""
    g = (value or "").strip().upper()
    m = _GSTIN_RE.match(g)
    if not m:
        raise GstError("GSTIN must be 15 characters in the official format")
    if m.group(1) not in STATE_CODES:
        raise GstError("GSTIN has an unknown state code")
    if gstin_checksum(g[:14]) != g[14]:
        raise GstError("GSTIN check character does not match")
    return g


def validate_state_code(code: str) -> str:
    c = (code or "").strip()
    if c not in STATE_CODES:
        raise GstError("unknown GST state code")
    return c


def round_half_up_div(numer: int, denom: int) -> int:
    return (2 * numer + denom) // (2 * denom)


def tax_on(taxable_paise: int, rate_bp: int) -> int:
    return round_half_up_div(taxable_paise * rate_bp, 10_000)


@dataclass(frozen=True)
class TaxSplit:
    taxable: int
    cgst: int
    sgst: int
    igst: int
    total: int
    intra_state: bool

    @property
    def tax(self) -> int:
        return self.cgst + self.sgst + self.igst


def split_inclusive(total_paise: int, rate_bp: int, supplier_state: str,
                    place_of_supply: str) -> TaxSplit:
    taxable = round_half_up_div(total_paise * 10_000, 10_000 + rate_bp)
    tax = total_paise - taxable
    intra = supplier_state == place_of_supply
    if intra:
        cgst = tax // 2
        return TaxSplit(taxable, cgst, tax - cgst, 0, total_paise, True)
    return TaxSplit(taxable, 0, 0, tax, total_paise, False)


def financial_year(at: datetime) -> str:
    """Indian FY (1 April to 31 March, judged in IST) as a 4 digit label, e.g. 2627."""
    d = at.astimezone(IST) if at.tzinfo else at.replace(tzinfo=UTC).astimezone(IST)
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


def financial_year_long(label: str) -> str:
    return f"20{label[:2]}-{label[2:]}"
