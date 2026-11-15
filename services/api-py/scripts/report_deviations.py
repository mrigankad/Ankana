"""Report how far a provider deviates from the reference cases.

    python scripts/report_deviations.py                      # astronomy vs references (text)
    python scripts/report_deviations.py --provider swiss     # swiss vs references
    python scripts/report_deviations.py --markdown ../../docs/engine-accuracy-tables.md
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "reference"))

import runner  # noqa: E402

from nakshatra_core.providers import get_provider  # noqa: E402

A = runner.ARCSEC


def _exp_longitudes(case: dict, provider) -> dict:
    utc = runner.birth_utc(case)
    return {"moon_trop": provider.planet("moon", utc).longitude}


def detail(provider_name: str) -> list[dict]:
    """Per-case deviations of `provider_name` against the stored (Swiss) expected values."""
    provider = get_provider(provider_name)
    swiss = get_provider("swiss")
    rows = []
    for case in runner.load_cases():
        utc = runner.birth_utc(case)
        i = case["input"]
        actual = runner.compute(case, provider)
        exp = case["expected"]
        g = runner._gap
        # tropical Moon, isolates the planet engine from the ayanamsa
        moon_trop = g(provider.planet("moon", utc).longitude, swiss.planet("moon", utc).longitude)
        # sunrise convention-matched ("standard" on both) isolates engine error from the rule
        std = swiss.sunrise_sunset(utc, i["latitude"], i["longitude"], "standard")
        mine = provider.sunrise_sunset(utc, i["latitude"], i["longitude"], "standard")
        # dasha start instants, exact (days, fractional)
        d_exp = runner.dasha_start_instants(exp["planets"]["moon"], utc)
        d_act = runner.dasha_start_instants(actual["planets"]["moon"], utc)
        drift = [(a - e).total_seconds() / 86400 for a, e in zip(d_act, d_exp, strict=True)]
        devs = {d.field: d for d in runner.compare(case, actual)}
        rows.append({
            "id": case["id"],
            "moon_trop": moon_trop * A,
            "ayanamsa": g(actual["ayanamsa"], exp["ayanamsa"]) * A,
            "moon_sid": devs["moon"].value,
            "asc": devs["ascendant"].value,
            "rahu": devs["rahu"].value,
            "max_planet": max(abs(devs[b].value) for b in runner.BODIES if b != "moon"),
            "sunrise_std": (mine[0] - std[0]).total_seconds(),
            "sunrise_hindu": devs["sunrise"].value,
            "dasha_first": drift[0],
            "dasha_max": max(drift, key=abs),
            "fails": [d.field for d in devs.values() if not d.ok],
        })
    return rows


def text(rows: list[dict]) -> str:
    cols = ["moon_trop", "ayanamsa", "moon_sid", "asc", "rahu", "max_planet", "sunrise_std",
            "sunrise_hindu", "dasha_first", "dasha_max"]
    out = ["id".ljust(24) + "".join(c.rjust(14) for c in cols)]
    for r in rows:
        out.append(r["id"].ljust(24) + "".join(f"{r[c]:14.2f}" for c in cols))
    return "\n".join(out)


def markdown(rows: list[dict], provider_name: str) -> str:
    lines = [
        f"Provider `{provider_name}` vs Swiss Ephemeris reference (arcsec unless noted, signed "
        "provider minus reference).",
        "",
        "| Case | Moon tropical | Ayanamsa | Moon sidereal | Asc | Mean node | Worst other planet |"
        " Sunrise std-vs-std (s) | Sunrise vs Hindu (s) | Dasha start drift first / worst (days) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['id']} | {r['moon_trop']:.2f} | {r['ayanamsa']:.2f} | {r['moon_sid']:.2f} | "
            f"{r['asc']:.2f} | {r['rahu']:.2f} | {r['max_planet']:.2f} | "
            f"{r['sunrise_std']:.1f} | {r['sunrise_hindu']:.1f} | "
            f"{r['dasha_first']:.2f} / {r['dasha_max']:.2f} |"
        )

    def col(k: str) -> tuple[float, float]:
        vals = [abs(r[k]) for r in rows]
        return sum(vals) / len(vals), max(vals)

    lines += ["", "| Field | Mean abs | Max abs |", "|---|---|---|"]
    for label, k in [("Moon tropical (arcsec)", "moon_trop"), ("Ayanamsa (arcsec)", "ayanamsa"),
                     ("Moon sidereal (arcsec)", "moon_sid"), ("Ascendant (arcsec)", "asc"),
                     ("Mean node (arcsec)", "rahu"), ("Worst other planet (arcsec)", "max_planet"),
                     ("Sunrise standard rule (s)", "sunrise_std"),
                     ("Sunrise vs Hindu rule (s)", "sunrise_hindu"),
                     ("Vimshottari first start (days)", "dasha_first"),
                     ("Vimshottari worst start (days)", "dasha_max")]:
        m, x = col(k)
        lines.append(f"| {label} | {m:.2f} | {x:.2f} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="astronomy")
    ap.add_argument("--markdown", help="write markdown tables to this file")
    args = ap.parse_args()
    rows = detail(args.provider)
    print(text(rows))
    failing = {r["id"]: r["fails"] for r in rows if r["fails"]}
    print(f"\n{len(rows) - len(failing)}/{len(rows)} cases within all tolerances")
    for cid, fields in failing.items():
        print(f"  {cid}: {', '.join(fields)}")
    if args.markdown:
        Path(args.markdown).write_text(markdown(rows, args.provider), encoding="utf-8")
        print("wrote", args.markdown, datetime.now().isoformat(timespec="seconds"))


if __name__ == "__main__":
    main()
