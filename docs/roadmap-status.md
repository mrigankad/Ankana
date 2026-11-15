# Nakshatra - Build Status & Next Steps

_Last updated: 2026-08-01_

## Current focus: FastAPI cutover (Phase 5.1) + assistant

Spec: `docs/superpowers/specs/2026-07-19-python-backend-deep-reading-design.md`.
Stability plan: `docs/superpowers/plans/2026-08-01-stability-cutover-plan.md`.

| Plan | Scope | State |
| --- | --- | --- |
| A–C | Engine core, analytics, yogas + interpretation | ✅ |
| Phase 1–3 | Accuracy, rules port, FastAPI persistence/routes | ✅ |
| Phase 5.2–5.3 | Reading tab + enriched predictions (Fastify bridge) | ✅ |
| Phase 5.1 | Point web at FastAPI `:8000` | next |
| Phase 4 | Assistant on Python + faithfulness evals | next |
| Phase 6 | Optional LLM polish | deferred |

**Runtime today:** Web → Fastify `:3001`. Deep reading shells into
`services/api-py/.venv` via `tools/build-reading.py`. FastAPI is ready beside it
but not the default `NEXT_PUBLIC_API_BASE_URL`.

## Recently landed (2026-08-01)

- Boundary warnings on TS artifacts + “Birth-time sensitive” chart chip
- Reading 503 when `.venv` missing (`reading_venv_missing`)
- DM Sans (quiet Next font warnings); root TypeScript pinned to ~5.9.3
- Navy CTA / badge cleanup on clients, intake, chart chrome
- Enriched predictions + Reading panel

## Remaining (ordered)

1. **5.1 FastAPI cutover** - envelope audit, smoke intake → chart → reading → predictions
2. **Reports on FastAPI** - PDF download after cutover
3. **4.1 Assistant port** - Ollama tool-loop + mock mode
4. **4.2 Faithfulness harness**
5. Finish any leftover gold CSS aliases once pages are on shadcn

## Working method
One vertical slice per session; TDD for engines; commit when asked.
