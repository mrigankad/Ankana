"""Prediction evaluator - exact port of rule-engine evaluator.ts."""

import math
from datetime import UTC, datetime, timedelta

from nakshatra_core.transits import sade_sati_active as saturn_sade_sati_active
from nakshatra_i18n import CATALOGS, Lang
from nakshatra_i18n.names import DOMAIN_LABELS_HI
from nakshatra_i18n.yogas_hi import YOGA_NAMES_HI

from .pack import DOMAIN_LABEL, VEDIC_PREDICTION_RULES

_SOURCE_KEYS = {v: k for k, v in CATALOGS["en"].items() if k.startswith("src.")}


def rule_catalog_key(rule: dict) -> str:
    """Catalog key for a rule's text: full id for special rules, else the
    domain-stripped suffix shared by the four generic rules per domain."""
    full = f"rule.{rule['id']}"
    if full in CATALOGS["en"]:
        return full
    return "rule." + rule["id"][len(rule["domain"]) + 1:]


def _rule_text(L: Lang, rule: dict, level: str, lord: str) -> str:
    if not L.hi:
        return rule["text"].replace("{level}", level).replace("{lord}", lord)
    return L.t(rule_catalog_key(rule), level=L.level(level), lord=L.planet(lord),
               label=DOMAIN_LABELS_HI.get(rule["domain"], DOMAIN_LABEL.get(rule["domain"])))


def _source(L: Lang, rule: dict) -> str:
    if not L.hi:
        return rule["source"]
    return L.t(_SOURCE_KEYS[rule["source"]])


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + (
        f"{dt.microsecond // 1000:03d}Z"
    )


def _build_facts(artifact: dict) -> dict:
    owned_houses: dict[str, list[int]] = {}
    for house in artifact["houses"]:
        owned_houses.setdefault(house["lord"], []).append(house["number"])
    return {
        "ownedHouses": owned_houses,
        "houseOf": {p["planet"]: p["house"] for p in artifact["planets"]},
        "dignityOf": {p["planet"]: p["dignity"] for p in artifact["planets"]},
        "combust": {p["planet"] for p in artifact["planets"] if p["combust"]},
        "strengthRatio": {
            r["planet"]: r["ratio"] for r in artifact["strengthMetrics"]["shadbala"]
        },
        "presentYogas": {y["key"] for y in artifact["yogas"] if y["present"]},
    }


def _condition_holds(condition: dict, lord: str, facts: dict, window: dict, L: Lang | None = None):
    L = L or Lang("en")
    kind = condition["kind"]
    if kind == "dashaLordOwnsHouse":
        owned = facts["ownedHouses"].get(lord, [])
        hits = [h for h in owned if h in condition["houses"]]
        if hits:
            return True, L.t("cond.owns", lord=L.planet(lord), hits=" and ".join(str(h) for h in hits))
        return False, None
    if kind == "dashaLordInHouse":
        house = facts["houseOf"].get(lord)
        if house is not None and house in condition["houses"]:
            return True, L.t("cond.occupies", lord=L.planet(lord), house=house)
        return False, None
    if kind == "dashaLordDignity":
        dignity = facts["dignityOf"].get(lord)
        if dignity is not None and dignity in condition["dignities"]:
            return True, L.t("cond.dignity", lord=L.planet(lord), dignity=L.dignity(dignity))
        return False, None
    if kind == "dashaLordStrengthRatioAtLeast":
        ratio = facts["strengthRatio"].get(lord)
        if ratio is not None and ratio >= condition["ratio"]:
            return True, L.t("cond.ratio_ge", lord=L.planet(lord), ratio=f"{ratio:.2f}", th=condition["ratio"])
        return False, None
    if kind == "dashaLordStrengthRatioBelow":
        ratio = facts["strengthRatio"].get(lord)
        if ratio is not None and ratio < condition["ratio"]:
            return True, L.t("cond.ratio_lt", lord=L.planet(lord), ratio=f"{ratio:.2f}", th=condition["ratio"])
        return False, None
    if kind == "dashaLordIs":
        if lord in condition["planets"]:
            return True, L.t("cond.lord_is", level=L.level(window["level"]), lord=L.planet(lord))
        return False, None
    if kind == "dashaLordCombust":
        if lord in facts["combust"]:
            return True, L.t("cond.combust", lord=L.planet(lord))
        return False, None
    if kind == "yogaPresent":
        hits = [k for k in condition["keys"] if k in facts["presentYogas"]]
        if hits:
            return True, L.t("cond.yoga", keys=", ".join(YOGA_NAMES_HI.get(k, k) if L.hi else k for k in hits))
        return False, None
    if kind == "sadeSatiActiveAtWindow":
        if window["sadeSatiActive"]:
            return True, L.t("cond.sade_sati")
        return False, None
    raise ValueError(f"unknown condition kind: {kind}")


