"""Download the Swiss Ephemeris data files for 1800-2399 into ../ephe (gitignored).

Without them the Swiss provider falls back to the built-in Moshier ephemeris
(lower accuracy, see docs/engine-accuracy.md). Licensing: see LICENSING.md.
"""

import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/"
FILES = ("sepl_18.se1", "semo_18.se1", "seas_18.se1")


def main() -> None:
    target = Path(__file__).resolve().parent.parent / "ephe"
    target.mkdir(exist_ok=True)
    for name in FILES:
        print("fetching", name)
        urllib.request.urlretrieve(BASE + name, target / name)


if __name__ == "__main__":
    main()
