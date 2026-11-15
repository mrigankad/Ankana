"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { TagChip } from "@/components/ankana/ui";
import { followUpTone } from "@/lib/api/clients";
import type { ClientRow } from "@/lib/api/types";
import { useT } from "@/lib/i18n/provider";

export const AVATAR_TONES = [
  "bg-wash text-accent-text",
  "bg-[var(--surface-2)] text-ink",
  "bg-wash text-accent-text",
  "bg-[var(--surface-2)] text-ink",
  "bg-[var(--surface-2)] text-body",
  "bg-[var(--surface-2)] text-ink",
  "bg-wash text-accent-text",
  "bg-[var(--surface-2)] text-body",
  "bg-[var(--surface-2)] text-ink",
  "bg-wash text-accent-text",
];

export const COLS = "flex shrink-0 items-center";

export function FilterPill({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={
        active
          ? "rounded-full px-[14px] py-2 text-[13px] font-bold leading-4 text-white"
          : "rounded-full border border-rule bg-white px-[14px] py-2 text-[13px] font-bold leading-4 text-body hover:text-ink"
      }
      style={
        active
          ? { backgroundColor: "var(--accent)" }
          : undefined
      }
    >
      {children}
    </button>
  );
}

function FollowUp({ label }: { label: string }) {
  const t = useT();
  const tone = followUpTone(label);
  const cls =
    tone === "today" ? "font-bold text-accent-text" : tone === "soon" ? "font-bold text-alert" : tone === "none" ? "text-soft" : "text-body";
  return <span className={cls}>{label ? t(label) : t("Not scheduled")}</span>;
}

export function ClientTableRow({ c, index, highlight }: { c: ClientRow; index: number; highlight: boolean }) {
  const t = useT();
  return (
    <Link
      href={`/clients/${c.id}`}
      className={`block border-b border-rule px-4 py-3 no-underline outline-none last:border-b-0 hover:bg-wash-soft focus-visible:bg-wash-soft focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring/50 md:flex md:h-[54px] md:items-center md:px-5 md:py-0 ${highlight ? "bg-wash-soft" : ""}`}
    >
      <div className="flex items-center gap-3 md:hidden">
        <div className={`flex size-9 shrink-0 items-center justify-center rounded-full text-[13px] font-bold leading-4 ${AVATAR_TONES[index % AVATAR_TONES.length]}`}>
          {c.initials}
        </div>
        <div className="flex min-w-0 grow flex-col">
          <div className="truncate text-[15px] font-bold leading-[19px] text-ink">{c.name}</div>
          <div className="truncate text-[12px] leading-4 text-soft">
            {[c.lagna || t("No chart yet"), c.dasha].filter(Boolean).join(" · ")}
          </div>
        </div>
        <div className="shrink-0 text-right text-[13px] leading-4">
          <FollowUp label={c.nextFollowUp} />
        </div>
      </div>
      <div className={`${COLS} hidden w-[300px] gap-3 md:flex`}>
        <div className={`flex size-9 shrink-0 items-center justify-center rounded-full text-[13px] font-bold leading-4 ${AVATAR_TONES[index % AVATAR_TONES.length]}`}>
          {c.initials}
        </div>
        <div className="flex min-w-0 flex-col">
          <div className="truncate text-[15px] font-bold leading-[19px] text-ink">{c.name}</div>
          <div className="truncate text-[12px] leading-4 text-soft">{c.birthLine}</div>
        </div>
      </div>
      {c.lagna ? (
        <div className="hidden w-[140px] shrink-0 truncate pr-2 text-[14px] font-bold leading-[18px] text-ink md:block">{c.lagna}</div>
      ) : (
        <div className="hidden w-[140px] shrink-0 truncate pr-2 text-[14px] leading-[18px] text-soft md:block">{t("No chart yet")}</div>
      )}
      <div className="hidden w-[190px] shrink-0 truncate pr-2 text-[14px] leading-[18px] text-body md:block">{c.dasha}</div>
      {c.lastConsult ? (
        <div className="hidden w-[120px] shrink-0 text-[14px] leading-[18px] text-body md:block">{c.lastConsult}</div>
      ) : (
        <div className="hidden w-[120px] shrink-0 text-[14px] leading-[18px] text-soft md:block">{t("No visits yet")}</div>
      )}
      <div className="hidden w-[140px] shrink-0 text-[14px] leading-[18px] md:block">
        <FollowUp label={c.nextFollowUp} />
      </div>
      <div className="hidden grow gap-[6px] md:flex">
        {c.tags.map((t) => (
          <TagChip key={t} tag={t} />
        ))}
      </div>
    </Link>
  );
}
