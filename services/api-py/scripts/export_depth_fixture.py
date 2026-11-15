"""Write the depth-view fixture the web app uses in fixture mode.

    python scripts/export_depth_fixture.py

Runs the real depth functions over the stored example artifact (Ananya), so fixture mode
shows exactly what the API would return. The dasha tree is stamped as of a fixed instant;
the web app re-marks the running period against the current time.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nakshatra_core.depth import ashtakavarga_depth, dashas_depth, planet_depth  # noqa: E402

WEB = ROOT.parents[1] / "apps" / "web-practitioner" / "lib" / "fixtures"
CHART_ID = "chart-ananya-sharma"

if __name__ == "__main__":
    artifact = json.loads((WEB / "ananya.generated.json").read_text(encoding="utf-8"))["artifact"]
    asof = datetime(2026, 11, 15, tzinfo=UTC)
    out = {
        "planets": {"chart_id": CHART_ID, **planet_depth(artifact)},
        "ashtakavarga": {"chart_id": CHART_ID, **ashtakavarga_depth(artifact)},
        "dashas": {s: {"chart_id": CHART_ID, **dashas_depth(artifact, s, asof)}
                   for s in ("vimshottari", "yogini")},
    }
    path = WEB / "depth.generated.json"
    path.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False) + "\n",
                    encoding="utf-8")
    print(f"wrote {path} ({path.stat().st_size // 1024} KB)")
