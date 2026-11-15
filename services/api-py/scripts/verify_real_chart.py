"""Verify the engine against a real chart whose values were read from other software.

    python scripts/verify_real_chart.py tests/real/public/einstein-1879.json
    python scripts/verify_real_chart.py tests/real/private/mriganka.json --engines
    python scripts/verify_real_chart.py CASE.json --provider astronomy --markdown out.md --json

A case file holds the birth input, the settings used in the other software and
the `observed` values typed in by hand (see tests/real/README.md and
tests/real/observed.schema.json). Output: a pass/fail table of differences
(arcminutes for longitudes, days for dasha dates), likely causes for every
failure, a birth-time sensitivity table, and with --engines a comparison of the
independent engines (swiss, astronomy, and jyotishganit when installed).

Exit status: 0 all observed values pass, 1 at least one fails, 2 case file
invalid, 3 observed values still pending.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import statistics
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nakshatra_core.dasha_vimshottari import compute_vimshottari  # noqa: E402
from nakshatra_core.ephemeris import SEVEN_BODIES, normalize_degrees  # noqa: E402
from nakshatra_core.provenance import ephemeris_provenance  # noqa: E402
from nakshatra_core.providers import NotSupportedError, get_provider  # noqa: E402
from nakshatra_core.sensitivity import sensitivity_report, state_at, utc_of  # noqa: E402
from nakshatra_core.zodiac import NAKSHATRA_NAMES, NAKSHATRA_SPAN, SIGN_NAMES  # noqa: E402

BODIES = (*SEVEN_BODIES, "rahu", "ketu")
ENTITIES = ("lagna", *BODIES)
DEFAULT_TOL_ARCMIN = 1.0
DASHA_TOL_DAYS = 1.0
PASS, FAIL, PENDING = "PASS", "FAIL", "-"

_SIGN_TOKENS: dict[str, int] = {}
for _i, _n in enumerate(SIGN_NAMES):
    _SIGN_TOKENS[_n.lower()] = _i
    _SIGN_TOKENS[_n[:2].lower()] = _i
    _SIGN_TOKENS[_n[:3].lower()] = _i
for _i, _n in enumerate(("mesha", "vrishabha", "mithuna", "karka", "simha", "kanya", "tula",
                         "vrischika", "dhanu", "makara", "kumbha", "meena")):
    _SIGN_TOKENS[_n] = _i
_SIGN_TOKENS.update({"cn": 3, "sg": 8, "sa": 8, "cp": 9, "aq": 10, "vir": 5})

_NAK_ALIASES = {
    "aswini": "ashwini", "mrigasira": "mrigashira", "mrigasiras": "mrigashira",
    "arudra": "ardra", "aslesha": "ashlesha", "ashlesa": "ashlesha", "poorvaphalguni": "purvaphalguni",
    "pubba": "purvaphalguni", "uttaraphalguni": "uttaraphalguni", "uttara": "uttaraphalguni",
    "svati": "swati", "visakha": "vishakha", "jyestha": "jyeshtha", "jyeshta": "jyeshtha",
    "moola": "mula", "mool": "mula", "poorvashadha": "purvaashadha", "purvashadha": "purvaashadha",
    "purvaashadha": "purvaashadha", "uttarashadha": "uttaraashadha", "uttaraashadha": "uttaraashadha",
    "sravana": "shravana", "sravan": "shravana", "dhanista": "dhanishta", "dhanishtha": "dhanishta",
    "satabhisha": "shatabhisha", "shatabhishaj": "shatabhisha", "satabhishak": "shatabhisha",
    "poorvabhadrapada": "purvabhadrapada", "purvabhadra": "purvabhadrapada",
    "uttarabhadra": "uttarabhadrapada", "uttarabhadrapada": "uttarabhadrapada",
}


def _nak_key(name: str) -> str:
    key = re.sub(r"[^a-z]", "", name.lower().replace("u.", "uttara").replace("p.", "purva"))
    return _NAK_ALIASES.get(key, key)


_NAK_BY_KEY = {_nak_key(n): n for n in NAKSHATRA_NAMES}


# ----------------------------------------------------------------- parsing
def parse_longitude(value) -> tuple[float, int | None]:
    """Hand-entered longitude -> (absolute degrees, sign index or None).

    Accepts a number (degrees), "14.9667", "14°58'", "14:58:12", "Sc 14°58'12\"",
    "14 58 Scorpio". With a sign the degrees are within the sign; without, absolute.
    """
    if isinstance(value, int | float):
        return float(value) % 360, None
    text = str(value).strip()
    sign = None
    for tok in re.findall(r"[A-Za-z]+", text):
        if tok.lower() in _SIGN_TOKENS:
            sign = _SIGN_TOKENS[tok.lower()]
            break
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", text)]
    if not nums:
        raise ValueError(f"cannot parse longitude {value!r}")
    deg = nums[0] + (nums[1] / 60 if len(nums) > 1 else 0) + (nums[2] / 3600 if len(nums) > 2 else 0)
    if sign is not None:
        if deg >= 30:
            raise ValueError(f"{value!r}: degrees within a sign must be under 30")
        return sign * 30 + deg, sign
    return deg % 360, None


def parse_date(text: str) -> datetime:
    text = text.strip()[:10]
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        y, m, d = (int(x) for x in text.split("-"))
    else:
        d, m, y = (int(x) for x in re.split(r"[-/.]", text))
    return datetime(y, m, d, tzinfo=UTC)


def deg_to_dms(deg: float) -> str:
    sign, rem = divmod(deg % 360, 30)
    d = int(rem)
    m_full = (rem - d) * 60
    m = int(m_full)
    s = (m_full - m) * 60
    return f"{SIGN_NAMES[int(sign)][:3]} {d:02d}°{m:02d}'{s:04.1f}\""


def arcmin_gap(a: float, b: float) -> float:
    """Signed shortest a - b in arcminutes."""
    return ((a - b + 180) % 360 - 180) * 60


# ------------------------------------------------------------- case loading
def load_case(path: Path) -> dict:
    case = json.loads(path.read_text(encoding="utf-8"))
    problems = validate_case(case)
    if problems:
        raise ValueError("invalid case file:\n  " + "\n  ".join(problems))
    return case


def validate_case(case: dict) -> list[str]:
    errs: list[str] = []
    for key in ("id", "consent", "source", "input", "settings", "observed"):
        if key not in case:
            errs.append(f"missing '{key}'")
    if errs:
        return errs
    inp = case["input"]
    for key in ("birthDate", "birthTime", "latitude", "longitude"):
        if key not in inp:
            errs.append(f"input.{key} missing")
    if "timezoneName" not in inp and "utcOffset" not in inp:
        errs.append("input needs timezoneName or utcOffset")
    if case["settings"].get("ayanamsa") not in ("lahiri", "raman", "kp", "true_chitra"):
        errs.append("settings.ayanamsa must be lahiri|raman|kp|true_chitra")
    if case["settings"].get("node") not in ("mean", "true"):
        errs.append("settings.node must be mean|true")
    obs = case["observed"]
    if obs.get("status") not in ("pending", "entered"):
        errs.append("observed.status must be pending|entered")
    if obs.get("status") == "entered":
        if "ascendant" not in obs and not obs.get("planets"):
            errs.append("observed.status is 'entered' but no ascendant/planets given")
        for name, val in (obs.get("planets") or {}).items():
            if name not in BODIES:
                errs.append(f"observed.planets.{name}: unknown body")
            try:
                parse_longitude(val["longitude"] if isinstance(val, dict) else val)
            except (ValueError, KeyError) as exc:
                errs.append(f"observed.planets.{name}: {exc}")
    return errs


def _observed_entities(case: dict) -> dict[str, dict]:
    """{entity: {'lon', 'sign', 'nakshatra', 'pada'}} from the hand-entered values."""
    obs = case["observed"]
    out: dict[str, dict] = {}
    raw = dict(obs.get("planets") or {})
    if "ascendant" in obs:
        raw["lagna"] = obs["ascendant"]
    for name, val in raw.items():
        cell = val if isinstance(val, dict) else {"longitude": val}
        lon, sign = parse_longitude(cell["longitude"])
        out[name] = {"lon": lon, "sign": sign, "nakshatra": cell.get("nakshatra"),
                     "pada": cell.get("pada")}
    return out


# --------------------------------------------------------------- computation
@contextlib.contextmanager
def _mean_ayanamsa(provider, flag: bool):
    old = getattr(provider, "mean_ayanamsa", None)
    if old is not None:
        provider.mean_ayanamsa = flag
    try:
        yield
    finally:
        if old is not None:
            provider.mean_ayanamsa = old


def settings_input(case: dict) -> dict:
    s = case["settings"]
    return {**case["input"], "ayanamsa": s["ayanamsa"], "nodeType": s["node"]}


def compute_case(provider, case: dict, shift_minutes: float = 0.0, settings: dict | None = None
                 ) -> dict:
    s = {**case["settings"], **(settings or {})}
    inp = {**case["input"], "ayanamsa": s["ayanamsa"], "nodeType": s["node"]}
    utc = utc_of(inp) + timedelta(minutes=shift_minutes)
    with _mean_ayanamsa(provider, bool(s.get("ayanamsaMean", False))):
        lon, _ = state_at(provider, utc, inp)
        aya = provider.ayanamsa(utc, s["ayanamsa"])
    return {"utc": utc, "lon": lon, "ayanamsa": aya}


def dasha_starts(moon_lon: float, utc: datetime) -> dict[str, datetime]:
    out = compute_vimshottari(moon_lon, utc)
    return {m["planet"]: parse_date(m["start"]) for m in out["mahadashas"]}


# ------------------------------------------------------------------ compare
def compare(provider, case: dict, tol: float) -> dict:
    comp = compute_case(provider, case)
    observed = _observed_entities(case)
    rows = []
    for name in ENTITIES:
        if name not in observed:
            continue
        o = observed[name]
        c = comp["lon"][name]
        diff = arcmin_gap(c, o["lon"])
        notes = []
        ok = abs(diff) <= tol
        if o["sign"] is not None and int(c // 30) != o["sign"]:
            ok = False
            notes.append(f"sign {SIGN_NAMES[int(c // 30)]} vs {SIGN_NAMES[o['sign']]}")
        if o["nakshatra"]:
            comp_nak = NAKSHATRA_NAMES[int(c // NAKSHATRA_SPAN)]
            want = _NAK_BY_KEY.get(_nak_key(o["nakshatra"]))
            if want is None:
                notes.append(f"nakshatra {o['nakshatra']!r} not recognised")
            elif want != comp_nak:
                ok = False
                notes.append(f"nakshatra {comp_nak} vs {want}")
        if o["pada"] is not None and int(c % NAKSHATRA_SPAN // (NAKSHATRA_SPAN / 4)) + 1 != int(
                o["pada"]):
            ok = False
            notes.append(
                f"pada {int(c % NAKSHATRA_SPAN // (NAKSHATRA_SPAN / 4)) + 1} vs {o['pada']}")
        rows.append({"item": name, "observed": o["lon"], "computed": c, "diff_arcmin": diff,
                     "status": PASS if ok else FAIL, "notes": notes})
    obs_aya = case["observed"].get("ayanamsa")
    if obs_aya is not None:
        a_obs = parse_longitude(obs_aya)[0]
        diff = arcmin_gap(comp["ayanamsa"], a_obs)
        rows.append({"item": "ayanamsa", "observed": a_obs, "computed": comp["ayanamsa"],
                     "diff_arcmin": diff, "status": PASS if abs(diff) <= tol else FAIL,
                     "notes": [], "plain": True})
    dasha_rows = []
    starts = dasha_starts(comp["lon"]["moon"], comp["utc"])
    for d in case["observed"].get("vimshottari") or []:
        planet = d["planet"].lower()
        if planet not in starts:
            continue
        days = (starts[planet] - parse_date(d["start"])).days
        dasha_rows.append({"planet": planet, "observed": parse_date(d["start"]).date().isoformat(),
                           "computed": starts[planet].date().isoformat(), "diff_days": days,
                           "status": PASS if abs(days) <= DASHA_TOL_DAYS else FAIL})
    return {"rows": rows, "dasha": dasha_rows, "computed": comp, "observed": observed,
            "tol": tol}


# -------------------------------------------------------------------- causes
def diagnose(provider, case: dict, result: dict) -> list[str]:
    tol = result["tol"]
    rows = [r for r in result["rows"] if r["item"] != "ayanamsa"]
    bad = [r for r in rows if r["status"] == FAIL]
    dasha_bad = [d for d in result["dasha"] if d["status"] == FAIL]
    if not bad and not dasha_bad:
        return []
    causes: list[str] = []
    by = {r["item"]: r["diff_arcmin"] for r in rows}
    observed = result["observed"]
    cur = case["settings"]

    # 1. settings fit: other ayanamsa / mean-vs-nutation / node type reproduce the observation?
    fits = []
    for aya in getattr(provider, "ayanamsas", ("lahiri",)):
        for mean in (False, True):
            for node in ("mean", "true"):
                if (aya, mean, node) == (cur["ayanamsa"], bool(cur.get("ayanamsaMean", False)),
                                         cur["node"]):
                    continue
                try:
                    comp = compute_case(provider, case, settings={
                        "ayanamsa": aya, "ayanamsaMean": mean, "node": node})
                except NotSupportedError:
                    continue
                worst = max(abs(arcmin_gap(comp["lon"][n], observed[n]["lon"])) for n in observed)
                fits.append((worst, aya, mean, node))
    fits.sort()
    for worst, aya, mean, node in fits[:2]:
        if worst <= tol * 1.5:
            what = []
            if aya != cur["ayanamsa"]:
                what.append(f"ayanamsa {aya} (you stated {cur['ayanamsa']})")
            if mean != bool(cur.get("ayanamsaMean", False)):
                what.append("mean ayanamsa without nutation" if mean else
                            "ayanamsa including nutation")
            if node != cur["node"]:
                what.append(f"{node} node (you stated {cur['node']})")
            causes.append(f"SETTINGS: all observed values agree within {worst:.2f}' if the other "
                          f"software used {', '.join(what)}. Check its settings dialog.")

    # 2. node type only
    node_bad = [r for r in bad if r["item"] in ("rahu", "ketu")]
    if node_bad and len(node_bad) == len(bad):
        causes.append("NODE TYPE: only Rahu/Ketu differ (mean vs true node differ by up to ~1.7 "
                      "degrees). Confirm the node setting in the other software.")

    # 3. uniform offset on the non-node bodies = ayanamsa value difference
    planets = [by[n] for n in SEVEN_BODIES if n in by]
    if len(planets) >= 3:
        mean_d = statistics.fmean(planets)
        spread = statistics.pstdev(planets)
        if abs(mean_d) > tol and spread < max(0.7, abs(mean_d) * 0.15):
            causes.append(
                f"AYANAMSA: planets are offset by a near-constant {mean_d:+.2f}' (spread "
                f"{spread:.2f}'). That is an ayanamsa value difference: a different variant "
                "(Lahiri vs True Chitra differ by about 0.6', Lahiri vs Raman by 1.5 degrees), "
                "mean vs nutation-corrected (about 0.3'), or a different precession formula.")

    # 4. birth-time / timezone fit
    names = [n for n in observed]
    base = [arcmin_gap(result["computed"]["lon"][n], observed[n]["lon"]) for n in names]
    best = (sum(x * x for x in base), 0)
    for shift in range(-720, 721):
        if shift == 0:
            continue
        comp = compute_case(provider, case, shift_minutes=shift)
        err = sum(arcmin_gap(comp["lon"][n], observed[n]["lon"]) ** 2 for n in names)
        if err < best[0]:
            best = (err, shift)
    if best[1] != 0 and (best[0] / len(names)) ** 0.5 <= tol * 1.5:
        shift = best[1]
        hint = ""
        if min(abs(abs(shift) - v) for v in (30, 60, 90, 120)) <= 2:
            hint = " Looks like a timezone / daylight-saving error (wrong offset or DST flag)."
        elif abs(shift) <= 5:
            hint = " Looks like birth-time rounding (seconds or minutes dropped)."
        causes.append(f"BIRTH TIME: observed values fit if the birth instant were {shift:+d} "
                      f"minutes from the one used here.{hint} Also check the other software's "
                      "timezone, DST and longitude entry (1 degree of longitude = 4 minutes).")
    elif "lagna" in by and abs(by["lagna"]) > tol:
        approx = by["lagna"] / 60 * 4  # lagna moves ~1 degree per 4 minutes
        others_ok = all(r["status"] == PASS for r in rows if r["item"] not in ("lagna", "moon"))
        if others_ok:
            causes.append(
                f"LAGNA: only the ascendant (and Moon) differ; a {by['lagna']:+.1f}' lagna gap is "
                f"about {approx:+.1f} minutes of birth time or {approx / 4:+.2f} degrees of "
                "longitude. Check coordinates (place lookup), birth time and timezone.")

    # 5. sign / pada boundary sensitivity
    near = []
    for r in bad:
        lon = r["computed"]
        edge = min(lon % 30, 30 - lon % 30, lon % (NAKSHATRA_SPAN / 4),
                   NAKSHATRA_SPAN / 4 - lon % (NAKSHATRA_SPAN / 4)) * 60
        if edge <= 3 and abs(r["diff_arcmin"]) <= 6:
            near.append(f"{r['item']} ({edge:.1f}' from a boundary)")
    if near:
        causes.append("BOUNDARY: " + ", ".join(near) + " sits on a sign / nakshatra-pada edge; a "
                      "difference of a few arcminutes flips the label. Compare longitudes, not "
                      "labels.")

    # 6. dasha
    if dasha_bad:
        diffs = [d["diff_days"] for d in result["dasha"]]
        growing = len(diffs) >= 3 and abs(diffs[-1]) > abs(diffs[0]) + 2
        if growing:
            causes.append(
                "DASHA YEAR LENGTH: date differences grow along the sequence. The engine uses a "
                "365.2425-day year; JHora can use 360, 365.25 or 365.2564 days. Match the "
                "year-length option.")
        else:
            causes.append(
                "DASHA START: constant date difference. With matching Moon longitudes it is a "
                "date-reading issue (local vs UTC date: up to 1 day); with a Moon difference it "
                "follows from it (a 2.2' Moon gap moves a 20-year dasha by about 1 day).")

    if not causes and (bad or dasha_bad):
        causes.append("UNEXPLAINED: no single setting, offset or time shift reproduces the "
                      "observation. Re-check the typed values, then the coordinates; if still "
                      "unexplained this is a candidate engine bug: keep the case and open an "
                      "issue.")
    return causes


# ------------------------------------------------------------------- engines
def engine_compare(case: dict) -> dict:
    """Independent computations of the same instant: swiss, astronomy, jyotishganit."""
    inp = settings_input(case)
    utc = utc_of(inp)
    out: dict[str, dict] = {}
    for name in ("swiss", "astronomy"):
        try:
            prov = get_provider(name)
            comp = compute_case(prov, case)
            with _mean_ayanamsa(prov, bool(case["settings"].get("ayanamsaMean", False))):
                tropical = {b: normalize_degrees(prov.planet(b, utc).longitude)
                            for b in SEVEN_BODIES}
                tropical["rahu"] = prov.lunar_node(utc, case["settings"]["node"])
                tropical["lagna"] = prov.angles(utc, inp["latitude"], inp["longitude"]).ascendant
            out[name] = {"ayanamsaName": case["settings"]["ayanamsa"], "ayanamsa": comp["ayanamsa"],
                         "sidereal": comp["lon"], "tropical": tropical,
                         "info": ephemeris_provenance(prov)}
        except (NotSupportedError, ImportError) as exc:
            out[name] = {"error": str(exc)}
    jg = _jyotishganit(inp)
    if jg:
        out["jyotishganit"] = jg
    return out


def _patch_offline_spica() -> None:
    """jyotishganit downloads the Hipparcos catalogue only to read Spica (True Chitra ayanamsa).
    When that host is unreachable, substitute Spica's published Hipparcos (1997) astrometry,
    HIP 65474: RA 13h25m11.579s, Dec -11d09m40.75s, pm -42.35/-30.67 mas/yr, plx 12.44 mas.
    """
    import jyotishganit.core.astronomical as astro
    from skyfield.api import Star

    star = Star(ra_hours=13 + 25 / 60 + 11.579 / 3600, dec_degrees=-(11 + 9 / 60 + 40.75 / 3600),
                ra_mas_per_year=-42.35, dec_mas_per_year=-30.67, parallax_mas=12.44,
                radial_km_per_s=1.0)
    astro._get_spica.cache_clear()
    astro._get_spica = lambda: star


def _jyotishganit(inp: dict) -> dict | None:
    try:
        from jyotishganit import calculate_birth_chart
    except ImportError:
        return None
    if os.environ.get("ANKANA_JG_OFFLINE_SPICA"):
        _patch_offline_spica()
    try:
        local = datetime.fromisoformat(f"{inp['birthDate']}T{inp['birthTime']}:00")
        utc = utc_of(inp)
        offset_h = (local.replace(tzinfo=UTC) - utc).total_seconds() / 3600
        chart = calculate_birth_chart(local, inp["latitude"], inp["longitude"], offset_h)
    except Exception as exc:  # noqa: BLE001 - optional engine; report why it is unusable
        return {"error": f"{type(exc).__name__}: {exc}"}
    aya = float(chart.ayanamsa.value)
    sid = {}
    for p in chart.d1_chart.planets:
        sid[p.celestial_body.lower()] = SIGN_NAMES.index(p.sign) * 30 + p.sign_degrees
    house1 = chart.d1_chart.houses[0]
    sid["lagna"] = SIGN_NAMES.index(house1.sign) * 30 + house1.sign_degrees
    tropical = {k: normalize_degrees(v + aya) for k, v in sid.items()}
    return {"ayanamsaName": chart.ayanamsa.name, "ayanamsa": aya, "sidereal": sid,
            "tropical": tropical,
            "info": {"provider": "jyotishganit", "library": "skyfield + JPL DE421"}}


# ----------------------------------------------------------------- rendering
def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h)
              for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True))
    out = [line, "  ".join("-" * w for w in widths)]
    out += ["  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)) for r in rows]
    return out


def render_comparison(case: dict, result: dict, provider) -> list[str]:
    lines = [f"Case {case['id']}  [{case['consent']}]  source: "
             f"{case['source'].get('software') or case['source'].get('citation', '')}",
             f"Engine: {json.dumps(ephemeris_provenance(provider))}",
             f"Ayanamsa {case['settings']['ayanamsa']} = {result['computed']['ayanamsa']:.6f}  "
             f"node {case['settings']['node']}  UTC {result['computed']['utc'].isoformat()}",
             f"Tolerance {result['tol']}' (hand entry to the arcminute)", ""]
    table = []
    for r in result["rows"]:
        if r.get("plain"):
            obs, comp = f"{r['observed']:.4f}", f"{r['computed']:.4f}"
        else:
            obs, comp = deg_to_dms(r["observed"]), deg_to_dms(r["computed"])
        table.append([r["item"], obs, comp, f"{r['diff_arcmin']:+.2f}", r["status"],
                      "; ".join(r["notes"])])
    lines += _table(["item", "observed", "computed", "diff (arcmin)", "", "note"], table)
    if result["dasha"]:
        lines += ["", "Vimshottari mahadasha starts"]
        lines += _table(["planet", "observed", "computed", "diff (days)", ""],
                        [[d["planet"], d["observed"], d["computed"], f"{d['diff_days']:+d}",
                          d["status"]] for d in result["dasha"]])
    return lines


def render_sensitivity(rep: dict, full: bool) -> list[str]:
    lines = [f"Birth-time sensitivity (minutes of error that flip a fact; flag < "
             f"{rep['flagThresholdMinutes']:g} min; '~' = extrapolated beyond "
             f"{rep['windowMinutes']} min)"]

    def cell(c: dict | None) -> str:
        if not c or c["minMinutes"] is None:
            return "-"
        text = f"{c['minMinutes']:.1f}"
        if c["estimated"]:
            text = "~" + text
        return text + ("  <<" if c["flagged"] else "")

    rows = []
    for e in rep["entities"]:
        if not full and not any(e.get(f, {}).get("flagged") for f in ("sign", "pada", "house")) \
                and e["entity"] not in ("lagna", "moon"):
            continue
        rows.append([e["entity"], f"{e['degreesInSign']:.3f}", cell(e["sign"]), cell(e["pada"]),
                     cell(e.get("house"))])
    lines += _table(["entity", "deg in sign", "sign flips", "pada flips", "house flips"], rows)
    d = rep["dashaLord"]
    lines.append(f"Dasha lord at birth {d['lord']}: flips at {cell(d)} min; the second mahadasha "
                 f"start moves {rep['secondMahadashaStartShift']['minus10MinDays']:+.1f} / "
                 f"{rep['secondMahadashaStartShift']['plus10MinDays']:+.1f} days for "
                 "-10 / +10 min.")
    if rep["flags"]:
        lines.append("FLAGGED under 10 minutes: " + "; ".join(
            f"{f['entity']} {f['feature']} ({f['minutes']:.1f} min)" for f in rep["flags"]))
    else:
        lines.append("No fact flips within 10 minutes of birth-time error.")
    return lines


def render_engines(cmp_: dict) -> list[str]:
    lines = ["Engine comparison (sidereal under each engine's own ayanamsa; tropical isolates "
             "the ephemeris from the ayanamsa)"]
    ok = {k: v for k, v in cmp_.items() if "error" not in v}
    for k, v in cmp_.items():
        if "error" in v:
            lines.append(f"  {k}: unavailable ({v['error']})")
    lines += [f"  {k}: ayanamsa {v['ayanamsaName']} = {v['ayanamsa']:.5f}" for k, v in ok.items()]
    names = list(ok)
    ref = "swiss" if "swiss" in ok else names[0]
    rows = []
    worst: dict[str, float] = {n: 0.0 for n in names}
    for ent in ENTITIES:
        if ent == "ketu":
            continue
        row = [ent]
        for n in names:
            lon = ok[n]["sidereal"].get(ent)
            row.append(deg_to_dms(lon) if lon is not None else "-")
        for n in names:
            if n == ref:
                continue
            t, t0 = ok[n]["tropical"].get(ent), ok[ref]["tropical"].get(ent)
            if t is None or t0 is None:
                row.append("-")
                continue
            d = arcmin_gap(t, t0)
            worst[n] = max(worst[n], abs(d))
            row.append(f"{d:+.2f}'")
        rows.append(row)
    lines += _table(["entity", *(f"{n} sidereal" for n in names),
                     *(f"tropical {n}-{ref}" for n in names if n != ref)], rows)
    for n in names:
        if n != ref:
            lines.append(f"  max |tropical {n} - {ref}| = {worst[n]:.2f}'")
    return lines


# ---------------------------------------------------------------------- main
def run(case: dict, provider, tol: float, engines: bool, full_sens: bool) -> tuple[int, dict, list[str]]:
    lines: list[str] = []
    payload: dict = {"id": case["id"]}
    pending = case["observed"]["status"] == "pending"
    status = 0
    if pending:
        lines += [f"Case {case['id']}: observed values are PENDING (enter them from JHora / "
                  "AstroSage, set observed.status to 'entered'). Showing engine output only.", ""]
        status = 3
        comp = compute_case(provider, case)
        lines += [f"Engine: {json.dumps(ephemeris_provenance(provider))}",
                  f"Ayanamsa {case['settings']['ayanamsa']} = {comp['ayanamsa']:.6f}  "
                  f"UTC {comp['utc'].isoformat()}", ""]
        lines += _table(["item", "computed", "nakshatra pada"], [
            [n, deg_to_dms(comp["lon"][n]),
             f"{NAKSHATRA_NAMES[int(comp['lon'][n] // NAKSHATRA_SPAN)]} "
             f"{int(comp['lon'][n] % NAKSHATRA_SPAN // (NAKSHATRA_SPAN / 4)) + 1}"]
            for n in ENTITIES])
        payload["computed"] = {n: comp["lon"][n] for n in ENTITIES}
    else:
        result = compare(provider, case, tol)
        lines += render_comparison(case, result, provider)
        fails = [r for r in result["rows"] if r["status"] == FAIL] + [
            d for d in result["dasha"] if d["status"] == FAIL]
        status = 1 if fails else 0
        lines += ["", f"RESULT: {'FAIL' if fails else 'PASS'} ({len(fails)} failing of "
                  f"{len(result['rows']) + len(result['dasha'])} compared)"]
        causes = diagnose(provider, case, result)
        if causes:
            lines += ["", "Likely causes"] + [f"  - {c}" for c in causes]
        payload.update(result={"rows": result["rows"], "dasha": result["dasha"]}, causes=causes)
    sens = sensitivity_report(settings_input(case), provider)
    lines += ["", *render_sensitivity(sens, full_sens)]
    payload["sensitivity"] = sens
    if engines:
        cmp_ = engine_compare(case)
        lines += ["", *render_engines(cmp_)]
        payload["engines"] = cmp_
    return status, payload, lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("case", type=Path)
    ap.add_argument("--provider", default=None, help="swiss|astronomy (default: env/swiss)")
    ap.add_argument("--tolerance", type=float, default=DEFAULT_TOL_ARCMIN,
                    help="arcminutes (default 1.0)")
    ap.add_argument("--engines", action="store_true", help="also compare independent engines")
    ap.add_argument("--full-sensitivity", action="store_true")
    ap.add_argument("--markdown", type=Path, help="also write the output to this .md file")
    ap.add_argument("--json", action="store_true", help="print JSON instead of the text table")
    args = ap.parse_args(argv)
    with contextlib.suppress(AttributeError):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        case = load_case(args.case)
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2
    provider = get_provider(args.provider)
    status, payload, lines = run(case, provider, args.tolerance, args.engines,
                                 args.full_sensitivity)
    text = "\n".join(lines)
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(text)
    if args.markdown:
        args.markdown.write_text(f"# {case['id']}\n\n```text\n{text}\n```\n", encoding="utf-8")
    return status


if __name__ == "__main__":
    sys.exit(main())
