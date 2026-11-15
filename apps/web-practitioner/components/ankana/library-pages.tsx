"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { PageHeader } from "@/components/ankana/page-header";
import { Topbar } from "@/components/ankana/topbar";
import { Panel } from "@/components/ankana/ui";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "@/components/ui/data";
import { ANANYA_CHART_ID } from "@/lib/api/fixtures";
import { useT } from "@/lib/i18n/provider";

function Shell({ crumb, title, subtitle, children }: { crumb: string; title: string; subtitle: string; children: ReactNode }) {
  const t = useT();
  return (
    <>
      <Topbar crumbs={[{ label: "Library" }, { label: crumb }]} />
      <main className="flex flex-1 flex-col gap-7 px-5 py-8 lg:px-10 lg:py-9">
        <PageHeader title={t(title)} subtitle={t(subtitle)} />
        {children}
      </main>
    </>
  );
}

function Card({ title, text, href, cta }: { title: string; text: string; href?: string; cta?: string }) {
  const t = useT();
  return (
    <Panel className="flex flex-col gap-2 p-5">
      <h3 className="m-0 text-[17px] font-bold leading-6 text-ink">{t(title)}</h3>
      <p className="m-0 text-[14px] leading-5 text-body">{t(text)}</p>
      {href && cta ? (
        <Link href={href} className="mt-1 text-[14px] font-bold leading-[18px] text-accent-text no-underline">
          {t(cta)}
        </Link>
      ) : null}
    </Panel>
  );
}

export function LalKitabLibrary() {
  const lk = `/charts/${ANANYA_CHART_ID}?tab=lal-kitab`;
  return (
    <Shell crumb="Lal Kitab" title="Lal Kitab" subtitle="The rules the engine applies when it reads a chart the Lal Kitab way.">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Card title="Debts (rin)" text="Ancestral, paternal and other debts are found from planet and house pairings, each with the book's remedy." href={lk} cta="See it on a chart" />
        <Card title="Sleeping planets" text="A planet can be dormant by rule. The engine names the planet that awakens it and the age it may wake by itself." href={lk} cta="See it on a chart" />
        <Card title="Artificial planets" text="Pairings of planets create a masnui planet. The engine checks them and says plainly when none apply." href={lk} cta="See it on a chart" />
        <Card title="Varshphal" text="The yearly chart for each year of life, read with the same rules." href={lk} cta="See it on a chart" />
        <Card title="Source and page cites" text="Every upay carries the printed volume and page it comes from, so you can check it against the book." />
        <Card title="Needs review" text="Rules that need a practitioner's judgement are marked, and nothing reaches a client until you approve it." />
      </div>
    </Shell>
  );
}

const REMEDY_KINDS = [
  { kind: "Lal Kitab upay", how: "One at a time, 43 days each, a few days apart", example: "Offer a rupee at a temple, feed a peepal tree" },
  { kind: "Mantra", how: "A set count each day for a fixed cycle", example: "Beej mantra of the planet" },
  { kind: "Daan", how: "A planet's article given on its day", example: "Donate to a temple" },
  { kind: "Fasting", how: "One day a week", example: "Saturday for Saturn" },
  { kind: "Lifestyle", how: "A daily habit tied to the planet", example: "Early rising for the Sun" },
  { kind: "Gemstone and rudraksha", how: "Only for a weak, unafflicted planet that rules a trikona", example: "Worn after your review" },
];

export function RemediesLibrary() {
  const t = useT();
  return (
    <Shell crumb="Remedies" title="Remedies" subtitle="The kinds of remedy Ankana can suggest, and how each one is scheduled.">
      <Table>
        <TableHead>
          <TableRow>
            <TableHeaderCell>{t("Kind")}</TableHeaderCell>
            <TableHeaderCell>{t("How it runs")}</TableHeaderCell>
            <TableHeaderCell>{t("Example")}</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {REMEDY_KINDS.map((r) => (
            <TableRow key={r.kind}>
              <TableCell className="font-bold">{t(r.kind)}</TableCell>
              <TableCell className="text-body">{t(r.how)}</TableCell>
              <TableCell className="text-body">{t(r.example)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="m-0 max-w-[640px] text-[13px] leading-5 text-body">
        {t("Remedies are traditional practices. They are advisory, never a medical or financial prescription.")}
      </p>
    </Shell>
  );
}

const SECTIONS = [
  ["Cover and summary", true],
  ["Rashi chart", true],
  ["Houses", true],
  ["Planet positions", true],
  ["Dasha timeline", true],
  ["Life reading", false],
  ["Yogas", true],
  ["Divisional charts", false],
  ["Panchang at birth", true],
  ["Lal Kitab and debts", true],
  ["Remedy plan", true],
] as const;

export function ReportTemplatesLibrary() {
  const t = useT();
  return (
    <Shell crumb="Report templates" title="Report templates" subtitle="Choose which sections a client report includes. Branding comes from Settings.">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
        <Panel className="flex flex-col">
          <div className="flex items-baseline justify-between gap-3 border-b border-rule px-5 py-4">
            <h2 className="m-0 text-[17px] font-bold leading-6 text-ink">{t("Standard")}</h2>
            <span className="text-[13px] leading-4 text-soft">{t("9 of 11 sections")}</span>
          </div>
          {SECTIONS.map(([name, on], i) => (
            <div key={name} className={`flex items-center gap-3 px-5 py-3 ${i < SECTIONS.length - 1 ? "border-b border-rule" : ""}`}>
              <span className={`size-[8px] shrink-0 rounded-full ${on ? "bg-sindoor" : "bg-rule"}`} aria-hidden />
              <span className="grow text-[15px] leading-5 text-ink">{t(name)}</span>
              <span className="text-[13px] leading-4 text-soft">{on ? t("Included") : t("Off by default")}</span>
            </div>
          ))}
        </Panel>
        <Card title="Branding" text="Your name, logo, colours and footer appear on every report you export." href="/settings/branding" cta="Edit branding" />
      </div>
    </Shell>
  );
}
