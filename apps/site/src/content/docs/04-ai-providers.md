---
title: AI providers
order: 4
summary: Which model writes the narration, and why you can swap it freely.
---

The assistant answers from chart facts through tools. It writes sentences that carry structured claims, and a deterministic claim verifier compares every claim with the chart without calling a model. A claim that fails is rewritten once. If it still fails, the sentence is replaced by the verified chart fact and flagged as not verified. Because the check does not depend on the model, you can change the model without changing what is trusted.

## Built in today

Each practice adds one or more connections under **Library, Engine & models**, picks a routing preset (best quality, balanced, lowest cost, local only) and can test every connection with one click. If a connection fails, Ankana falls back to the next enabled one. API keys are encrypted at rest and never shown again.

| Provider | How it connects | Runs where |
|---|---|---|
| Claude Code | Your local `claude` login, no API key | Your machine |
| Codex | Your local `codex` login | Your machine |
| Gemini CLI | Your local `gemini` login | Your machine |
| Ollama | Local daemon (`http://localhost:11434`) | Your machine, fully offline |
| Ollama Cloud | `https://ollama.com` with an API key | Ollama's cloud |
| Gemini API | Google AI API key | Google |
| Anthropic API | API key | Anthropic |
| OpenAI compatible | Any OpenAI-style endpoint: OpenAI, OpenRouter, Groq, LiteLLM, LM Studio, vLLM | Wherever it points |
| Mock | Deterministic answers for tests and offline demos | Built in |

Providers that use a login on your own machine (Claude Code, Codex, Gemini CLI, local Ollama) are only enabled when you self-host with `ANKANA_ALLOW_LOCAL_PROVIDERS=1`. They are never offered on a shared hosted server.

The CLI providers do not take Ankana's tools natively, so Ankana asks them for a strict JSON reply and keeps the tool loop itself. That means every answer still goes through the same claim verifier.

## Which one to choose

- Choose Ollama if client data must never leave your machine.
- Choose a hosted provider if you want stronger models and accept that chart facts in the prompt go to that provider under its terms.
- Run the evaluation suite, `python -m ankana_ai.eval`, before trusting a new model. It uses the mock provider by default, and a manual live run is available.
