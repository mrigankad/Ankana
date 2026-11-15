#!/usr/bin/env python3
"""CLI: stdin VedicChartArtifact JSON → stdout reading JSON.

Used by the Fastify API so the practitioner UI can show the Python
interpretation engine without a full backend cutover yet.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "services" / "api-py" / "src"
sys.path.insert(0, str(SRC))

from nakshatra_interpret import build_reading  # noqa: E402


def main() -> None:
    artifact = json.load(sys.stdin)
    json.dump(build_reading(artifact), sys.stdout, separators=(",", ":"))


if __name__ == "__main__":
    main()
