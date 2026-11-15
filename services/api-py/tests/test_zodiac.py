from nakshatra_core.zodiac import nakshatra_of, sign_of


def test_planets_and_ascendant_map_to_golden_signs(golden_charts: list[dict]) -> None:
    for chart in golden_charts:
        artifact = chart["artifact"]
        bodies = list(artifact["planets"]) + [
            {
                "planet": "ascendant",
                "siderealLongitude": artifact["ascendant"]["siderealLongitude"],
                "signIndex": artifact["ascendant"]["signIndex"],
                "signName": artifact["ascendant"]["signName"],
                "nakshatra": artifact["ascendant"]["nakshatra"],
                "pada": artifact["ascendant"]["pada"],
            }
        ]
        for body in bodies:
            sign = sign_of(body["siderealLongitude"])
            nak = nakshatra_of(body["siderealLongitude"])
            label = f"{chart['label']} {body['planet']}"
            assert sign.index == body["signIndex"], label
            assert sign.name == body["signName"], label
            assert nak.name == body["nakshatra"], label
            assert nak.pada == body["pada"], label
