"""Additive enrichment over golden-parity predictions.

Adds practitioner-facing depth without changing the ported evaluator's
outputs: confidence bands with numeric drivers, an explicit tension flag for
mixed windows, and links to remedies for weak window lords.
"""

from datetime import datetime

from nakshatra_i18n import Lang

from .evaluator import _evaluate
from .remedies import evaluate_remedies


def _band(confidence: float) -> str:
    if confidence >= 0.7:
        return "high"
    if confidence >= 0.4:
        return "medium"
    return "low"


def evaluate_predictions_enriched(
    artifact: dict,
    from_date: datetime | None = None,
    horizon_years: float = 5,
    domains: list[str] | None = None,
    lang: str = "en",
) -> list[dict]:
    L = Lang(lang)
    predictions = _evaluate(artifact, from_date, horizon_years, domains, None, lang)
    ratio_of = {
        r["planet"]: r["ratio"] for r in artifact["strengthMetrics"]["shadbala"]
    }
    remedies = evaluate_remedies(artifact)
    remedy_planets = {r["planet"] for r in remedies}

    for prediction in predictions:
        prediction["confidenceBand"] = _band(prediction["confidence"])

        # Window lords: mahadasha lord then antardasha lord.
        lords = list(prediction.pop("_lords"))
        drivers = [
            L.t("pred.driver", lord=L.planet(lord), ratio=f"{ratio_of[lord]:.2f}")
            for lord in lords
            if lord in ratio_of
        ]
        if drivers:
            prediction["confidenceDrivers"] = drivers

        if prediction["effect"] == "mixed":
            prediction["tension"] = True
            prediction["narrative"] = L.t("pred.tension") + prediction["narrative"]

        linked = [
            lord for lord in lords if lord in remedy_planets and
            (lord not in ratio_of or ratio_of[lord] < 1)
        ]
        if linked:
            prediction["linkedRemedyPlanets"] = list(dict.fromkeys(linked))

    return predictions
