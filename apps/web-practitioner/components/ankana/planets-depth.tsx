"use client";

import { depthApi } from "@/lib/api/depth";
import { planetViews, type Fact, type PlanetView, type Tone } from "@/lib/api/depth-views";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

import { DepthBody, DepthFailed, DepthLoading, useDepthData } from "./depth-shell";
import { ProofValue } from "./proof-drawer";

const TONE: Record<Tone, string> = {
  good: "bg-ok-wash text-ok",
  bad: "bg-alert-wash text-alert",
  plain: "bg-sidebar-wash text-ink",
};

function Chip({ fact }: { fact: Fact }) {
  return (
    <span className={cn("inline-flex items-center rounded-[4px] px-[7px] py-[2px] text-[12px] font-bold leading-4", TONE[fact.tone])}>
      <ProofValue proof={fact.proof}>{fact.text}</ProofValue>
    </span>
  );
}

function Cell({ fact, strong }: { fact: Fact; strong?: boolean }) {
  return (
    <ProofValue proof={fact.proof} className={cn("text-[14px] leading-[18px]", strong ? "font-bold text-ink" : "text-body")}>
      {fact.text}
    </ProofValue>
  );
}

function Flags({ v, empty }: { v: PlanetView; empty?: string }) {
  const f = v.facts;
  const items = [f.retrograde.tone === "bad" ? f.retrograde : null, f.combust.tone === "bad" ? f.combust : null].filter(Boolean) as Fact[];
  if (!items.length && !empty) return null;
  return (
    <div className="flex flex-wrap gap-[6px]">
      {items.length ? items.map((it) => <Chip key={it.id} fact={it} />) : <span className="text-[13px] leading-4 text-soft">{empty}</span>}
    </div>
  );
}

function Row({ v }: { v: PlanetView }) {
  const f = v.facts;
  return (
    <tr id={`planet-${v.planet}`} className="border-b border-rule align-top last:border-0">
      <th scope="row" className="min-w-[150px] py-3 pr-3 text-left align-top">
        <div className="flex flex-col gap-[3px]">
          <div className="text-[15px] font-bold leading-5 text-ink">{v.name}</div>
          <div className="whitespace-nowrap text-[12px] font-normal leading-4 text-soft">
            {v.position} {v.degree} · H{v.house}
          </div>
          <Flags v={v} />
        </div>
      </th>
      <td className="px-3 py-3">
        <div className="flex flex-col gap-[2px]">
          <Cell fact={f.nakshatra} strong />
          <div className="flex flex-wrap gap-x-2 text-[13px] leading-4 text-body">
            <Cell fact={f.pada} />
            <Cell fact={f.nakshatraLord} />
          </div>
        </div>
      </td>
      <td className="px-3 py-3"><Cell fact={f.signLord} /></td>
      <td className="px-3 py-3"><Chip fact={f.dignity} /></td>
      <td className="px-3 py-3"><Cell fact={f.avastha} /></td>
      <td className="px-3 py-3"><Cell fact={f.karaka} /></td>
      <td className="py-3 pl-3"><Cell fact={f.lordships} /></td>
    </tr>
  );
}

function Card({ v, labels }: { v: PlanetView; labels: Record<string, string> }) {
  const f = v.facts;
  const rows: Array<[string, Fact]> = [
    [labels.nakshatra!, f.nakshatra], [labels.pada!, f.pada], [labels.nakshatraLord!, f.nakshatraLord], [labels.signLord!, f.signLord],
    [labels.dignity!, f.dignity], [labels.avastha!, f.avastha], [labels.karaka!, f.karaka], [labels.lordships!, f.lordships],
  ];
  return (
    <article id={`planet-${v.planet}-card`} className="flex flex-col gap-3 rounded-[10px] border border-rule p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="m-0 text-[16px] font-bold leading-5 text-ink">{v.name}</h3>
        <span className="text-[13px] leading-4 text-soft">{v.position} {v.degree} · H{v.house}</span>
      </div>
      <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
        {rows.map(([label, fact]) => (
          <div key={fact.id} className="contents">
            <dt className="text-[13px] leading-[18px] text-soft">{label}</dt>
            <dd className="m-0 text-right"><Cell fact={fact} strong /></dd>
          </div>
        ))}
        <dt className="text-[13px] leading-[18px] text-soft">{labels.status}</dt>
        <dd className="m-0 flex justify-end"><Flags v={v} empty={labels.none!} /></dd>
      </dl>
    </article>
  );
}

/** Planets tab: one row per graha with the facts the engine already computed, each opening its proof. */
export function PlanetsDepthView({ chartId, live }: { chartId: string; live: boolean }) {
  const t = useT();
  const { data, failed, retry } = useDepthData(() => depthApi.planets(chartId, live), `${chartId}:${live}`);

  if (failed) return <DepthBody><DepthFailed onRetry={retry} /></DepthBody>;
  if (!data) return <DepthBody><DepthLoading rows={5} /></DepthBody>;

  const views = planetViews(data, t);
  const head = ["Planet", "Nakshatra", "Sign lord", "Dignity", "Avastha", "Chara karaka", "Rules houses"];
  const labels = {
    nakshatra: t("Nakshatra"), pada: t("Pada"), nakshatraLord: t("Nakshatra lord"), signLord: t("Sign lord"), dignity: t("Dignity"),
    avastha: t("Avastha"), karaka: t("Chara karaka"), lordships: t("Rules houses"), status: t("State"), none: t("None"),
  };

  return (
    <DepthBody>
      <div id="planets" className="flex flex-col gap-1">
        <h2 className="m-0 text-[20px] font-bold leading-6 tracking-[-0.01em] text-ink">{t("Planet positions")}</h2>
        <p className="m-0 text-[14px] leading-5 text-body">
          {t("Lagna {sign} {nakshatra} pada {pada}. Select any underlined value to see how it was worked out.", {
            sign: t(data.lagna.sign), nakshatra: t(data.lagna.nakshatra), pada: data.lagna.pada,
          })}
        </p>
      </div>

      <div className="hidden overflow-x-auto rounded-[10px] border border-rule px-4 md:block">
        <table className="w-full min-w-[720px] border-collapse">
          <thead>
            <tr className="border-b border-rule">
              {head.map((h, i) => (
                <th key={h} scope="col" className={cn("py-[10px] text-left text-[12px] font-bold leading-4 text-soft", i === 0 ? "pr-3" : i === head.length - 1 ? "pl-3" : "px-3")}>
                  {t(h)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {views.map((v) => (
              <Row key={v.planet} v={v} />
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid gap-3 md:hidden">
        {views.map((v) => (
          <Card key={v.planet} v={v} labels={labels} />
        ))}
      </div>

      <p className="m-0 text-[12px] leading-4 text-soft">
        {t("Chara karakas use the seven planet scheme, so Rahu and Ketu have none. Baladi avastha is not assigned to the nodes.")}
      </p>
    </DepthBody>
  );
}
