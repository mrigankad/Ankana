"""Planet-in-house matching and ranked upay (port of remedies.ts)."""

from __future__ import annotations

from typing import Any

from .chart import planets_in
from .data import masnui_data, planet_house_entries, remedy_delivery
from .models import Delivery, EntryMatch, LkChart, MatchedCondition, UpayPlan
from .rules import detect_masnui, detect_rin, sleeping_planets


def clause_holds(chart: LkChart, clause: dict[str, Any], entry_planet: str) -> bool:
    if "in" in clause:
        c = clause["in"]
        return any(
            (h := chart.planet_house.get(p)) is not None and h in c["houses"] for p in c["planets"]
        )
    if "together" in clause:
        a, b = clause["together"]
        ha = chart.planet_house.get(a)
        return ha is not None and ha == chart.planet_house.get(b)
    if "empty" in clause:
        return all(not planets_in(chart, h) for h in clause["empty"])
    h = chart.planet_house.get(entry_planet)
    return h is not None and len(planets_in(chart, h)) == 1


def match_planet_house_entries(chart: LkChart) -> list[EntryMatch]:
    out: list[EntryMatch] = []
    for entry in planet_house_entries:
        if entry["status"] != "done":
            continue
        if chart.planet_house.get(entry["planet"]) != entry["house"]:
            continue
        matched = [
            MatchedCondition(effect=c["effect"], tone=c["tone"], needs_review=c["needs_review"])
            for c in entry["conditions"]
            if c.get("when")
            and all(clause_holds(chart, cl, entry["planet"]) for cl in c["when"])
        ]
        out.append(EntryMatch(entry=entry, matched=matched))
    return out


def _delivery_for(planet: str, chart: LkChart) -> Delivery | None:
    house = chart.planet_house.get(planet)
    if not house:
        return None
    for r in remedy_delivery["rows"]:
        if r["house"] == house:
            return Delivery(house=house, method=r["method"], cite=r["cite"])
    return None


def _method(d: Delivery | None) -> str:
    return (d.method if d and d.method is not None else "")


def remedies(chart: LkChart) -> UpayPlan:
    rule = remedy_delivery["one_at_a_time"]
    days = rule["duration_days"][1]
    drafts: list[dict[str, Any]] = []
    seen: set[str] = set()

    def push(key: str, d: dict[str, Any]) -> None:
        if key in seen:
            return
        seen.add(key)
        drafts.append(d)

    # 1. debts
    for f in detect_rin(chart):
        if f.basis == "indicator":
            continue
        push(
            f"rin:{f.id}",
            dict(
                kind="rin",
                planet=f.planet,
                house=f.house,
                title=f"{f.kind}: {f.planet} in house {f.house}",
                action=f.remedy,
                why=(
                    f"{f.planet} sits in house {f.house} with {', '.join(f.with_)}, "
                    "which the book lists as the pattern for this debt."
                ),
                delivery=None,
                duration_days=days,
                cites=[f.cite, f.remedy_cite],
                needs_review=f.needs_review,
            ),
        )
        for polluter in f.with_:
            d = _delivery_for(polluter, chart)
            push(
                f"rin_polluter:{f.id}:{polluter}",
                dict(
                    kind="rin_polluter",
                    planet=polluter,
                    house=f.house,
                    title=f"Repair {polluter} (spoils {f.planet} in house {f.house})",
                    action=(
                        f"Do a separate remedy for {polluter} after the debt remedy is finished. "
                        f"{_method(d)}"
                    ).strip(),
                    why=(
                        "The book asks for two remedies in a debt: the damaged planet and the "
                        "planet that damages it, run one after the other."
                    ),
                    delivery=d,
                    duration_days=days,
                    cites=[f.cite, rule["cite"]],
                    needs_review=True,
                ),
            )

    # 2. dormant planets
    for s in sleeping_planets(chart):
        if s.status != "dormant":
            continue
        d = _delivery_for(s.awakener, chart)
        if s.awakener_present:
            action = f"Strengthen {s.awakener}, the awakener of house {s.house}. {_method(d)}".strip()
        else:
            action = (
                f"{s.awakener} is absent from the chart; identify a remedy that awakens house "
                f"{s.house} through {s.awakener}'s articles."
            )
        push(
            f"sleep:{s.planet}",
            dict(
                kind="sleeping_planet",
                planet=s.planet,
                house=s.house,
                title=f"Awaken {s.planet} in house {s.house} (via {s.awakener})",
                action=action,
                why=(
                    f'{s.planet} is dormant by rule "{s.rule}". '
                    f"It may also awaken by itself around age {_js_num(s.self_awakening_age)}."
                ),
                delivery=d,
                duration_days=days,
                cites=[s.cite],
                needs_review=s.needs_review,
            ),
        )

    # 3. planet-in-house remedies where a malefic condition holds
    for m in match_planet_house_entries(chart):
        malefic = [x for x in m.matched if x.tone == "malefic"]
        if not malefic or not m.entry["remedies"]:
            continue
        for i, r in enumerate(m.entry["remedies"]):
            push(
                f"entry:{m.entry['id']}:{i}",
                dict(
                    kind="house_entry",
                    planet=m.entry["planet"],
                    house=m.entry["house"],
                    title=f"{m.entry['planet']} in house {m.entry['house']}",
                    action=r["text"],
                    why=" ".join(x.effect for x in malefic),
                    delivery=_delivery_for(m.entry["planet"], chart),
                    duration_days=days,
                    cites=[m.entry["cite"]],
                    needs_review=True,
                ),
            )

    # 4. artificial planets
    for a in detect_masnui(chart):
        variant = f" ({a.variant})" if a.variant else ""
        push(
            f"masnui:{a.id}",
            dict(
                kind="masnui",
                planet=a.formed_planet,
                house=a.house,
                title=(
                    f"Artificial {a.formed_planet}{variant} from "
                    f"{' + '.join(a.components)} in house {a.house}"
                ),
                action=masnui_data["remedy_principle"]["text"],
                why=(
                    f"{' and '.join(a.components)} share house {a.house}, "
                    f"forming an artificial {a.formed_planet}."
                ),
                delivery=_delivery_for(a.components[0], chart),
                duration_days=days,
                cites=[a.cite, masnui_data["remedy_principle"]["cite"]],
                needs_review=True,
            ),
        )

    upay = [dict(rank=i + 1, **d) for i, d in enumerate(drafts)]
    return UpayPlan.model_validate(
        dict(
            upay=upay,
            one_at_a_time=dict(
                rule=rule["rule"],
                duration_days=rule["duration_days"],
                gap=rule["gap"],
                cite=rule["cite"],
            ),
            schedule=[
                dict(phase=i + 1, upay_rank=u["rank"], days=days, then_pause=rule["gap"])
                for i, u in enumerate(upay)
            ],
            coverage=dict(
                planet_house_entries_done=sum(1 for e in planet_house_entries if e["status"] == "done"),
                planet_house_entries_total=len(planet_house_entries),
            ),
        )
    )


def _js_num(n: int | float) -> str:
    """Format a number the way JS template literals do (30.0 -> '30')."""
    return str(int(n)) if float(n).is_integer() else str(n)
