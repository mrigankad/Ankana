"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { AnkanaLockup } from "@/components/ankana/logo";
import { Glyph, type GlyphName } from "@/components/ankana/icons";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { api } from "@/lib/api/client";
import { getMeta } from "@/lib/api/v1";
import type { WorkspaceMeta } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { CommandPalette } from "./command-palette";
import { isPublicPath, useAuth } from "./auth/auth-provider";
import { activeRole } from "@/lib/auth/roles";
import { UserMenu } from "./auth/user-menu";
import { LanguageSwitcher } from "./language-switcher";
import { useT } from "@/lib/i18n/provider";

const DEFAULT_SOURCE_URL = process.env.NEXT_PUBLIC_SOURCE_URL ?? "https://github.com/mrigankad/Ankana";
const DEFAULT_SHA = (process.env.NEXT_PUBLIC_GIT_SHA ?? "").slice(0, 7);

/** AGPL-3.0 section 13: every network user can get the source. Prefers GET /v1/meta when reachable. */
export function SourceLink({ className }: { className?: string }) {
  const t = useT();
  const [meta, setMeta] = useState({ url: DEFAULT_SOURCE_URL, sha: DEFAULT_SHA });
  useEffect(() => {
    getMeta()
      .then((m) =>
        setMeta({ url: m.source_url || DEFAULT_SOURCE_URL, sha: (m.git_sha || DEFAULT_SHA).slice(0, 7) }),
      )
      .catch(() => undefined);
  }, []);
  return (
    <a
      href={meta.url}
      target="_blank"
      rel="noreferrer"
      className={cn("text-[12px] leading-4 text-soft no-underline hover:text-body", className)}
    >
      {t("Source code")} · AGPL-3.0{meta.sha ? ` · ${meta.sha}` : ""}
    </a>
  );
}

/** Billing exists only on the hosted service; hidden when GET /v1/meta reports billing off. */
function BillingNavLink({ active, onNavigate }: { active: boolean; onNavigate?: () => void }) {
  const [on, setOn] = useState(false);
  useEffect(() => {
    getMeta()
      .then((m) => setOn(Boolean(m.billing)))
      .catch(() => undefined);
  }, []);
  if (!on) return null;
  return <NavItem href="/settings/billing" icon="wallet" label="Plan and billing" active={active} onNavigate={onNavigate} />;
}

/** Settings links. Team and Practice are owner-only; Sessions and Branding are for any staff. */
function SettingsNav({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  const t = useT();
  const role = activeRole(useAuth().session);
  const items: [string, GlyphName, string, boolean][] = [
    ["/settings/team", "people", "Team", role === null || role === "owner"],
    ["/settings/sessions", "device", "Sessions", true],
    ["/settings/practice", "building", "Practice", role === null || role === "owner"],
    ["/settings/branding", "brush", "Branding", true],
  ];
  return (
    <div className="flex flex-col gap-[2px]">
      <SectionLabel>{t("SETTINGS")}</SectionLabel>
      {items
        .filter(([, , , show]) => show)
        .map(([href, icon, label]) => (
          <NavItem key={href} href={href} icon={icon} label={t(label)} active={pathname.startsWith(href)} onNavigate={onNavigate} />
        ))}
    </div>
  );
}

interface ShellContextValue {
  workspace: WorkspaceMeta | null;
  openNav: () => void;
  openSearch: () => void;
}
const ShellContext = createContext<ShellContextValue>({
  workspace: null,
  openNav: () => undefined,
  openSearch: () => undefined,
});
export const useShell = () => useContext(ShellContext);

function NavItem({
  href,
  icon,
  label,
  active,
  count,
  badge,
  iconColor,
  onNavigate,
}: {
  href: string;
  icon: GlyphName;
  label: string;
  active?: boolean;
  count?: number | string;
  badge?: number | string;
  iconColor?: string;
  onNavigate?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-[10px] rounded-[6px] border px-[10px] py-2 text-[15px] leading-[18px] text-ink no-underline",
        active ? "border-rule bg-white font-bold" : "border-transparent hover:bg-white/70",
      )}
    >
      <Glyph name={icon} color={iconColor ?? (active ? "var(--text-primary)" : "var(--text-body)")} />
      <span className="grow">{label}</span>
      {badge !== undefined ? (
        <span className="rounded-full bg-wash px-[7px] py-px text-[12px] font-bold leading-4 text-accent-text">{badge}</span>
      ) : null}
      {count !== undefined ? <span className="text-[12px] leading-4 text-soft">{count}</span> : null}
    </Link>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="px-[10px] pb-[6px] text-[12px] font-bold leading-4 tracking-[0.06em] text-soft">{children}</div>
  );
}

