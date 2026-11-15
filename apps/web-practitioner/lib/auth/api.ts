import { getApiBaseUrl } from "@/lib/api/client";

export interface Membership {
  member_id: string;
  practice_id: string;
  practice_name: string;
  role: "owner" | "astrologer" | "assistant" | "client";
}

export interface AuthUser {
  id: string;
  email: string | null;
  name: string | null;
  has_password: boolean;
}

export interface SessionPayload {
  access_token?: string;
  expires_in?: number;
  session_id: string;
  user: AuthUser;
  memberships: Membership[];
  active_practice_id: string | null;
}

export interface AuthConfig {
  email_code: boolean;
  phone_code: boolean;
  password: boolean;
  signup: boolean;
  oidc: { id: string; label: string }[];
  password_min_length: number;
  otp_ttl_seconds: number;
}

export interface InvitePreview {
  practice_name: string;
  role: string;
  email: string;
  email_hint: string;
}

export interface DeviceSession {
  id: string;
  method: string;
  ip: string | null;
  user_agent: string | null;
  created_at: string;
  last_used_at: string;
  current: boolean;
}

export class AuthApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(
  path: string,
  init: { method?: string; body?: unknown; token?: string; csrf?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  if (init.token) headers.Authorization = `Bearer ${init.token}`;
  if (init.csrf) headers["X-Ankana-Csrf"] = "1";
  let res: Response;
  try {
    res = await fetch(`${getApiBaseUrl()}/v1/auth${path}`, {
      method: init.method ?? (init.body !== undefined ? "POST" : "GET"),
      headers,
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
      credentials: "include",
    });
  } catch {
    throw new AuthApiError(0, "network", "Could not reach the server. Check your connection.");
  }
  if (res.status === 204) return undefined as T;
  let json: { detail?: string; code?: string } | null = null;
  try {
    json = await res.json();
  } catch {
    json = null;
  }
  if (!res.ok) {
    throw new AuthApiError(res.status, json?.code ?? "error", json?.detail ?? `Request failed (${res.status})`);
  }
  return json as T;
}

export const authApi = {
  config: () => call<AuthConfig>("/config"),
  signup: (b: { email: string; name: string; practice_name?: string }) =>
    call<{ ok: true; expires_in: number }>("/signup", { body: b }),
  requestCode: (email: string) => call<{ ok: true; expires_in: number }>("/otp/request", { body: { email } }),
  verifyCode: (email: string, code: string) => call<SessionPayload>("/otp/verify", { body: { email, code } }),
  passwordSignin: (email: string, password: string) =>
    call<SessionPayload>("/password/signin", { body: { email, password } }),
  setPassword: (token: string, new_password: string, current_password?: string) =>
    call<void>("/password", { method: "PUT", body: { new_password, current_password }, token }),
  refresh: () => call<SessionPayload>("/refresh", { method: "POST", csrf: true }),
  signout: () => call<void>("/signout", { method: "POST", csrf: true }),
  createPractice: (token: string, name: string) =>
    call<{ practice_id: string }>("/practices", { body: { name }, token }),
  switchPractice: (token: string, practice_id: string) =>
    call<{ practice_id: string }>("/switch-practice", { body: { practice_id }, token }),
  listSessions: (token: string) => call<{ sessions: DeviceSession[] }>("/sessions", { token }),
  revokeSession: (token: string, id: string) => call<void>(`/sessions/${encodeURIComponent(id)}`, { method: "DELETE", token }),
  revokeOtherSessions: (token: string) => call<{ revoked: number }>("/sessions", { method: "DELETE", token }),
  previewInvite: (inviteToken: string) => call<InvitePreview>(`/invites/${encodeURIComponent(inviteToken)}`),
  acceptInvite: (token: string, inviteToken: string) =>
    call<{ practice_id: string; role: string }>(`/invites/${encodeURIComponent(inviteToken)}/accept`, {
      method: "POST",
      token,
    }),
  oidcStartUrl: (provider: string, next: string) =>
    `${getApiBaseUrl()}/v1/auth/oidc/${encodeURIComponent(provider)}/start?redirect=${encodeURIComponent(next)}`,
};
