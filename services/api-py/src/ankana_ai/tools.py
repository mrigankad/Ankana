"""Tool definitions, executor and citation registrar.

Tools are read-only views over an already computed chart artifact (a plain dict
from nakshatra_core.chart). Lal Kitab is reached through the thin
LalKitabProvider interface so the real package (ankana_lalkitab) can be dropped
in without touching this module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

TOOL_ANCHORS: dict[str, str] = {
    "get_birth_chart": "planets",
    "get_dashas": "dashas",
    "get_yogas": "yogas",
    "get_strengths": "strengths",
    "get_transits": "transits",
    "get_predictions": "predictions",
    "get_remedies": "remedies",
    "get_reading_summary": "reading",
    "get_life_story": "your-life",
    "lk_chart": "lal-kitab",
    "lk_sleeping": "lal-kitab-sleeping",
    "lk_rin": "lal-kitab-rin",
    "lk_masnui": "lal-kitab-masnui",
    "lk_varshphal": "lal-kitab-varshphal",
    "lk_upay": "lal-kitab-upay",
}

SUBMIT_TOOL = "submit_answer"

TOOL_STATUS_LABELS: dict[str, str] = {
    "get_birth_chart": "Consulting birth chart...",
    "get_dashas": "Consulting dasha timeline...",
    "get_yogas": "Reviewing yogas...",
    "get_strengths": "Checking planetary strengths...",
    "get_transits": "Reading current transits...",
    "get_predictions": "Scanning prediction windows...",
    "get_remedies": "Looking up remedies...",
    "get_reading_summary": "Opening deep reading...",
    "get_life_story": "Opening Your Life chapters...",
    "lk_chart": "Reading Lal Kitab chart...",
    "lk_sleeping": "Checking dormant planets...",
    "lk_rin": "Checking Lal Kitab debts...",
    "lk_masnui": "Checking artificial planets...",
    "lk_varshphal": "Casting the annual chart...",
    "lk_upay": "Ranking Lal Kitab upay...",
}


def tool_status_label(name: str) -> str:
    return TOOL_STATUS_LABELS.get(name, f"Consulting {name}...")


# ---------------------------------------------------------------- Lal Kitab


class LalKitabProvider(Protocol):
    """What the assistant needs from the Lal Kitab package (keyed lookup, no RAG).

    Every method returns JSON-serialisable data. `chart` must contain
    `planetHouse: {planet: house}` so claims can be verified.
    """

    def chart(self, artifact: dict, origin: str = "lagna_h1") -> dict: ...
    def sleeping(self, artifact: dict) -> dict: ...
    def rin(self, artifact: dict) -> list: ...
    def masnui(self, artifact: dict) -> list: ...
    def varshphal(self, artifact: dict, age: int | None, now: datetime) -> dict: ...
    def upay(self, artifact: dict) -> dict: ...


class StubLalKitab:
    """Placeholder used until ankana_lalkitab is installed.

    Lal Kitab houses are whole-sign houses from the lagna for origin
    `lagna_h1`, so the chart is exact; everything else reports that the module
    is not installed rather than inventing rules.
    """

    available_rules = False

    def chart(self, artifact: dict, origin: str = "lagna_h1") -> dict:
        planet_house = {p["planet"]: p["house"] for p in artifact["planets"]}
        houses: list[dict] = [
            {"house": n, "planets": [pl for pl, h in planet_house.items() if h == n]}
            for n in range(1, 13)
        ]
        return {"origin": origin, "houses": houses, "planetHouse": planet_house,
                "coverage": {"rules": "stub"}}

    def _na(self) -> dict:
        return {"available": False, "reason": "Lal Kitab rules package not installed"}

    def sleeping(self, artifact: dict) -> dict:
        return self._na()

    def rin(self, artifact: dict) -> list:
        return []

    def masnui(self, artifact: dict) -> list:
        return []

    def varshphal(self, artifact: dict, age: int | None, now: datetime) -> dict:
        return self._na()

    def upay(self, artifact: dict) -> dict:
        return self._na()


def load_lalkitab() -> LalKitabProvider:
    """Return the real Lal Kitab adapter when ankana_lalkitab exposes one.

    The package is being ported in parallel. It is expected to expose
    `ankana_lalkitab.assistant_adapter()` returning a LalKitabProvider; until
    then (or on ImportError) the stub is used.
    """
    try:
        import ankana_lalkitab  # type: ignore[import-not-found]

        factory = getattr(ankana_lalkitab, "assistant_adapter", None)
        if callable(factory):
            return factory()
    except ImportError:
        pass
    return StubLalKitab()


# ---------------------------------------------------------------- citations


@dataclass
class Citation:
    index: int
    tool: str
    fact: str
    anchor: str | None = None

    def as_dict(self) -> dict:
        return {"index": self.index, "tool": self.tool, "fact": self.fact, "anchor": self.anchor}


@dataclass
class CitationRegistrar:
    """Allocates [n] markers in tool-call order; identical calls reuse an index."""

    citations: list[Citation] = field(default_factory=list)
    _seen: dict[str, int] = field(default_factory=dict)

    def register(self, tool: str, args: dict, fact: str, anchor: str | None) -> Citation:
        key = f"{tool}:{json.dumps(args, sort_keys=True, default=str)}"
        if key in self._seen:
            return self.citations[self._seen[key] - 1]
        citation = Citation(len(self.citations) + 1, tool, fact, anchor)
        self.citations.append(citation)
        self._seen[key] = citation.index
        return citation

    def get(self, index: int) -> Citation | None:
        if 1 <= index <= len(self.citations):
            return self.citations[index - 1]
        return None


# --------------------------------------------------------------- definitions

_EMPTY = {"type": "object", "properties": {}, "additionalProperties": False}


def _tool(name: str, description: str, schema: dict | None = None) -> dict:
    return {
        "name": name,
        "description": description,
        "input_schema": schema or _EMPTY,
        "strict": True,
    }


DATA_TOOLS: list[dict] = [
    _tool(
        "get_birth_chart",
        "Natal chart facts: lagna (sign, degree, nakshatra, pada), every planet with sign, "
        "degree in sign, house, nakshatra, pada, dignity, retrograde and combustion, and "
        "house lords. Source of truth for placements.",
    ),
    _tool(
        "get_dashas",
        "Vimshottari dasha timeline: all mahadashas with dates, the running mahadasha and "
        "antardasha for the reference date, and the antardashas of one mahadasha on request.",
        {
            "type": "object",
            "properties": {
                "mahadasha": {
                    "type": "string",
                    "description": "Planet name to expand antardashas for; defaults to the current one.",
                }
            },
            "required": ["mahadasha"],
            "additionalProperties": False,
        },
    ),
    _tool("get_yogas", "Yogas and doshas detected as present, with their supporting evidence."),
    _tool(
        "get_strengths",
        "Shadbala ratios per planet, Vimshopaka scores and Sarvashtakavarga bindus per sign.",
    ),
    _tool(
        "get_transits",
        "Current transit snapshot against the natal chart, including sade sati status.",
    ),
    _tool(
        "get_predictions",
        "Rule-engine prediction windows (dated, with confidence and evidence), next five years.",
    ),
    _tool("get_remedies", "Traditional remedies the chart supports, each with its cautions."),
    _tool("get_reading_summary", "Condensed deterministic reading by section (lagna, planets, houses...)."),
    _tool("get_life_story", "Your Life chapters by age band and dasha, hybrid lens."),
]

LK_TOOLS: list[dict] = [
    _tool(
        "lk_chart",
        "Lal Kitab chart: planets by house (fixed-house system), aspects and planet-in-house rules.",
        {
            "type": "object",
            "properties": {"origin": {"type": "string", "enum": ["lagna_h1", "aries_h1"]}},
            "required": ["origin"],
            "additionalProperties": False,
        },
    ),
    _tool("lk_sleeping", "Lal Kitab dormant (sleeping) planets and houses."),
    _tool("lk_rin", "Lal Kitab debts (rin) detected in the chart."),
    _tool("lk_masnui", "Lal Kitab artificial (masnui) planets formed by conjunctions."),
    _tool(
        "lk_varshphal",
        "Lal Kitab annual chart (varshphal) for a year of life.",
        {
            "type": "object",
            "properties": {"age": {"type": "integer", "description": "Year of life; 0 for current."}},
            "required": ["age"],
            "additionalProperties": False,
        },
    ),
    _tool("lk_upay", "Ranked Lal Kitab upay (remedies); run one at a time."),
]

PLANETS = ["sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "rahu", "ketu"]
SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
CLAIM_TYPES = [
    "lagna", "planet_sign", "planet_house", "planet_degree", "planet_nakshatra",
    "house_lord", "dasha_period", "yoga", "lk_planet_house", "transit_sign", "sade_sati",
]

SUBMIT_ANSWER_TOOL: dict = {
    "name": SUBMIT_TOOL,
    "description": (
        "Deliver the final answer. Call this exactly once when you are done researching. "
        "Split the answer into sentences; list every chart fact stated in a sentence as a claim "
        "tied to the [n] citation of the tool result it came from. Claim fields use canonical "
        "English values whatever language the sentence is in."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "language": {"type": "string", "enum": ["en", "hi", "hinglish"]},
            "refusal": {"type": "boolean", "description": "True if you decline the request."},
            "sentences": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "One sentence; include [n] markers."},
                        "claims": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string", "enum": CLAIM_TYPES},
                                    "cite": {"type": "integer", "description": "Citation index n."},
                                    "planet": {"type": "string", "enum": [*PLANETS, "lagna"]},
                                    "sign": {"type": "string", "enum": SIGNS},
                                    "house": {"type": "integer"},
                                    "degree": {"type": "number", "description": "Degrees within the sign."},
                                    "nakshatra": {"type": "string"},
                                    "pada": {"type": "integer"},
                                    "lord": {"type": "string", "enum": PLANETS},
                                    "level": {"type": "string", "enum": ["mahadasha", "antardasha"]},
                                    "parent": {"type": "string", "description": "Mahadasha planet when level is antardasha."},
                                    "start": {"type": "string", "description": "YYYY-MM-DD"},
                                    "end": {"type": "string", "description": "YYYY-MM-DD"},
                                    "yoga": {"type": "string"},
                                    "present": {"type": "boolean"},
                                },
                                "required": ["type", "cite"],
                            },
                        },
                    },
                    "required": ["text", "claims"],
                },
            },
        },
        "required": ["sentences"],
    },
}


def tool_definitions(lk_enabled: bool = True) -> list[dict]:
    """Deterministic ordering (prompt-cache friendly): data, lk, then submit."""
    defs = [*DATA_TOOLS, *(LK_TOOLS if lk_enabled else []), SUBMIT_ANSWER_TOOL]
    return defs


# ------------------------------------------------------------------ executor


@dataclass
class ToolContext:
    artifact: dict
    now: datetime
    lalkitab: LalKitabProvider = field(default_factory=StubLalKitab)
    _reading: dict | None = None
    _life: dict | None = None

    def reading(self) -> dict:
        if self._reading is None:
            from nakshatra_interpret import build_reading

            self._reading = build_reading(self.artifact, self.now)
        return self._reading

    def life_story(self) -> dict:
        if self._life is None:
            from nakshatra_interpret.life_story import build_life_story

            self._life = build_life_story(self.artifact, self.now)
        return self._life


@dataclass
class ToolResult:
    summary: str
    data: Any
    anchor: str | None = None


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def current_dashas(artifact: dict, now: datetime) -> tuple[dict | None, dict | None]:
    now = now if now.tzinfo else now.replace(tzinfo=UTC)
    md = next(
        (m for m in artifact["vimshottari"]["mahadashas"]
         if _parse(m["start"]) <= now < _parse(m["end"])),
        None,
    )
    ad = None
    if md:
        ad = next(
            (a for a in md.get("children", []) if _parse(a["start"]) <= now < _parse(a["end"])),
            None,
        )
    return md, ad


def _period(p: dict | None) -> dict | None:
    if p is None:
        return None
    return {"planet": p["planet"], "start": p["start"][:10], "end": p["end"][:10]}


def _antardashas(md: dict | None) -> list[dict]:
    return [_period(a) for a in (md or {}).get("children", [])]


def execute_tool(name: str, ctx: ToolContext, args: dict | None = None) -> ToolResult:
    args = args or {}
    a = ctx.artifact
    anchor = TOOL_ANCHORS.get(name)

    if name == "get_birth_chart":
        asc = a["ascendant"]
        planets = [
            {k: p[k] for k in (
                "planet", "signName", "degreesInSign", "house", "nakshatra", "pada",
                "dignity", "retrograde", "combust")}
            for p in a["planets"]
        ]
        for p in planets:
            p["degreesInSign"] = round(p["degreesInSign"], 2)
        summary = (
            f"Lagna {asc['signName']} {asc['degreesInSign']:.1f} deg; house lords: "
            + " ".join(f"H{h['number']}:{h['lord']}" for h in a["houses"]) + "; "
            + ", ".join(
                f"{p['planet']} {p['signName']} H{p['house']}"
                + (" R" if p["retrograde"] else "") + (" combust" if p["combust"] else "")
                for p in planets
            )
        )
        return ToolResult(summary, {
            "ascendant": {k: asc[k] for k in ("signName", "degreesInSign", "nakshatra", "pada")},
            "planets": planets,
            "houses": [{"number": h["number"], "signName": h["signName"], "lord": h["lord"],
                        "occupants": h["occupants"]} for h in a["houses"]],
        }, anchor)

    if name == "get_dashas":
        md, ad = current_dashas(a, ctx.now)
        want = str(args.get("mahadasha") or "").lower()
        expand = next(
            (m for m in a["vimshottari"]["mahadashas"] if m["planet"] == want), md
        ) if want else md
        md_p, ad_p = _period(md), _period(ad)
        summary = (
            f"Current mahadasha {md_p['planet'] if md_p else 'unknown'} "
            f"({md_p['start'] if md_p else '?'} to {md_p['end'] if md_p else '?'}), "
            f"antardasha {ad_p['planet'] if ad_p else 'unknown'} "
            f"({ad_p['start'] if ad_p else '?'} to {ad_p['end'] if ad_p else '?'})"
        )
        return ToolResult(summary, {
            "referenceDate": ctx.now.date().isoformat(),
            "current": {"mahadasha": md_p, "antardasha": ad_p},
            "mahadashas": [_period(m) for m in a["vimshottari"]["mahadashas"]],
            "antardashasOf": {"planet": expand["planet"] if expand else None,
                              "periods": _antardashas(expand)},
        }, anchor)

    if name == "get_yogas":
        present = [y for y in a["yogas"] if y["present"]]
        return ToolResult(
            "Present yogas: " + (", ".join(y["name"] for y in present) or "none detected"),
            [{"key": y["key"], "name": y["name"], "category": y.get("category"),
              "evidence": y["evidence"]} for y in present],
            anchor,
        )

    if name == "get_strengths":
        sm = a["strengthMetrics"]
        shadbala = [{"planet": s["planet"], "ratio": round(s["ratio"], 2)} for s in sm["shadbala"]]
        return ToolResult(
            "Shadbala ratios: " + ", ".join(f"{s['planet']} {s['ratio']:.2f}" for s in shadbala),
            {"shadbala": shadbala, "vimshopaka": sm.get("vimshopaka"),
             "sarvashtakavarga": sm.get("sarvashtakavarga")},
            anchor,
        )

    if name == "get_transits":
        from nakshatra_core.transits import compute_transit_snapshot

        snap = compute_transit_snapshot(a, ctx.now)
        ss = snap["sadeSati"]
        return ToolResult(
            f"Transits {snap['date'][:10]}: "
            + ", ".join(f"{p['planet']} {p['signName']}" for p in snap["planets"])
            + "; sade sati " + (f"active ({ss['phase']})" if ss["active"] else "inactive"),
            snap, anchor,
        )

    if name == "get_predictions":
        from nakshatra_rules import evaluate_predictions_enriched

        preds = evaluate_predictions_enriched(a, from_date=ctx.now, horizon_years=5)
        preds = sorted(preds, key=lambda p: -p["confidence"])[:12]
        return ToolResult(f"{len(preds)} top prediction windows in the next 5 years", preds, anchor)

    if name == "get_remedies":
        from nakshatra_rules import evaluate_remedies

        rem = evaluate_remedies(a)
        return ToolResult(f"{len(rem)} remedies suggested", rem, anchor)

    if name == "get_reading_summary":
        r = ctx.reading()
        sections = [
            {"key": s["key"], "title": s["title"],
             "highlights": [{"title": i["title"], "text": i["text"], "evidence": i["evidence"][:4]}
                            for i in s["items"][:3]]}
            for s in r["sections"]
        ]
        return ToolResult(
            f"Deep reading ({len(sections)} sections): " + "; ".join(s["title"] for s in sections),
            {"sections": sections}, anchor,
        )

    if name == "get_life_story":
        life = ctx.life_story()
        chapters = life["lenses"]["hybrid"]
        brief = [{"key": c["key"], "title": c["title"], "ageRange": c.get("ageRange"),
                  "isCurrent": c.get("isCurrent", False), "summary": c.get("summary"),
                  "items": [{"title": i["title"], "text": i["text"]} for i in c["items"][:3]]}
                 for c in chapters]
        return ToolResult(f"Your Life: {len(brief)} chapters", {"chapters": brief}, anchor)

    if name.startswith("lk_"):
        lk = ctx.lalkitab
        if name == "lk_chart":
            origin = "aries_h1" if args.get("origin") == "aries_h1" else "lagna_h1"
            data = lk.chart(a, origin)
            ph = data.get("planetHouse", {})
            return ToolResult(
                f"Lal Kitab chart ({origin}): " + ", ".join(f"{p} H{h}" for p, h in ph.items()),
                data, anchor,
            )
        if name == "lk_sleeping":
            data = lk.sleeping(a)
            return ToolResult("Lal Kitab dormant planets and houses", data, anchor)
        if name == "lk_rin":
            data = lk.rin(a)
            return ToolResult(f"{len(data)} Lal Kitab debt patterns", data, anchor)
        if name == "lk_masnui":
            data = lk.masnui(a)
            return ToolResult(f"{len(data)} artificial planets", data, anchor)
        if name == "lk_varshphal":
            age = args.get("age")
            data = lk.varshphal(a, int(age) if isinstance(age, int) and age > 0 else None, ctx.now)
            return ToolResult("Lal Kitab varshphal", data, anchor)
        if name == "lk_upay":
            data = lk.upay(a)
            return ToolResult("Lal Kitab upay", data, anchor)

    return ToolResult(f"Unknown tool {name}", None)
