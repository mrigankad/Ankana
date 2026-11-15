import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Soft status chip. Tones come straight from the Paper palette. */
const CHIP_TONES = {
  ok: "bg-ok-wash text-ok",
  alert: "bg-alert-wash text-alert",
  accent: "bg-wash text-accent-text",
  ink: "bg-chip text-ink",
  muted: "bg-sidebar-wash text-body",
} as const;
export type ChipTone = keyof typeof CHIP_TONES;

export function Chip({ tone = "ink", children, className }: { tone?: ChipTone; children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center rounded-[4px] px-2 py-[2px] text-[13px] font-bold leading-4", CHIP_TONES[tone], className)}>
      {children}
    </span>
  );
}

/** Raised surface used for the content cards in Paper. */
export function Panel({ className, style, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cn("rounded-[10px] border border-rule bg-white", className)}
      style={{ boxShadow: "0 1px 2px rgba(34,30,29,0.04), 0 6px 18px rgba(34,30,29,0.05)", ...style }}
      {...props}
    />
  );
}

/** Primary fill: flat sindoor with a quiet same-hue shade, never a gradient across hues. */
export const PRIMARY_FILL = "var(--fill-primary)";
export const PRIMARY_SHADOW = "0 1px 2px rgba(34,30,29,0.14)";

type BtnVariant = "primary" | "outline" | "ink" | "text";
const BTN_BASE = "inline-flex items-center justify-center gap-[6px] whitespace-nowrap text-[14px] font-bold leading-[18px] no-underline transition-opacity hover:opacity-90 disabled:opacity-50";

function btnClass(variant: BtnVariant, className?: string) {
  const v: Record<BtnVariant, string> = {
    primary: "rounded-[6px] px-[14px] py-2 text-white",
    outline: "rounded-[6px] border border-rule bg-white px-[14px] py-2 text-ink",
    /** Graphite filled, for destructive actions so that red only ever means the brand. */
    ink: "rounded-[6px] px-[14px] py-2 text-white",
    text: "text-accent-text",
  };
  return cn(BTN_BASE, v[variant], className);
}

function btnStyle(variant: BtnVariant) {
  if (variant === "primary") return { backgroundColor: "var(--accent)", backgroundImage: PRIMARY_FILL, boxShadow: PRIMARY_SHADOW };
  if (variant === "ink") return { backgroundColor: "var(--color-ink)" };
  return undefined;
}

export function Btn({
  variant = "primary",
  href,
  className,
  children,
  ...rest
}: { variant?: BtnVariant; href?: string; className?: string; children: ReactNode } & Omit<ComponentProps<"button">, "className">) {
  if (href) {
    return (
      <Link href={href} className={btnClass(variant, className)} style={btnStyle(variant)}>
        {children}
      </Link>
    );
  }
  return (
    <button type="button" className={btnClass(variant, className)} style={btnStyle(variant)} {...rest}>
      {children}
    </button>
  );
}

/** 12px bold label above a value, used in panchang strips and fact rows. */
export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("text-[12px] font-bold leading-4 tracking-[0.06em] text-soft", className)}>{children}</div>;
}

/** Row tag chip: Lal Kitab, Rectify, Matching. */
const TAG_STYLES: Record<string, string> = {
  "Lal Kitab": "bg-wash text-accent-text",
  Rectify: "bg-alert-wash text-alert",
  Matching: "bg-[var(--surface-2)] text-[color:var(--text-primary)]",
};

export function TagChip({ tag }: { tag: string }) {
  return (
    <span className={cn("rounded-[4px] px-2 py-[3px] text-[13px] font-bold leading-4", TAG_STYLES[tag] ?? "bg-chip text-ink")}>{tag}</span>
  );
}
