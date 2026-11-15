"use client";

import { useCallback, useEffect, useState } from "react";

import { OptionSelect, Toggle } from "@/components/ankana/option-select";
import { Chip, Panel } from "@/components/ankana/ui";
import { KIND_LABEL, notifyApi } from "@/lib/api/notify";
import type { NotificationPrefs, NotificationRow } from "@/lib/api/notify";

const HOURS = Array.from({ length: 24 }, (_, h) => {
  const v = `${String(h).padStart(2, "0")}:00`;
  return { value: v, label: v };
});
const LANGS = [
  { value: "en", label: "English" },
  { value: "hi", label: "Hindi" },
];
const CHANNELS = [
  { key: "email_opt_in", label: "Email" },
  { key: "whatsapp_opt_in", label: "WhatsApp" },
  { key: "sms_opt_in", label: "SMS" },
] as const;
const STATUS_TONE = { sent: "ok", pending: "accent", failed: "alert", skipped: "muted", cancelled: "muted" } as const;

const hhmm = (t: string) => t.slice(0, 5);

/** Reminders section of the client page: channels, quiet hours, language, recent sends. */
export function RemindersPanel({ clientId }: { clientId: string }) {
  const [prefs, setPrefs] = useState<NotificationPrefs | null>(null);
  const [rows, setRows] = useState<NotificationRow[]>([]);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [p, n] = await Promise.all([notifyApi.prefs(clientId), notifyApi.list(clientId)]);
      setPrefs(p);
      setRows(n.notifications);
    } catch {
      setUnavailable(true);
    }
  }, [clientId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function save(patch: Partial<NotificationPrefs>) {
    setError(null);
    try {
      setPrefs(await notifyApi.savePrefs(clientId, patch));
    } catch {
      setError("That change could not be saved.");
    }
  }

  async function resend(id: string) {
    setError(null);
    try {
      await notifyApi.resend(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not resend.");
    }
  }

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <h2 className="m-0 text-[20px] font-bold leading-6 text-ink">Reminders</h2>
        <span className="text-[13px] leading-4 text-soft">Daily remedy messages</span>
      </div>
      <Panel className="flex flex-col">
        {unavailable ? (
          <div className="px-4 py-[14px] text-[14px] leading-5 text-body">Reminders are not available for this client yet.</div>
        ) : !prefs ? (
          <div className="px-4 py-[14px] text-[14px] leading-5 text-soft">Loading reminders.</div>
        ) : (
          <>
            {!prefs.reminders_consent ? (
              <div className="border-b border-rule bg-wash-soft px-4 py-3 text-[13px] leading-[18px] text-body">
                Nothing is sent until the client gives consent for reminders. Record it under consents.
              </div>
            ) : null}
            {CHANNELS.map((c) => (
              <div key={c.key} className="flex items-center justify-between gap-3 border-b border-rule px-4 py-3">
                <span className="text-[14px] font-bold leading-[18px] text-ink">{c.label}</span>
                <Toggle on={prefs[c.key]} label={`${c.label} reminders`} onChange={(v) => void save({ [c.key]: v })} />
              </div>
            ))}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-4 py-3">
              <span className="text-[14px] font-bold leading-[18px] text-ink">Language</span>
              <OptionSelect label="Language" value={prefs.language} options={LANGS} onChange={(v) => void save({ language: v as "en" | "hi" })} />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
              <span className="text-[14px] font-bold leading-[18px] text-ink">Quiet hours</span>
              <div className="flex items-center gap-2 text-[13px] text-soft">
                <OptionSelect label="Quiet from" value={hhmm(prefs.quiet_start)} options={HOURS} onChange={(v) => void save({ quiet_start: v })} />
                to
                <OptionSelect label="Quiet until" value={hhmm(prefs.quiet_end)} options={HOURS} onChange={(v) => void save({ quiet_end: v })} />
              </div>
            </div>
          </>
        )}
        {error ? <div className="border-t border-rule px-4 py-2 text-[13px] leading-4 text-alert">{error}</div> : null}
      </Panel>
      {rows.length ? (
        <Panel className="flex flex-col">
          {rows.map((n, i) => (
            <div key={n.id} className={`flex items-center gap-3 px-4 py-3 ${i === rows.length - 1 ? "" : "border-b border-rule"}`}>
              <div className="flex grow flex-col">
                <div className="text-[14px] font-bold leading-[18px] text-ink">{KIND_LABEL[n.kind] ?? n.kind}</div>
                <div className="text-[12px] leading-4 text-soft">
                  {n.channel}, {n.local_date}
                  {n.skip_reason ? `, ${n.skip_reason.replace("_", " ")}` : ""}
                </div>
              </div>
              <Chip tone={STATUS_TONE[n.status]} className="py-[3px]">{n.status}</Chip>
              {n.status === "failed" || n.status === "skipped" ? (
                <button type="button" onClick={() => void resend(n.id)} className="text-[13px] font-bold leading-4 text-accent-text">
                  Resend
                </button>
              ) : null}
            </div>
          ))}
        </Panel>
      ) : null}
    </section>
  );
}
