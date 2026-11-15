"use client";

import { Dialog } from "radix-ui";
import { useEffect, useState, type ReactNode } from "react";

import { Select } from "@/components/ui/select";
import { Btn } from "@/components/ankana/ui";
import { v1Api, type ClientInput, type ClientV1 } from "@/lib/api/live";
import { problemMessage } from "@/lib/api/v1";
import { cn } from "@/lib/utils";

const LANGS = [
  { value: "en", label: "English" },
  { value: "hi", label: "Hindi" },
  { value: "mr", label: "Marathi" },
  { value: "ta", label: "Tamil" },
  { value: "bn", label: "Bengali" },
];
const ZONES = [
  { value: "Asia/Kolkata", label: "India (IST)" },
  { value: "Europe/London", label: "United Kingdom" },
  { value: "America/New_York", label: "US Eastern" },
  { value: "America/Los_Angeles", label: "US Pacific" },
  { value: "Asia/Dubai", label: "Gulf (GST)" },
  { value: "Asia/Singapore", label: "Singapore" },
  { value: "Australia/Sydney", label: "Sydney" },
];

function Field({ label, htmlFor, children }: { label: string; htmlFor?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-[6px]">
      <label htmlFor={htmlFor} className="text-[13px] font-bold leading-4 text-body">
        {label}
      </label>
      {children}
    </div>
  );
}

const INPUT =
  "h-[42px] w-full rounded-[6px] border border-rule bg-white px-3 text-[15px] leading-5 text-ink outline-none placeholder:text-soft focus:border-sindoor";

/** Create or edit a client (POST / PATCH /v1/clients). `client` switches it to edit mode. */
export function ClientFormDialog({
  open,
  onOpenChange,
  client,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  client?: ClientV1 | null;
  onSaved: (c: ClientV1) => void;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [zone, setZone] = useState("Asia/Kolkata");
  const [lang, setLang] = useState("en");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setName(client?.display_name ?? "");
    setEmail(client?.contact_email ?? "");
    setPhone(client?.contact_phone ?? "");
    setZone(client?.timezone ?? "Asia/Kolkata");
    setLang(client?.preferred_language ?? "en");
    setError("");
  }, [open, client]);

  async function save() {
    setBusy(true);
    setError("");
    const body: ClientInput = {
      display_name: name.trim(),
      contact_email: email.trim() || null,
      contact_phone: phone.trim() || null,
      timezone: zone,
      preferred_language: lang,
    };
    try {
      const saved = client ? await v1Api.updateClient(client.id, body) : await v1Api.createClient(body);
      onSaved(saved);
      onOpenChange(false);
    } catch (cause) {
      setError(problemMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-[rgba(34,30,29,0.35)]" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed left-1/2 top-1/2 z-50 flex w-[calc(100vw-32px)] max-w-[460px] -translate-x-1/2 -translate-y-1/2 flex-col gap-4 rounded-[10px] border border-rule bg-white p-6 shadow-[0_24px_60px_rgba(34,30,29,0.18)]"
        >
          <Dialog.Title className="m-0 text-[20px] font-bold leading-6 tracking-[-0.01em] text-ink">{client ? "Edit client" : "New client"}</Dialog.Title>
          <form
            className="flex flex-col gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (name.trim() && !busy) void save();
            }}
          >
            <Field label="Full name" htmlFor="cf-name">
              <input id="cf-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Full name" autoComplete="off" className={INPUT} />
            </Field>
            <div className="flex flex-col gap-4 sm:flex-row">
              <Field label="Email" htmlFor="cf-email">
                <input id="cf-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Optional" className={INPUT} />
              </Field>
              <Field label="Phone" htmlFor="cf-phone">
                <input id="cf-phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Optional" className={INPUT} />
              </Field>
            </div>
            <div className="flex gap-4">
              <Field label="Time zone">
                <Select aria-label="Time zone" value={zone} onValueChange={setZone} options={ZONES} />
              </Field>
              <Field label="Language">
                <Select aria-label="Preferred language" value={lang} onValueChange={setLang} options={LANGS} />
              </Field>
            </div>
            {error ? (
              <p role="alert" className="m-0 rounded-[6px] bg-alert-wash px-[14px] py-[10px] text-[14px] font-bold leading-[18px] text-alert">
                {error}
              </p>
            ) : null}
            <div className="flex justify-end gap-2">
              <Btn variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Btn>
              <Btn type="submit" disabled={!name.trim() || busy}>
                {busy ? "Saving" : client ? "Save changes" : "Create client"}
              </Btn>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
