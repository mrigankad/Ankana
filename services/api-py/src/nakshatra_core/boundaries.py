"""Boundary-proximity warnings.

A 0.1 deg shift in longitude (a ~4 minute birth-time error, or ayanamsa
variance between traditions) can flip a sign, nakshatra, or pada near a
boundary. Charts flag such bodies so practitioners know the reading is
birth-time sensitive (ICRC ayanamsa literature; comparative software study).
"""

from .zodiac import NAKSHATRA_SPAN

THRESHOLD_DEG = 0.1

_PADA_SPAN = NAKSHATRA_SPAN / 4


def _distance_to_multiple(longitude: float, span: float) -> float:
    within = longitude % span
    return min(within, span - within)


def boundary_warnings(
    longitudes: dict[str, float], ascendant_longitude: float
) -> list[dict]:
    warnings: list[dict] = []
    bodies = {**longitudes, "ascendant": ascendant_longitude}
    for body, longitude in bodies.items():
        for kind, span in (("sign", 30.0), ("nakshatra", NAKSHATRA_SPAN), ("pada", _PADA_SPAN)):
            distance = _distance_to_multiple(longitude, span)
            if distance <= THRESHOLD_DEG:
                warnings.append(
                    {"body": body, "kind": kind, "distanceDeg": round(distance, 4)}
                )
    return warnings
