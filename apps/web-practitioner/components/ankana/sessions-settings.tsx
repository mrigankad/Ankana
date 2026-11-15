"use client";

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { Chip, Panel } from "@/components/ankana/ui";
import { Banner } from "@/components/ui/data";
import { SampleBadge } from "@/components/ankana/server-unavailable";
import { isFixtures } from "@/lib/api/client";
import { fxSessions } from "@/lib/api/fixture-admin";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { authApi, AuthApiError, type DeviceSession } from "@/lib/auth/api";
import { getFreshToken } from "@/lib/auth/session";
import { formatDay } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";

/** "Chrome on Windows" from a user-agent string. Best effort; falls back to "Unknown device". */
export function deviceLabel(ua: string | null): string {
  if (!ua) return "Unknown device";
  const browser = /Edg\//.test(ua) ? "Edge" : /Firefox\//.test(ua) ? "Firefox" : /Chrome\//.test(ua) ? "Chrome" : /Safari\//.test(ua) ? "Safari" : "Browser";
  const os = /iPhone|iPad/.test(ua) ? "iPhone" : /Android/.test(ua) ? "Android" : /Windows/.test(ua) ? "Windows" : /Mac OS X/.test(ua) ? "Mac" : /Linux/.test(ua) ? "Linux" : "";
  return os ? `${browser} on ${os}` : browser;
}

const METHOD: Record<string, string> = {
  otp: "Email code",
  email_code: "Email code",
  password: "Password",
  oidc: "Single sign-on",
};

function when(iso: string, t: (s: string) => string): string {
  const d = new Date(iso);
  if (Date.now() - d.getTime() < 120_000) return t("Active now");
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${formatDay(`${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`)}, ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function SessionsSettings() {
  const t = useT();
  const toast = useToast();
  const { enabled } = useAuth();
  const sample = isFixtures();
  const [rows, setRows] = useState<DeviceSession[] | null>(sample ? fxSessions : null);
  const [error, setError] = useState<string | null>(null);
  const [target, setTarget] = useState<DeviceSession | null>(null);
  const [allOthers, setAllOthers] = useState(false);
  // Relative times depend on the clock, so they render after mount to keep server and client markup equal.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const load = useCallback(async () => {
    try {
      const token = await getFreshToken();
      if (!token) throw new AuthApiError(401, "invalid_session", t("Sign in again to see your devices."));
      setRows((await authApi.listSessions(token)).sessions);
      setError(null);
    } catch (e) {
      setError(e instanceof AuthApiError ? e.message : t("Your devices could not be loaded."));
    }
  }, [t]);

  useEffect(() => {
    if (enabled && !sample) void load();
  }, [enabled, sample, load]);

  async function revoke(s: DeviceSession) {
    if (sample) {
      setRows((r) => (r ?? []).filter((x) => x.id !== s.id));
      toast(t("Sample mode: changes are not saved"));
      return;
    }
    try {
      const token = await getFreshToken();
      if (token) await authApi.revokeSession(token, s.id);
      toast(t("Signed out"), { tone: "success" });
    } catch (e) {
      toast(e instanceof AuthApiError ? e.message : t("That device could not be signed out."), { tone: "error" });
    }
    await load();
  }

  async function revokeOthers() {
    if (sample) {
      setRows((r) => (r ?? []).filter((x) => x.current));
      toast(t("Sample mode: changes are not saved"));
      return;
    }
    try {
      const token = await getFreshToken();
      if (token) await authApi.revokeOtherSessions(token);
      toast(t("Other devices signed out"), { tone: "success" });
    } catch (e) {
      toast(e instanceof AuthApiError ? e.message : t("The devices could not be signed out."), { tone: "error" });
    }
    await load();
  }

  const others = (rows ?? []).filter((r) => !r.current).length;

  return (
    <div className="flex flex-col gap-5 px-4 py-6 lg:px-10 lg:py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="m-0 text-[32px] font-bold leading-[38px] tracking-[-0.01em] text-ink">{t("Sessions")}{sample ? <SampleBadge className="ml-3 align-middle" /> : null}</h1>
          <p className="m-0 text-[15px] leading-5 text-body">
            {t("Every device that is signed in to your account. Sign out any you do not recognise.")}
          </p>
        </div>
        {others > 0 ? (
          <Button variant="outline" size="md" onClick={() => setAllOthers(true)}>
            {t("Sign out other devices")}
          </Button>
        ) : null}
      </div>

      {!enabled && !sample ? (
        <Banner tone="info">{t("Device sessions appear when built-in sign-in is switched on for this server.")}</Banner>
      ) : null}
      {error ? <Banner tone="error">{error}</Banner> : null}

      {enabled || sample ? (
        <Panel className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-left" aria-label={t("Signed-in devices")}>
            <thead className="bg-sidebar-wash">
              <tr className="text-[12px] font-bold text-soft">
                <th scope="col" className="px-5 py-[11px] font-bold">{t("DEVICE")}</th>
                <th scope="col" className="px-2 py-[11px] font-bold">{t("SIGNED IN WITH")}</th>
                <th scope="col" className="px-2 py-[11px] font-bold">{t("LAST ACTIVE")}</th>
                <th scope="col" className="px-5 py-[11px] text-right font-bold">{t("ACTION")}</th>
              </tr>
            </thead>
            <tbody>
              {(rows ?? []).map((s) => (
                <tr key={s.id} className={`border-t border-rule ${s.current ? "bg-wash-soft" : ""}`}>
                  <td className="px-5 py-[11px]">
                    <div className="flex flex-col">
                      <span className="flex items-center gap-2 text-[15px] font-bold leading-[19px] text-ink">
                        {t(deviceLabel(s.user_agent))}
                        {s.current ? <Chip tone="ok">{t("This device")}</Chip> : null}
                      </span>
                      <span className="text-[12px] leading-4 text-soft">{s.ip ?? ""}</span>
                    </div>
                  </td>
                  <td className="px-2 py-[11px] text-[14px] text-body">{t(METHOD[s.method] ?? "Email code")}</td>
                  <td className="px-2 py-[11px] text-[14px] text-body">{mounted ? when(s.last_used_at, t) : ""}</td>
                  <td className="px-5 py-[11px] text-right">
                    {s.current ? (
                      <span className="text-[13px] text-soft">{t("Current session")}</span>
                    ) : (
                      <Button variant="link" size="sm" className="h-auto p-0 text-[14px] font-bold text-alert no-underline hover:no-underline" onClick={() => setTarget(s)}>
                        {t("Sign out")}
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      ) : null}

      <ConfirmDialog
        open={!!target}
        onOpenChange={(o) => !o && setTarget(null)}
        tone="danger"
        title={t("Sign out this device?")}
        description={target ? t(deviceLabel(target.user_agent)) : undefined}
        confirmLabel={t("Sign out")}
        cancelLabel={t("Keep")}
        onConfirm={async () => {
          if (target) await revoke(target);
        }}
      />
      <ConfirmDialog
        open={allOthers}
        onOpenChange={setAllOthers}
        tone="danger"
        title={t("Sign out every other device?")}
        description={t("You stay signed in here. Everything else needs a new sign-in.")}
        confirmLabel={t("Sign out others")}
        cancelLabel={t("Keep")}
        onConfirm={revokeOthers}
      />
    </div>
  );
}
