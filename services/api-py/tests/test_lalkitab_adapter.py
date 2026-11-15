from ankana_ai.tools import load_lalkitab


def test_assistant_uses_real_lal_kitab():
    lk = load_lalkitab()
    assert getattr(lk, "available_rules", False) is True
    art = {"planets": [{"planet": p, "house": h, "signIndex": (11 + h - 1) % 12}
                       for p, h in {"sun": 1, "ketu": 2, "mars": 5, "moon": 6, "rahu": 8,
                                    "jupiter": 9, "venus": 11, "mercury": 12,
                                    "saturn": 12}.items()],
           "ascendant": {"signIndex": 11}}
    chart = lk.chart(art)
    assert chart["planetHouse"]["saturn"] == 12
    assert "planets" in lk.sleeping(art)
    assert isinstance(lk.rin(art), list)
