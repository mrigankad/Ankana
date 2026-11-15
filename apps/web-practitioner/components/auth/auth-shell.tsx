import type { ComponentProps, ReactNode } from "react";

import { AnkanaLockup } from "@/components/ankana/logo";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

/** Full-page frame for sign-in, sign-up and invite screens: wash background, one card. */
export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const t = useT();
  return (
    <main
      className="flex min-h-svh flex-col items-center justify-center px-4 py-10"
      style={{ backgroundColor: "var(--surface-2)", backgroundImage: "radial-gradient(900px 420px at 50% -10%, var(--surface) 0%, var(--surface-2) 70%)" }}
    >
      <div className="mb-7">
        <AnkanaLockup wordSize={22} />
      </div>
      <div
        className="w-full max-w-[420px] rounded-[10px] border border-rule bg-white p-6 sm:p-8"
        style={{ boxShadow: "0 1px 2px rgba(34,30,29,0.04), 0 14px 36px rgba(34,30,29,0.08)" }}
      >
        <h1 className="text-[24px] font-bold leading-[30px] text-ink" style={{ letterSpacing: "-0.01em" }}>
          {t(title)}
        </h1>
        {subtitle ? <p className="mt-1 text-[15px] leading-[22px] text-body">{typeof subtitle === "string" ? t(subtitle) : subtitle}</p> : null}
        <div className="mt-6 flex flex-col gap-4">{children}</div>
      </div>
      <div className="mt-5 max-w-[420px] text-center text-[13px] leading-5 text-body">{footer}</div>
      <p className="mt-6 text-[12px] leading-4 text-soft">{t("Ankana is open source (AGPL-3.0) and runs on your own server.")}</p>
    </main>
  );
}

export function Field({
  label,
  hint,
  id,
  className,
  ...props
}: { label: string; hint?: string; id: string } & ComponentProps<"input">) {
  const t = useT();
  return (
    <div className="flex flex-col gap-[6px]">
      <label htmlFor={id} className="text-[13px] font-bold leading-4 text-ink">
        {t(label)}
      </label>
      <input
        id={id}
        className={cn(
          "h-11 w-full rounded-[6px] border border-rule bg-white px-3 text-[16px] leading-6 text-ink outline-none transition-shadow",
          "placeholder:text-soft focus:border-sindoor focus:ring-[3px] focus:ring-[color-mix(in_srgb,var(--accent)_25%,transparent)] disabled:bg-sidebar-wash",
          className,
        )}
        {...props}
      />
      {hint ? <span className="text-[12px] leading-4 text-soft">{t(hint)}</span> : null}
    </div>
  );
}

export function SubmitButton({ children, busy, disabled }: { children: ReactNode; busy?: boolean; disabled?: boolean }) {
  const t = useT();
  return (
    <Button type="submit" size="lg" loading={busy} disabled={disabled} className="h-11 w-full text-[15px] font-bold">
      {busy ? t("One moment") : children}
    </Button>
  );
}

export function FormError({ children }: { children?: ReactNode }) {
  if (!children) return null;
  return (
    <div role="alert" className="rounded-[6px] bg-alert-wash px-3 py-[10px] text-[14px] leading-5 text-alert">
      {children}
    </div>
  );
}

export function LinkButton({ children, ...props }: ComponentProps<"button">) {
  return (
    <Button type="button" variant="link" size="sm" className="h-auto px-0 text-[14px] font-bold text-accent-text" {...props}>
      {children}
    </Button>
  );
}

/** Six digit code box: one input so paste and one-time-code autofill both work. */
export function CodeField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <Field
      id="code"
      label="Six digit code"
      inputMode="numeric"
      autoComplete="one-time-code"
      maxLength={6}
      value={value}
      onChange={(e) => onChange(e.target.value.replace(/\D/g, "").slice(0, 6))}
      placeholder="000000"
      className="h-14 text-center text-[28px] font-bold tracking-[0.5em] tabular-nums"
      autoFocus
    />
  );
}