def evaluate_predictions(
    artifact: dict,
    from_date: datetime | None = None,
    horizon_years: float = 5,
    domains: list[str] | None = None,
    rules: list[dict] | None = None,
    lang: str = "en",
) -> list[dict]:
    predictions = _evaluate(artifact, from_date, horizon_years, domains, rules, lang)
    for prediction in predictions:
        prediction.pop("_lords", None)
    return predictions


def _evaluate(
    artifact: dict,
    from_date: datetime | None = None,
    horizon_years: float = 5,
    domains: list[str] | None = None,
    rules: list[dict] | None = None,
    lang: str = "en",
) -> list[dict]:
    """Shared core; predictions carry a private `_lords` pair for enrichment."""
    L = Lang(lang)
    from_date = from_date or datetime.now(tz=UTC)
    horizon_years = min(horizon_years, 30)
    until = from_date + timedelta(days=horizon_years * 365.2425)
    rules = rules if rules is not None else VEDIC_PREDICTION_RULES
    facts = _build_facts(artifact)

    windows = []
    for mahadasha in artifact["vimshottari"]["mahadashas"]:
        for antardasha in mahadasha.get("children", []):
            start = _parse(antardasha["start"])
            end = _parse(antardasha["end"])
            if end <= from_date or start >= until:
                continue
            windows.append(
                {
                    "start": start,
                    "end": end,
                    "mdLord": mahadasha["planet"],
                    "adLord": antardasha["planet"],
                }
            )

    predictions: list[dict] = []

    for window in windows:
        midpoint = window["start"] + (window["end"] - window["start"]) / 2
        sade_sati_active = saturn_sade_sati_active(artifact, midpoint)

        contexts = [
            {"level": "mahadasha", "lord": window["mdLord"], "sadeSatiActive": sade_sati_active},
            {"level": "antardasha", "lord": window["adLord"], "sadeSatiActive": sade_sati_active},
        ]

        by_domain: dict[str, dict] = {}
        for context in contexts:
            for rule in rules:
                if domains and rule["domain"] not in domains:
                    continue
                evidence = []
                all_hold = True
                for condition in rule["when"]:
                    holds, note = _condition_holds(
                        condition, context["lord"], facts, context, L
                    )
                    if not holds:
                        all_hold = False
                        break
                    if note:
                        evidence.append(note)
                if not all_hold:
                    continue
                entry = by_domain.setdefault(
                    rule["domain"],
                    {"rules": [], "evidence": [], "narratives": [], "lords": set()},
                )
                entry["rules"].append(rule)
                entry["lords"].add(context["lord"])
                src = _source(L, rule)
                entry["evidence"].extend(f"{e} ({src})" for e in evidence)
                entry["narratives"].append(
                    _rule_text(L, rule, context["level"], context["lord"])
                )

        for domain, entry in by_domain.items():
            supportive = [r for r in entry["rules"] if r["effect"] == "supportive"]
            challenging = [r for r in entry["rules"] if r["effect"] == "challenging"]
            if supportive and challenging:
                effect = "mixed"
            elif supportive:
                effect = "supportive"
            else:
                effect = "challenging"

            matched_weight = sum(r["weight"] for r in entry["rules"])
            ratios = [
                facts["strengthRatio"][lord]
                for lord in entry["lords"]
                if lord in facts["strengthRatio"]
            ]
            mean_ratio = sum(ratios) / len(ratios) if ratios else 1
            strength_factor = min(max(0.75 + 0.25 * mean_ratio, 0.75), 1.25)
            confidence = min(
                max(matched_weight / (matched_weight + 4) * strength_factor, 0.05),
                0.95,
            )

            label = L.t("pred.window", start=_iso(window["start"])[:10],
                        end=_iso(window["end"])[:10])
            predictions.append(
                {
                    "domain": domain,
                    "window": {"start": _iso(window["start"]), "end": _iso(window["end"])},
                    "headline": L.t(
                        "pred.headline", domain=L.domain(domain),
                        md=L.planet(window["mdLord"]), ad=L.planet(window["adLord"]),
                        label=label,
                    ),
                    "narrative": " ".join(dict.fromkeys(entry["narratives"])),
                    "effect": effect,
                    "confidence": math.floor(confidence * 100 + 0.5) / 100,
                    "evidence": list(dict.fromkeys(entry["evidence"])),
                    "ruleIds": list(dict.fromkeys(r["id"] for r in entry["rules"])),
                    "_lords": (window["mdLord"], window["adLord"]),
                }
            )

    return sorted(predictions, key=lambda p: (p["window"]["start"], p["domain"]))
