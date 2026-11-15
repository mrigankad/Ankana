from datetime import UTC, datetime

from nakshatra_core.chart import compute_vedic_chart_artifact
from nakshatra_interpret import build_reading
from nakshatra_interpret.life_story import build_life_story

RAIGANJ = {
    "birthDate": "2003-08-29",
    "birthTime": "12:22",
    "timezoneName": "Asia/Kolkata",
    "latitude": 25.6167,
    "longitude": 88.1233,
}

NOW = datetime(2026, 7, 19, tzinfo=UTC)


def test_life_story_structure_and_evidence() -> None:
    artifact = compute_vedic_chart_artifact(RAIGANJ)
    story = build_life_story(artifact, NOW)

    assert story["birthDate"] == "2003-08-29"
    assert story["currentAgeYears"] == 22
    assert set(story["lenses"]) == {"hybrid", "ageBands", "dashaChapters"}
    assert len(story["lenses"]["ageBands"]) == 5
    assert len(story["lenses"]["hybrid"]) == 5
    assert len(story["lenses"]["dashaChapters"]) >= 5

    for lens_key, chapters in story["lenses"].items():
        for chapter in chapters:
            assert chapter["summary"]
            assert chapter["items"], chapter["title"]
            for item in chapter["items"]:
                assert item["evidence"], f"{lens_key}: {chapter['title']}: {item['title']}"
                assert len(item["text"]) > 30


def test_life_story_hybrid_names_mahadashas() -> None:
    artifact = compute_vedic_chart_artifact(RAIGANJ)
    story = build_life_story(artifact, NOW)
    childhood = story["lenses"]["hybrid"][0]
    # Childhood overlaps Sun then Moon for Raiganj 2003.
    assert any(d["planet"] == "sun" for d in childhood["dashas"])
    assert any(d["planet"] == "moon" for d in childhood["dashas"])
    assert "Sun" in childhood["summary"] or "Moon" in childhood["summary"]


def test_life_story_dasha_titles() -> None:
    artifact = compute_vedic_chart_artifact(RAIGANJ)
    story = build_life_story(artifact, NOW)
    titles = [c["title"] for c in story["lenses"]["dashaChapters"]]
    assert any(t.startswith("Rahu years") for t in titles)
    current = [c for c in story["lenses"]["dashaChapters"] if c.get("isCurrent")]
    assert len(current) == 1
    assert current[0]["dashas"][0]["planet"] == "rahu"


def test_life_story_deterministic() -> None:
    artifact = compute_vedic_chart_artifact(RAIGANJ)
    assert build_life_story(artifact, NOW) == build_life_story(artifact, NOW)


def test_reading_includes_life_story() -> None:
    artifact = compute_vedic_chart_artifact(RAIGANJ)
    reading = build_reading(artifact, NOW)
    assert "lifeStory" in reading
    assert len(reading["sections"]) == 7
    assert set(reading["lifeStory"]["lenses"]) == {
        "hybrid",
        "ageBands",
        "dashaChapters",
    }
