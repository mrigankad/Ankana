"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Glyph } from "@/components/ankana/icons";
import { Btn } from "@/components/ankana/ui";
import { useShell } from "@/components/app-shell";
import { useT } from "@/lib/i18n/provider";

export interface Crumb {
  label: string;
  href?: string;
}

/** 48px top bar from Paper: breadcrumb on the left, actions on the right. */
export function Topbar({ crumbs, right }: { crumbs: Crumb[]; right?: ReactNode }) {
  const { workspace, openNav } = useShell();
  const t = useT();
  return (
    <div className="flex h-12 shrink-0 items-center justify-between border-b border-rule px-4 lg:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <button type="button" onClick={openNav} className="lg:hidden" aria-label={t("Open navigation")}>
          <Glyph name="menu" size={18} color="var(--text-primary)" />
        </button>
        <nav aria-label={t("Breadcrumb")} className="flex min-w-0 items-center gap-2 text-[14px] leading-[18px] text-body">
          {crumbs.map((c, i) => {
            const last = i === crumbs.length - 1;
            return (
              <span key={`${c.label}-${i}`} className="flex min-w-0 items-center gap-2">
                {c.href && !last ? (
                  <Link href={c.href} className="text-body no-underline hover:text-ink">
                    {t(c.label)}
                  </Link>
                ) : (
                  <span className={last && crumbs.length > 1 ? "truncate text-ink" : "truncate"}>{t(c.label)}</span>
                )}
                {!last ? <span className="text-soft">/</span> : null}
              </span>
            );
          })}
        </nav>
      </div>
      <div className="flex items-center gap-3">
        {right ?? (
          <>
            <span className="hidden items-center gap-[6px] rounded-full bg-sidebar-wash px-[10px] py-1 sm:flex">
              <span className="size-[6px] rounded-full bg-ok" />
              <span className="text-[13px] leading-4 text-body">{workspace?.engine ?? "Engine v2 · Lahiri"}</span>
            </span>
            <Glyph name="bell" color="var(--text-body)" stroke={1.5} />
            <Btn href="/clients/new">{t("+ New chart")}</Btn>
          </>
        )}
      </div>
    </div>
  );
}
