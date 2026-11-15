from datetime import UTC, datetime

from nakshatra_core.chart import compute_vedic_chart_artifact
from nakshatra_interpret import build_reading

RAIGANJ = {
    "birthDate": "2003-08-29",
    "birthTime": "12:22",
    "timezoneName": "Asia/Kolkata",
    "latitude": 25.6167,
    "longitude": 88.1233,
}

NOW = datetime(2026, 7, 19, tzinfo=UTC)


def test_reading_structure_and_grounding() -> None:
    artifact = compute_vedic_chart_artifact(RAIGANJ)
    reading = build_reading(artifact, NOW)

    sections = {s["key"]: s for s in reading["sections"]}
    assert set(sections) == {
        "lagna", "planets", "houses", "yogas", "dasha", "vargas", "panchang",
    }
    assert len(sections["planets"]["items"]) == 9
    assert len(sections["houses"]["items"]) == 12
    # Only present yogas are interpreted (5 for the Raiganj chart).
    assert len(sections["yogas"]["items"]) == 5
    # Every item is evidence-cited.
    for section in reading["sections"]:
        for item in section["items"]:
            assert item["evidence"], f"{section['key']}: {item['title']}"
            assert len(item["text"]) > 40


def test_reading_reflects_chart_facts() -> None:
    artifact = compute_vedic_chart_artifact(RAIGANJ)
    reading = build_reading(artifact, NOW)
    sections = {s["key"]: s for s in reading["sections"]}

    lagna_text = sections["lagna"]["items"][0]["text"]
    assert "Scorpio" in lagna_text
    assert "Anuradha" in lagna_text

    mercury = next(
        i for i in sections["planets"]["items"] if "Mercury" in i["title"]
    )
    assert "exalted" in mercury["text"]
    assert "Retrograde" in mercury["text"]

    venus = next(i for i in sections["planets"]["items"] if "Venus" in i["title"])
    assert "Combustion" in venus["text"]

    dasha = sections["dasha"]["items"][0]
    assert "rahu" in dasha["title"]


def test_reading_deterministic() -> None:
    artifact = compute_vedic_chart_artifact(RAIGANJ)
    assert build_reading(artifact, NOW) == build_reading(artifact, NOW)
