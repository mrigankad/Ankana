import { getApiBaseUrl, isFixtures, mode, withFixture } from "./client";
import { ProblemError, authHeaders, v1Get } from "./v1";

export type Tier = "top" | "strong" | "fast";
export type Models = Record<Tier, string | null>;

export interface ProviderKind {
  kind: string;
  label: string;
  description: string;
  logo: string;
  local: boolean;
  requires_key: boolean;
  requires_base_url: boolean;
  default_base_url: string | null;
  default_models: Record<Tier, string>;
  available: boolean;
  allowed: boolean;
  status: string;
  detail: string;
}

export interface ProvidersOut {
  kinds: ProviderKind[];
  local_providers_allowed: boolean;
  secret_key_configured: boolean;
  roles: string[];
  presets: string[];
}

export interface AiConnection {
  id: string;
  kind: string;
  label: string;
  base_url: string | null;
  has_key: boolean;
  models: Models;
  effective_models: Record<Tier, string>;
  enabled: boolean;
  local: boolean;
  allowed: boolean;
}

export interface AiRoute {
  role: string;
  connection_id: string | null;
  model: string | null;
}

export interface AiRouting {
  routes: AiRoute[];
  preset: string | null;
  presets: string[];
  roles: string[];
}

export interface TestResult {
  ok: boolean;
  latency_ms: number;
  model: string | null;
  error: string | null;
}

export interface NewConnection {
  kind: string;
  label: string;
  base_url?: string | null;
  api_key?: string | null;
  models?: Partial<Models>;
  enabled?: boolean;
}

export const ROLE_COPY: Record<string, { title: string; note: string }> = {
  classify: { title: "Classify", note: "Quick sorting of a question before it is answered." },
  narrate: { title: "Narrate", note: "Plain language wording of chart facts." },
  synthesise: { title: "Synthesise", note: "The assistant answering a question about a chart." },
  report: { title: "Report", note: "Longer written readings for reports." },
};

export const PRESET_COPY: Record<string, { title: string; note: string }> = {
  best_quality: { title: "Best quality", note: "Strongest model for every job." },
  balanced: { title: "Balanced", note: "Fast model for sorting, strong for answers." },
  lowest_cost: { title: "Lowest cost", note: "Smallest model that can do each job." },
  local_only: { title: "Local only", note: "Only models running on this computer." },
};

export const logoSrc = (file: string) => `/providers/${file}`;

export type Dot = "ok" | "bad" | "idle";

/** Status dot for a connection card: the last test result wins, then the kind's availability. */
export function dotFor(conn: AiConnection, kind: ProviderKind | undefined, test: TestResult | undefined): Dot {
  if (!conn.enabled || !conn.allowed) return "idle";
  if (test) return test.ok ? "ok" : "bad";
  if (kind && !kind.available) return "bad";
  return "idle";
}

async function send<T>(method: "POST" | "PUT" | "PATCH" | "DELETE", path: string, body?: unknown): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 120000);
  try {
    const res = await fetch(`${getApiBaseUrl()}/v1${path}`, {
      method,
      headers: { ...(await authHeaders()), ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (!res.ok) {
      let problem = null;
      try {
        problem = await res.json();
      } catch {
        // not problem+json
      }
      throw new ProblemError(res.status, problem);
    }
    return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
  } finally {
    clearTimeout(timer);
  }
}

const MODELS = (top: string, strong: string, fast: string): Record<Tier, string> => ({ top, strong, fast });

const providersFixture: ProvidersOut = {
  local_providers_allowed: true,
  secret_key_configured: true,
  roles: ["classify", "narrate", "synthesise", "report"],
  presets: ["best_quality", "balanced", "lowest_cost", "local_only"],
  kinds: [
    { kind: "claude_cli", label: "Claude Code (this computer)", description: "Uses the Claude Code login on this computer. No key needed.", logo: "claude.svg", local: true, requires_key: false, requires_base_url: false, default_base_url: null, default_models: MODELS("opus", "sonnet", "haiku"), available: true, allowed: true, status: "ready", detail: "" },
    { kind: "ollama_local", label: "Ollama (this computer)", description: "Models that run on this computer. Nothing leaves it.", logo: "ollama.svg", local: true, requires_key: false, requires_base_url: true, default_base_url: "http://127.0.0.1:11434", default_models: MODELS("qwen3:32b", "qwen3:14b", "qwen3:4b"), available: true, allowed: true, status: "ready", detail: "" },
  ],
};

const connectionsFixture: AiConnection[] = [
  { id: "sample-claude", kind: "claude_cli", label: "Claude Code", base_url: null, has_key: false, models: { top: null, strong: null, fast: null }, effective_models: MODELS("opus", "sonnet", "haiku"), enabled: true, local: true, allowed: true },
  { id: "sample-ollama", kind: "ollama_local", label: "Ollama", base_url: "http://127.0.0.1:11434", has_key: false, models: { top: null, strong: null, fast: null }, effective_models: MODELS("qwen3:32b", "qwen3:14b", "qwen3:4b"), enabled: true, local: true, allowed: true },
];

const routingFixture: AiRouting = {
  preset: "balanced",
  presets: providersFixture.presets,
  roles: providersFixture.roles,
  routes: [
    { role: "classify", connection_id: "sample-ollama", model: null },
    { role: "narrate", connection_id: "sample-claude", model: null },
    { role: "synthesise", connection_id: "sample-claude", model: null },
    { role: "report", connection_id: "sample-claude", model: null },
  ],
};

/** True when the engine screen is showing built-in sample data (nothing can be saved). */
export const isSampleEngine = () => isFixtures() || mode() === "auto";

/** Probe once so the screen can tell "API answered" from "showing samples". */
export async function engineIsSample(): Promise<boolean> {
  if (isFixtures()) return true;
  if (mode() === "live") return false;
  try {
    await v1Get<ProvidersOut>("/ai/providers", 2500);
    return false;
  } catch {
    return true;
  }
}

export const listProviders = () => withFixture(() => v1Get<ProvidersOut>("/ai/providers", 15000), () => providersFixture);
export const listConnections = () => withFixture(() => v1Get<AiConnection[]>("/ai/connections", 15000), () => connectionsFixture);
export const getRouting = () => withFixture(() => v1Get<AiRouting>("/ai/routing", 15000), () => routingFixture);
export const createConnection = (b: NewConnection) => send<AiConnection>("POST", "/ai/connections", b);
export const updateConnection = (id: string, b: Record<string, unknown>) =>
  send<AiConnection>("PATCH", `/ai/connections/${id}`, b);
export const deleteConnection = (id: string) => send<void>("DELETE", `/ai/connections/${id}`);
export const testConnection = (id: string) => send<TestResult>("POST", `/ai/connections/${id}/test`);
export const setRouting = (routes: AiRoute[]) => send<AiRouting>("PUT", "/ai/routing", { routes });
export const applyPreset = (preset: string) => send<AiRouting>("POST", "/ai/routing/preset", { preset });
