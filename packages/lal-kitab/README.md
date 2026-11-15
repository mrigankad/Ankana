# @astro/lal-kitab

Lal Kitab calculators and rule tables (TypeScript first).

- `data/*.json`: paraphrased tables. Every row has `cite` (vol, printed_page, pdf_page, section, ocr_confidence, verified_from_image) and `needs_review`. No verbatim book prose is stored.
- `src/`: `lkChart` (lagna = house 1 by default, `aries_h1` optional), dormant planets/houses, aspects, rin, masnui, varshphal (+ 35-year cycle), ranked `remedies` with the one-at-a-time rule, and `lalKitabReport` (everything the future "lal-kitab" tab needs).
- Wired into `@astro/ai-orchestrator` (`lk_*` tools) and `GET /api/v1/charts/jobs/:jobId/lal-kitab` in `apps/api`.

## Python port (not done yet)

`services/api-py` has no Lal Kitab module. When porting: add `nakshatra_lalkitab/` that loads the same `data/*.json` files (copy or read from this package so there is one source of truth), mirror the function names, and add golden fixtures (`services/api-py/tests/golden/lal_kitab.json`) generated from the TS output for the demo chart (Ananya Sharma, 1995-03-15 06:42 Varanasi) plus a few synthetic house maps, then a parity test like `test_parity_core.py`.

## Data status

See `dataCoverage()` in `src/data.ts`. Planet-in-house entries: all 108 done. Sun lives in `data/planet_house.json`; the other eight planets live in `data/planet_house/<planet>.json` and override the placeholder rows by id. Every entry is paraphrased with a page cite and most carry `needs_review`. Remedies involving harm to animals or people, liquor, piercing or medicine doses were deliberately omitted (see each row's `note`). Page cites were re-derived from the page images in the book audit (see `docs/lal-kitab-verification.md`): the printed-page offset differs per section of the scan (Sun and Jupiter 16, Moon 14, Venus 13, Mars 11, Mercury 10, Saturn 8, Rahu 6, Ketu 4). Row-level `needs_review` flags now mark only the rules the book leaves ambiguous; the paraphrased planet-in-house effect text itself was sampled, not audited line by line.
