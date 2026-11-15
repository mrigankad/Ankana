import type { CSSProperties } from "react";

/**
 * Ankana mark, "Niche and bindu": an arched niche holding one point.
 * 64 unit grid, one stroke of 7 with round caps and joins, arch radius 19,
 * legs to y 56, bindu radius 6.5 at (32, 40).
 * The mark takes currentColor unless a colour is passed, so it follows text colour.
 */
export function AnkanaMark({
  size = 20,
  tone = "accent",
  className,
  style,
}: {
  size?: number;
  /** "accent" is sindoor on light, "light" is white for use on accent or ink, "dark" is the dark mode coral, "ink" is graphite. */
  tone?: "accent" | "light" | "dark" | "ink";
  className?: string;
  style?: CSSProperties;
}) {
  const color = tone === "light" ? "#FFFFFF" : tone === "dark" ? "var(--color-accent-light)" : tone === "ink" ? "var(--color-ink)" : "var(--accent)";
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={className} style={style} aria-hidden>
      <path d="M13 56 V31 A19 19 0 0 1 51 31 V56" fill="none" stroke={color} strokeWidth={7} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="32" cy="40" r="6.5" fill={color} />
    </svg>
  );
}

/** Sidebar lockup: the mark in sindoor, then the lowercase wordmark in ink. */
export function AnkanaLockup({ wordSize = 19 }: { wordSize?: number }) {
  return (
    <span className="inline-flex items-center gap-[8px]">
      <AnkanaMark size={Math.round(wordSize * 1.4)} />
      <span className="font-bold text-ink" style={{ fontSize: wordSize, lineHeight: "24px", letterSpacing: "-0.04em" }}>
        ankana
      </span>
    </span>
  );
}
