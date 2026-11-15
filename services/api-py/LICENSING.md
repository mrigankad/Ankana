# Licensing

Ankana is licensed under **AGPL-3.0-only** (see the root `LICENSE`).

## Swiss Ephemeris

Charts are computed with the Swiss Ephemeris via `pyswisseph`, used under its AGPL-3.0
licence from Astrodienst. Because Ankana is itself AGPL-3.0, no professional licence is
needed.

## What AGPL means for running Ankana

- Ankana is offered to practitioners as a network service, so section 13 applies: every
  user must be able to get the complete corresponding source of the version they use.
  The app shows a "Source code" link (footer and About) to the public repository and the
  exact commit deployed (`ANKANA_SOURCE_URL`, `ANKANA_GIT_SHA`).
- Any modification deployed to users must be published under AGPL-3.0, including
  ephemeris data handling, the Lal Kitab rules and the AI assistant code.
- Secrets and configuration (API keys, database URLs) are not source and stay private.
- Practitioner and client data is never part of the source.

## Data files

The Swiss Ephemeris data files (`ephe/*.se1`, fetched by `scripts/fetch_ephe.py`,
gitignored) fall under the same AGPL terms. If they are missing, pyswisseph falls back
to the built-in Moshier ephemeris (lower precision); production images must include them.

## Fallback

`ANKANA_EPHEMERIS=astronomy` selects astronomy-engine (MIT). It fails the reference
tolerances (see `docs/engine-accuracy.md`) and is kept only as a cross-check.
