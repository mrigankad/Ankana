"use client";

import { useEffect, useState } from "react";

import { Topbar } from "@/components/ankana/topbar";
import { Btn, Panel } from "@/components/ankana/ui";
import { isFixtures } from "@/lib/api/client";
import { v1Api, type BrandingV1 } from "@/lib/api/live";
import { problemMessage } from "@/lib/api/v1";

const HEX = /^#[0-9a-fA-F]{6}$/;
const INPUT = "h-[42px] w-full rounded-[6px] border border-rule bg-white px-3 text-[15px] leading-5 text-ink outline-none placeholder:text-soft focus:border-sindoor";

function Field({ label, hint, htmlFor, children }: { label: string; hint?: string; htmlFor?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-[6px]">
      <label htmlFor={htmlFor} className="text-[13px] font-bold leading-4 text-body">
        {label}
      </label>
      {children}
      {hint ? <div className="text-[12px] leading-4 text-soft">{hint}</div> : null}
    </div>
  );
}

function ColorField({ id, label, value, onChange }: { id: string; label: string; value: string; onChange: (v: string) => void }) {
  const ok = !value || HEX.test(value);
  return (
    <Field label={label} htmlFor={id} hint={ok ? "Six digit hex, for example D32704. Leave empty for the default." : undefined}>
      <div className="flex items-center gap-2">
        <span className="size-[42px] shrink-0 rounded-[6px] border border-rule" style={{ backgroundColor: ok && value ? value : "transparent" }} aria-hidden />
        <input id={id} value={value} onChange={(e) => onChange(e.target.value.startsWith("#") || !e.target.value ? e.target.value : `#${e.target.value}`)} placeholder="#" className={INPUT} />
      </div>
      {!ok ? <div className="text-[12px] font-bold leading-4 text-alert">Use a six digit hex colour such as #D32704.</div> : null}
    </Field>
  );
}

/** Practice branding used on every PDF report (GET/PUT /v1/practice/branding, owner only). */
export default function BrandingPage() {
  const [b, setB] = useState<BrandingV1 | null>(null);
  const [logo, setLogo] = useState("");
  const [primary, setPrimary] = useState("");
  const [accent, setAccent] = useState("");
  const [footer, setFooter] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (isFixtures()) return;
    v1Api
      .getBranding()
      .then((r) => {
        setB(r);
        setLogo(r.logo_url ?? "");
        setPrimary(r.brand_primary_color ?? "");
        setAccent(r.brand_accent_color ?? "");
        setFooter(r.brand_footer ?? "");
      })
      .catch((e) => setError(problemMessage(e)));
  }, []);

  const valid = (!primary || HEX.test(primary)) && (!accent || HEX.test(accent));

  async function save() {
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const r = await v1Api.updateBranding({
        logo_url: logo.trim() || null,
        brand_primary_color: primary || null,
        brand_accent_color: accent || null,
        brand_footer: footer.trim() || null,
      });
      setB(r);
      setSaved(true);
    } catch (cause) {
      setError(problemMessage(cause, "Branding could not be saved."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Topbar crumbs={[{ label: "Settings" }, { label: "Branding" }]} />
      <main className="flex flex-1 flex-col gap-6 px-5 py-8 lg:px-10">
        <div className="flex flex-col gap-1">
          <h1 className="m-0 text-[28px] font-bold leading-[34px] tracking-[-0.02em] text-ink lg:text-[32px] lg:leading-[38px]">Branding</h1>
          <p className="m-0 text-[15px] leading-5 text-body">Your name, logo, colours and footer appear on every report you export.</p>
        </div>
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
          <Panel className="flex w-full flex-col gap-4 p-6 lg:w-[520px]">
            <Field label="Practice name" hint="Change the name from the practice settings.">
              <input aria-label="Practice name" value={b?.name ?? ""} readOnly className={`${INPUT} bg-sidebar-wash`} />
            </Field>
            <Field label="Logo address" htmlFor="br-logo" hint="A secure https link to a square PNG or SVG.">
              <input id="br-logo" value={logo} onChange={(e) => setLogo(e.target.value)} placeholder="https://" className={INPUT} />
            </Field>
            <div className="flex flex-col gap-4 sm:flex-row">
              <ColorField id="br-primary" label="Primary colour" value={primary} onChange={setPrimary} />
              <ColorField id="br-accent" label="Accent colour" value={accent} onChange={setAccent} />
            </div>
            <Field label="Report footer" htmlFor="br-footer" hint={`${footer.length} of 200 characters`}>
              <input id="br-footer" value={footer} maxLength={200} onChange={(e) => setFooter(e.target.value)} placeholder="Address, phone, disclaimer" className={INPUT} />
            </Field>
            {error ? (
              <p role="alert" className="m-0 rounded-[6px] bg-alert-wash px-[14px] py-[10px] text-[14px] font-bold leading-[18px] text-alert">
                {error}
              </p>
            ) : null}
            {saved ? (
              <p role="status" className="m-0 rounded-[6px] bg-ok-wash px-[14px] py-[10px] text-[14px] font-bold leading-[18px] text-ok">
                Branding saved. New reports use it.
              </p>
            ) : null}
            <div className="flex justify-end">
              <Btn onClick={() => void save()} disabled={busy || !valid || isFixtures()}>
                {busy ? "Saving" : "Save branding"}
              </Btn>
            </div>
          </Panel>

          <Panel className="flex w-full flex-col gap-3 p-6 lg:w-[360px]" aria-label="Report header preview">
            <div className="text-[12px] font-bold leading-4 tracking-[0.06em] text-soft">REPORT HEADER PREVIEW</div>
            <div className="flex items-center gap-3 rounded-[8px] border border-rule p-4">
              {logo ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={logo} alt="" className="size-10 rounded-[5px] object-contain" />
              ) : (
                <span className="flex size-10 items-center justify-center rounded-[5px]" style={{ backgroundColor: HEX.test(primary) ? primary : "var(--color-ink)" }}>
                  <span className="size-3 rotate-45" style={{ backgroundColor: HEX.test(accent) ? accent : "var(--color-accent-light)" }} />
                </span>
              )}
              <div className="text-[18px] font-bold leading-6" style={{ color: HEX.test(primary) ? primary : "var(--color-ink)" }}>
                {b?.name ?? "Your practice"}
              </div>
            </div>
            <div className="border-t pt-2 text-[12px] leading-4 text-soft" style={{ borderColor: HEX.test(accent) ? accent : "var(--color-rule)" }}>
              {footer || "Advisory only. Traditional practice, not a prediction or prescription."}
            </div>
          </Panel>
        </div>
      </main>
    </>
  );
}
