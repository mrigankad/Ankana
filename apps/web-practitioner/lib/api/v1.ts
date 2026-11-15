import type { paths } from "./generated/schema";
import { getApiBaseUrl } from "./client";
import { authEnabled, getFreshToken, getSession } from "../auth/session";

/**
 * Thin typed wrapper over the generated /v1 contract (services/api-py/openapi.json).
 * Regenerate types with:
 *   npx openapi-typescript ../../services/api-py/openapi.json -o lib/api/generated/schema.d.ts
 * Auth is Bearer + X-Practice-Id. For local dev set NEXT_PUBLIC_V1_TOKEN and
 * NEXT_PUBLIC_PRACTICE_ID (token from POST /v1/dev/token with AUTH_DEV_STUB=1; see
 * scripts/dev-bootstrap.mjs). Errors are problem+json; lists use cursor pagination (next_cursor).
 */
export type V1Paths = paths;

export interface Problem {
  title?: string;
  detail?: string;
  type?: string;
  code?: string;
  status?: number;
  purpose?: string;
  errors?: Array<{ loc?: string[]; msg?: string; type?: string }>;
}

export class ProblemError extends Error {
  constructor(
    public status: number,
    public problem: Problem | null,
  ) {
    super(problem?.detail ?? problem?.title ?? `HTTP ${status}`);
  }
  get code() {
    return this.problem?.code ?? "";
  }
}

/** Auth headers: built-in session when auth is enabled, else the dev stub env token. */
export async function authHeaders(): Promise<Record<string, string>> {
  const h: Record<string, string> = {};
  if (authEnabled()) {
    const token = await getFreshToken();
    if (token) h.Authorization = `Bearer ${token}`;
    const practice = getSession().practiceId;
    if (practice) h["X-Practice-Id"] = practice;
    return h;
  }
  const token = process.env.NEXT_PUBLIC_V1_TOKEN;
  const practice = process.env.NEXT_PUBLIC_PRACTICE_ID;
  if (token) h.Authorization = `Bearer ${token}`;
  if (practice) h["X-Practice-Id"] = practice;
  return h;
}

const COPY: Record<string, string> = {
  consent_required: "This client has not agreed to chart calculation yet. Record their consent first.",
  not_found: "That record could not be found. It may have been removed.",
  validation_error: "Some details are missing or not valid. Check the highlighted fields.",
  unsupported_setting: "That chart setting is not supported yet.",
  chart_compute_failed: "The chart could not be calculated from these birth details. Check the date, time and place.",
  ai_unavailable: "The assistant is not switched on for this practice yet.",
  ai_provider_error: "The assistant could not answer just now. Try again in a moment.",
  invalid_cursor: "The list moved while you were reading it. Reload to continue.",
  idempotency_key_reuse: "That request was already sent with different details. Reload and try again.",
  rate_limited: "Too many requests. Wait a few seconds and try again.",
  unauthorized: "Your session has expired. Sign in again.",
  forbidden: "You do not have permission to do that.",
};

/** Friendly sentence for any thrown value. Never leaks stack traces or raw JSON. */
export function problemMessage(err: unknown, fallback = "Something went wrong. Try again."): string {
  if (err instanceof ProblemError) {
    const code = err.code || ({ 401: "unauthorized", 403: "forbidden", 404: "not_found", 429: "rate_limited" } as Record<number, string>)[err.status] || "";
    if (code === "consent_required" && err.problem?.purpose) {
      return `This client has not agreed to ${err.problem.purpose.replace(/_/g, " ")} yet. Record their consent first.`;
    }
    if (COPY[code]) return COPY[code]!;
    if (err.status >= 500) return "The server had a problem. Try again in a moment.";
    return err.problem?.detail && err.problem.detail.length < 160 ? err.problem.detail : fallback;
  }
  if (err instanceof DOMException && err.name === "AbortError") return "The server took too long to answer. Try again.";
  if (err instanceof TypeError) return "Cannot reach the Ankana server. Check your connection.";
  return fallback;
}

async function parseProblem(res: Response): Promise<ProblemError> {
  let problem: Problem | null = null;
  try {
    const body = (await res.json()) as Problem & { detail?: unknown };
    problem = typeof body === "object" && body ? { ...body, detail: typeof body.detail === "string" ? body.detail : undefined } : null;
  } catch {
    // not problem+json
  }
  return new ProblemError(res.status, problem);
}

export interface RequestOpts {
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  idempotencyKey?: string;
  timeoutMs?: number;
  signal?: AbortSignal;
}

function qs(query?: RequestOpts["query"]) {
  if (!query) return "";
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
}

export async function v1Request<T = unknown>(method: string, path: string, opts: RequestOpts = {}): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), opts.timeoutMs ?? 15000);
  opts.signal?.addEventListener("abort", () => ctrl.abort());
  try {
    const headers: Record<string, string> = { ...(await authHeaders()) };
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    if (opts.idempotencyKey) headers["Idempotency-Key"] = opts.idempotencyKey;
    const res = await fetch(`${getApiBaseUrl()}/v1${path}${qs(opts.query)}`, {
      method,
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      signal: ctrl.signal,
    });
    if (!res.ok) throw await parseProblem(res);
    if (res.status === 204) return undefined as T;
    const out = (await res.json()) as T;
    // Expose status for callers that care (200 vs 201 on idempotent create).
    if (out && typeof out === "object") Object.defineProperty(out, "__status", { value: res.status, enumerable: false });
    return out;
  } finally {
    clearTimeout(timer);
  }
}

export const v1Get = <T = unknown>(path: string, timeoutMs = 2500, query?: RequestOpts["query"]) =>
  v1Request<T>("GET", path, { timeoutMs, query });
export const v1Post = <T = unknown>(path: string, body?: unknown, opts: Omit<RequestOpts, "body"> = {}) =>
  v1Request<T>("POST", path, { ...opts, body: body ?? {} });
export const v1Patch = <T = unknown>(path: string, body: unknown) => v1Request<T>("PATCH", path, { body });
export const v1Put = <T = unknown>(path: string, body: unknown) => v1Request<T>("PUT", path, { body });

export interface MetaInfo {
  source_url?: string;
  git_sha?: string;
  /** true on the hosted service; self-hosted deployments have no billing. */
  billing?: boolean;
}

/** GET /v1/meta: public, used for the AGPL source link. */
export function getMeta() {
  return v1Get<MetaInfo>("/meta");
}

/** A stable-per-attempt key so double clicks and retries do not create duplicates. */
export function newIdempotencyKey(prefix = "web") {
  const rnd = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : String(Math.random()).slice(2);
  return `${prefix}-${rnd}`;
}

export interface SseEvent {
  event: string;
  data: unknown;
}

/** POST an SSE endpoint and yield parsed events. */
export async function* v1Sse(path: string, body: unknown, signal?: AbortSignal): AsyncGenerator<SseEvent> {
  const res = await fetch(`${getApiBaseUrl()}/v1${path}`, {
    method: "POST",
    headers: { ...(await authHeaders()), "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) throw await parseProblem(res);
  if (!res.body) return;
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let event = "message";
      const data: string[] = [];
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).trim());
      }
      if (!data.length) continue;
      try {
        yield { event, data: JSON.parse(data.join("\n")) };
      } catch {
        yield { event, data: data.join("\n") };
      }
    }
  }
}
