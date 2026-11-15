import "@testing-library/jest-dom/vitest";
import React from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EngineSettings } from "./ankana/engine-settings";
import { chooseSelectOption } from "@/components/ui/test-utils";
import { dotFor } from "@/lib/api/ai";
import type { AiConnection } from "@/lib/api/ai";

const models = { top: "gpt-oss:120b", strong: "gpt-oss:20b", fast: "gpt-oss:20b" };
const conn = (over: Partial<AiConnection> = {}): AiConnection => ({
  id: "c1", kind: "ollama_cloud", label: "Ollama Cloud", base_url: null, has_key: true,
  models: { top: null, strong: null, fast: null }, effective_models: models, enabled: true,
  local: false, allowed: true, ...over,
});
const kind = (k: string, logo: string, over: Record<string, unknown> = {}) => ({
  kind: k, label: k, description: "d", logo, local: false, requires_key: false, requires_base_url: false,
  default_base_url: null, default_models: models, available: true, allowed: true, status: "ready", detail: "", ...over,
});
const PROVIDERS = {
  kinds: [
    kind("ollama_cloud", "ollama.svg", { requires_key: true, label: "Ollama Cloud" }),
    kind("claude_code", "claude.svg", { local: true, label: "Claude Code (this computer)" }),
    kind("codex", "openai.svg", { local: true, allowed: false, label: "Codex CLI (this computer)" }),
  ],
  local_providers_allowed: false, secret_key_configured: true,
  roles: ["classify", "narrate", "synthesise", "report"],
  presets: ["best_quality", "balanced", "lowest_cost", "local_only"],
};
const ROUTING = { routes: [], preset: null, presets: PROVIDERS.presets, roles: PROVIDERS.roles };

function mockApi(connections: AiConnection[], extra: (url: string, init?: RequestInit) => unknown = () => undefined) {
  const calls: { url: string; method: string; body?: string }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input).replace(/^https?:\/\/[^/]+\/v1/, "");
    calls.push({ url, method: init?.method ?? "GET", body: init?.body as string | undefined });
    const custom = extra(url, init);
    const body = custom !== undefined ? custom
      : url === "/ai/providers" ? PROVIDERS
      : url === "/ai/connections" ? connections
      : url === "/ai/routing" ? ROUTING : {};
    return { ok: true, status: 200, json: async () => body } as Response;
  });
  return calls;
}

describe("EngineSettings", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows provider logos, status dot and never a key", async () => {
    mockApi([conn()]);
    const { container } = render(React.createElement(EngineSettings));
    const card = await screen.findByTestId("connection-card");
    expect(within(card).getByText("Key saved")).toBeInTheDocument();
    expect(card.querySelector('[data-slot="provider-logo"]')).not.toBeNull();
    expect(within(card).getByTestId("status-dot")).toHaveAttribute("data-state", "idle");
    expect(container.textContent).not.toMatch(/[–—]/); // no en or em dashes
    expect(screen.getByRole("heading", { name: /engine & models/i })).toBeInTheDocument();
  });

  it("test button reports latency and turns the dot green", async () => {
    mockApi([conn()], (url) => (url === "/ai/connections/c1/test"
      ? { ok: true, latency_ms: 412, model: "gpt-oss:20b", error: null } : undefined));
    render(React.createElement(EngineSettings));
    fireEvent.click(await screen.findByRole("button", { name: "Test" }));
    expect(await screen.findByText(/Answered in 412 ms with gpt-oss:20b/)).toBeInTheDocument();
    expect(screen.getByTestId("status-dot")).toHaveAttribute("data-state", "ok");
  });

  it("failed test shows the error and a red dot", async () => {
    mockApi([conn()], (url) => (url === "/ai/connections/c1/test"
      ? { ok: false, latency_ms: 9, model: null, error: "Could not reach https://ollama.com" } : undefined));
    render(React.createElement(EngineSettings));
    fireEvent.click(await screen.findByRole("button", { name: "Test" }));
    expect(await screen.findByText(/Could not reach/)).toBeInTheDocument();
    expect(screen.getByTestId("status-dot")).toHaveAttribute("data-state", "bad");
  });

  it("preset buttons call the preset endpoint", async () => {
    const calls = mockApi([conn()], (url) => (url === "/ai/routing/preset"
      ? { ...ROUTING, preset: "lowest_cost" } : undefined));
    render(React.createElement(EngineSettings));
    fireEvent.click(await screen.findByRole("button", { name: /lowest cost/i }));
    await waitFor(() => expect(screen.getByRole("button", { name: /lowest cost/i })).toHaveAttribute("aria-pressed", "true"));
    expect(calls.find((c) => c.url === "/ai/routing/preset")?.body).toBe('{"preset":"lowest_cost"}');
  });

  it("changing a route sends only that role", async () => {
    const calls = mockApi([conn()]);
    render(React.createElement(EngineSettings));
    const select = await screen.findByLabelText("Synthesise connection");
    chooseSelectOption(select, "Ollama Cloud");
    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
    expect(JSON.parse(calls.find((c) => c.method === "PUT")!.body!)).toEqual({
      routes: [{ role: "synthesise", connection_id: "c1", model: null }],
    });
  });

  it("add dialog lists provider logos, disables turned-off kinds and posts the key once", async () => {
    const calls = mockApi([], (url, init) => (url === "/ai/connections" && init?.method === "POST" ? conn() : undefined));
    render(React.createElement(EngineSettings));
    fireEvent.click(await screen.findByRole("button", { name: "Add connection" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog.querySelectorAll('[data-slot="provider-logo"]').length).toBeGreaterThanOrEqual(3);
    expect(within(dialog).getByRole("button", { name: /Codex CLI/ })).toBeDisabled();
    fireEvent.click(within(dialog).getByRole("button", { name: /Ollama Cloud/ }));
    const keyField = within(dialog).getByLabelText(/API key/) as HTMLInputElement;
    expect(keyField.type).toBe("password");
    fireEvent.change(keyField, { target: { value: "secret-123" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Add connection" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect(JSON.parse(calls.find((c) => c.method === "POST")!.body!).api_key).toBe("secret-123");
  });

  it("dotFor prefers the last test, then availability", () => {
    const k = PROVIDERS.kinds[1] as never;
    expect(dotFor(conn(), k, undefined)).toBe("idle");
    expect(dotFor(conn(), { ...(k as object), available: false } as never, undefined)).toBe("bad");
    expect(dotFor(conn({ enabled: false }), k, { ok: true, latency_ms: 1, model: null, error: null })).toBe("idle");
  });
});