function Sidebar({
  pathname,
  workspace,
  onNavigate,
  onOpenSearch,
}: {
  pathname: string;
  workspace: WorkspaceMeta | null;
  onNavigate?: () => void;
  onOpenSearch: () => void;
}) {
  const w = workspace;
  const authOn = useAuth().enabled;
  const t = useT();
  const unlimited = w ? w.reportsQuota === null : false;
  const quotaPct = w && w.reportsQuota ? Math.min(100, Math.round((w.reportsUsed / w.reportsQuota) * 100)) : 0;
  const quotaText = !w ? "" : unlimited ? t("{n} · Unlimited", { n: w.reportsUsed }) : w.reportsQuota === 0 ? t("Not in plan") : `${w.reportsUsed} / ${w.reportsQuota}`;
  return (
    <div className="flex h-full flex-col gap-3 px-3 pb-3 pt-4">
      <Link href="/" onClick={onNavigate} className="px-[6px] py-[2px] no-underline" aria-label={t("Ankana home")}>
        <AnkanaLockup />
      </Link>

      <button
        type="button"
        onClick={() => {
          onNavigate?.();
          onOpenSearch();
        }}
        className="flex items-center gap-2 rounded-[6px] border border-rule bg-white px-3 py-[9px] text-left"
      >
        <Glyph name="search" size={14} color="var(--text-soft)" />
        <span className="grow text-[14px] leading-[18px] text-soft">{t("Search clients and charts")}</span>
      </button>

      <div className="nk-scroll nk-scroll-thin -mx-3 flex min-h-0 grow flex-col gap-4 px-3 py-1">
      <nav className="flex flex-col gap-[2px]" aria-label={t("Primary")}>
        <NavItem href="/" icon="home" label={t("Today")} active={pathname === "/"} onNavigate={onNavigate} />
        <NavItem
          href="/needs-you"
          icon="flag"
          label={t("Needs you")}
          active={pathname.startsWith("/needs-you")}
          badge={w?.needsYouCount}
          onNavigate={onNavigate}
        />
        <NavItem
          href="/clients"
          icon="people"
          label={t("Clients")}
          active={pathname.startsWith("/clients") || pathname.startsWith("/charts")}
          count={w?.clientCount}
          onNavigate={onNavigate}
        />
        <NavItem
          href="/panchang"
          icon="calendar"
          label={t("Panchang & muhurta")}
          active={pathname.startsWith("/panchang")}
          onNavigate={onNavigate}
        />
      </nav>

      <div className="flex flex-col gap-[2px]">
        <SectionLabel>{t("TODAY'S CONSULTS")}</SectionLabel>
        {(w?.consults ?? []).map((c) => (
          <Link
            key={c.clientName}
            href="/"
            onClick={onNavigate}
            className="flex items-center gap-[10px] px-[10px] py-[7px] text-[14px] leading-[18px] text-black no-underline"
          >
            <span
              className="size-[7px] shrink-0 rounded-full"
              style={{ backgroundColor: c.active ? "var(--accent)" : "var(--rule-strong)" }}
            />
            <span className="grow">{c.clientName}</span>
            <span className="text-[12px] leading-4 text-soft">{c.time}</span>
          </Link>
        ))}
      </div>

      <div className="flex flex-col gap-[2px]">
        <SectionLabel>{t("LIBRARY")}</SectionLabel>
        {(
          [
            ["/library/lal-kitab", "book", "Lal Kitab", "var(--text-primary)"],
            ["/library/remedies", "heart", "Remedies", undefined],
            ["/library/report-templates", "doc", "Report templates", undefined],
            ["/library/engine", "sliders", "Engine & models", undefined],
          ] as const
        ).map(([href, icon, label, color]) => (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            className="flex items-center gap-[10px] px-[10px] py-[7px] text-[15px] leading-[18px] text-black no-underline"
          >
            <Glyph name={icon} color={color ?? "var(--text-body)"} />
            {t(label)}
          </Link>
        ))}
      </div>

      <SettingsNav pathname={pathname} onNavigate={onNavigate} />

      <BillingNavLink active={pathname.startsWith("/settings/billing")} onNavigate={onNavigate} />

      </div>

      <div className="flex shrink-0 flex-col gap-3 rounded-[8px] border border-rule bg-white p-3">
        <div className="flex flex-col gap-[6px]">
          <div className="flex justify-between text-[12px] leading-4">
            <span className="text-body">{t("Reports this month")}</span>
            <span className="font-bold text-black">{quotaText}</span>
          </div>
          {unlimited ? null : (
            <div className="h-1 rounded-[2px] bg-rule">
              <div className="h-1 rounded-[2px] bg-sindoor" style={{ width: `${quotaPct}%` }} />
            </div>
          )}
        </div>
        <div className="-mx-3 border-t border-rule" />
      {authOn ? (
        <UserMenu />
      ) : (
        <div className="flex items-center gap-[10px]">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-ink text-[12px] font-bold leading-4 text-white">
            {w?.practitioner.initials ?? ""}
          </span>
          <div className="flex min-w-0 grow flex-col">
            <span className="truncate text-[14px] font-bold leading-[18px] text-black">{w?.practitioner.name ?? ""}</span>
            <span className="truncate text-[12px] leading-4 text-soft">{w?.practitioner.practice ?? ""}</span>
          </div>
          <LanguageSwitcher compact />
        </div>
      )}
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const t = useT();
  const pathname = usePathname() ?? "/";
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [workspace, setWorkspace] = useState<WorkspaceMeta | null>(null);
  const { session } = useAuth();
  const role = activeRole(session);
  // Print pages, public pages and the client portal bring their own chrome (no practitioner sidebar).
  const isPrintRoute = pathname.endsWith("/print") || isPublicPath(pathname) || role === "client" || pathname.startsWith("/portal");

  useEffect(() => {
    if (role === "client") return; // portal users never load the practitioner workspace
    let cancelled = false;
    api.getWorkspace().then((w) => !cancelled && setWorkspace(w)).catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [role]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  if (isPrintRoute) return <>{children}</>;

  return (
    <ShellContext.Provider
      value={{ workspace, openNav: () => setMobileOpen(true), openSearch: () => setPaletteOpen(true) }}
    >
      <div className="flex h-svh overflow-hidden bg-white">
        <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />

        <aside
          className="hidden h-svh w-[240px] shrink-0 border-r border-rule bg-sidebar-wash lg:block"
          aria-label={t("Sidebar")}
        >
          <Sidebar pathname={pathname} workspace={workspace} onOpenSearch={() => setPaletteOpen(true)} />
        </aside>

        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetContent side="left" className="w-[min(100vw-2rem,280px)] max-w-[280px] overflow-y-auto bg-sidebar-wash p-0">
            <SheetHeader className="sr-only">
              <SheetTitle>{t("Navigation")}</SheetTitle>
            </SheetHeader>
            <Sidebar
              pathname={pathname}
              workspace={workspace}
              onNavigate={() => setMobileOpen(false)}
              onOpenSearch={() => setPaletteOpen(true)}
            />
          </SheetContent>
        </Sheet>

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <div className="nk-scroll nk-scroll-flush flex min-h-0 flex-1 flex-col">
            <div className="flex flex-1 shrink-0 flex-col">{children}</div>
            <footer className="flex shrink-0 flex-wrap items-center justify-between gap-x-6 gap-y-1 border-t border-rule px-6 py-3 lg:px-10">
              <span className="text-[12px] leading-4 text-soft">
                {t("Ankana · deterministic Vedic computation, explainable readings. Guidance is advisory.")}
              </span>
              <SourceLink />
            </footer>
          </div>
        </div>
      </div>
    </ShellContext.Provider>
  );
}
