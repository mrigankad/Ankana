import json
from pathlib import Path

import pytest

GOLDEN_PATH = Path(__file__).parent / "golden" / "charts.json"


@pytest.fixture(scope="session")
def golden_charts() -> list[dict]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
