# Real-chart verification

Synthetic reference cases (`tests/reference/`) only prove the engine agrees with itself.
This folder checks it against values read from other software, for real births.

## Where cases live

| Folder | Content | Committed |
|---|---|---|
| `public/` | public-domain figures (cite the source), anonymised or explicitly consented charts | yes |
| `private/` | real personal charts (yours, family, clients) | **never**: the folder is in `.gitignore` |

Do not put a real person's chart in `public/` without their written consent.
Strip names; keep only date, time and place coordinates.

## Add a real chart

1. Copy a file from `public/` and edit it. Format: `observed.schema.json`.
2. Fill `input` (date, local time, IANA zone, coordinates). For local-mean-time births use `utcOffset` ("+00:39:57").
3. In JHora (or AstroSage, etc.) open the same birth with the same settings and note them in `settings`: ayanamsa (Lahiri default), node (mean/true), and whether it adds nutation.
4. Type the values into `observed`: lagna and planet longitudes to the arcminute (`"Sc 14°58'"`), optionally nakshatra and pada, mahadasha start dates, the ayanamsa value. Set `status` to `entered`.
5. Run:

```
python scripts/verify_real_chart.py tests/real/private/me.json
python scripts/verify_real_chart.py tests/real/private/me.json --engines --markdown tests/real/private/me-report.md
```

Add `--provider astronomy` to test the other engine, `--json` for machine output, `--full-sensitivity` for every planet.

## Reading the output

* Pass means within 1 arcminute (hand entry is to the arcminute; `--tolerance` changes it) and dasha dates within 1 day.
* Each failure lists likely causes: settings mismatch (the script tries every ayanamsa/node combination), uniform ayanamsa offset, birth-time or timezone/DST shift (it fits a time offset), lagna/longitude error, sign or pada boundary, dasha year length.
* The sensitivity table shows how many minutes of birth-time error flip each sign, pada, house or the dasha lord; anything under 10 minutes is flagged. The same data is served at `GET /v1/charts/{id}/sensitivity`.
* Exit codes: 0 pass, 1 fail, 2 invalid case, 3 observed still pending.

`--engines` also compares swiss, astronomy and (if installed with `pip install jyotishganit`) an independent Skyfield/DE421 engine. If its Hipparcos download host is unreachable, set `ANKANA_JG_OFFLINE_SPICA=1`.

The five public cases are Astro-Databank births (Rodden AA as recorded there; confirm on the page). Their `observed` is `pending` until someone enters JHora values.
