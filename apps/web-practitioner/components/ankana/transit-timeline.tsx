"use client";

import { useMemo, useState } from "react";

import { FilterPill } from "@/components/ankana/client-table";
import { Chip, Panel } from "@/components/ankana/ui";
import type { SadeSatiPhase, TransitEventV1, TransitTimelineV1 } from "@/lib/api/live";
import { useLanguage, useT } from "@/lib/i18n/provider";
import { tName } from "@/lib/i18n/translate";

type Group = "all" | "ingress" | "aspect" | "station" | "sade_sati";

const GROUP_OF: Record<TransitEventV1["kind"], Exclude<Group, "all">> = {
  ingress: "ingress",
  aspect: "aspect",
  conjunction: "aspect",
  "retrograde-station": "station",
  "direct-station": "station",
  sade_sati: "sade_sati",
};

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

function useFormat() {
  const { lang } = useLanguage();
  const locale = lang === "hi" ? "hi-IN" : "en-GB";
  return {
    day: (iso: string) => new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" }).format(new Date(iso)),
    full: (iso: string) => new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", year: "numeric" }).format(new Date(iso)),
    month: (iso: string) => new Intl.DateTimeFormat(locale, { month: "long", year: "numeric" }).format(new Date(iso)),
  };
}

function useEventText() {
  const t = useT();
  const name = (s: string) => tName(t, cap(s));
  return (e: TransitEventV1): string => {
    const planet = name(e.planet);
    const sign = name(e.sign);
    const target = e.target === "moon" ? t("natal Moon") : t("lagna");
    switch (e.kind) {
      case "ingress":
        return t("{planet} enters {sign}", { planet, sign });
      case "retrograde-station":
        return t("{planet} turns retrograde in {sign}", { planet, sign });
      case "direct-station":
        return t("{planet} turns direct in {sign}", { planet, sign });
      case "aspect":
        return t("{planet} in {sign} aspects the {target}", { planet, sign, target });
      case "conjunction":
        return t("{planet} joins the {target} in {sign}", { planet, sign, target });
      default:
        return e.phase ? t("Sade sati enters its {phase} phase", { phase: t(e.phase) }) : t("Sade sati ends");
    }
  };
}

function SadeSati({ data }: { data: TransitTimelineV1["sade_sati"] }) {
  const t = useT();
  const f = useFormat();
  const label = (p: SadeSatiPhase) => t(p);
  return (
    <Panel className="flex flex-col gap-2 px-5 py-4">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="m-0 text-[17px] font-bold leading-[22px] text-ink">{t("Sade sati")}</h3>
        <Chip tone={data.active_now ? "accent" : "muted"}>
          {data.active_now && data.phase_now ? t("Running, {phase} phase", { phase: label(data.phase_now) }) : t("Not running")}
        </Chip>
      </div>
      {data.phases.length ? (
        <ul className="m-0 flex list-none flex-col gap-1 p-0">
          {data.phases.map((p, i) => (
            <li key={`${p.phase}-${i}`} className="flex flex-wrap gap-x-2 text-[14px] leading-5 text-body">
              <span className="font-bold text-ink">{t("{phase} phase", { phase: label(p.phase) })}</span>
              <span>
                {p.starts_at ? t("from {date}", { date: f.full(p.starts_at) }) : t("running now")}
                {p.ends_at ? `, ${t("until {date}", { date: f.full(p.ends_at) })}` : `, ${t("continues past this window")}`}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="m-0 text-[14px] leading-5 text-body">{t("Saturn does not move through the 12th, 1st or 2nd sign from the natal Moon in this window.")}</p>
      )}
    </Panel>
  );
}

/** Upcoming transits against the natal chart: ingresses with houses, drishti on the Moon and lagna, stations, sade sati. */
export function TransitTimeline({ data }: { data: TransitTimelineV1 }) {
  const t = useT();
  const f = useFormat();
  const text = useEventText();
  const [group, setGroup] = useState<Group>("all");

  const counts = useMemo(() => {
    const c: Record<Group, number> = { all: data.events.length, ingress: 0, aspect: 0, station: 0, sade_sati: 0 };
    for (const e of data.events) c[GROUP_OF[e.kind]] += 1;
    return c;
  }, [data.events]);

  const months = useMemo(() => {
    const out: Array<{ key: string; label: string; events: TransitEventV1[] }> = [];
    for (const e of data.events) {
      if (group !== "all" && GROUP_OF[e.kind] !== group) continue;
      const key = e.date.slice(0, 7);
      let m = out.find((x) => x.key === key);
      if (!m) {
        m = { key, label: f.month(e.date), events: [] };
        out.push(m);
      }
      m.events.push(e);
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.events, group]);

  const pills: Array<[Group, string]> = [
    ["all", t("All")],
    ["ingress", t("Ingresses")],
    ["aspect", t("Aspects")],
    ["station", t("Stations")],
    ["sade_sati", t("Sade sati")],
  ];

  return (
    <section aria-label={t("Upcoming events")} className="flex flex-col gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="m-0 text-[20px] font-bold leading-6 text-ink">{t("Upcoming events")}</h2>
        <span className="text-[13px] leading-4 text-soft">
          {t("Next {n} months from {date}", { n: data.months, date: f.full(data.start) })}
        </span>
      </div>
      <p className="m-0 max-w-[720px] text-[14px] leading-5 text-body">
        {t("Houses count from the {lagna} lagna and from the {moon} Moon. Aspects are graha drishti onto the natal Moon and lagna, checked when a planet changes sign.", {
          lagna: tName(t, cap(data.natal.lagna_sign)),
          moon: tName(t, cap(data.natal.moon_sign)),
        })}
      </p>
      <SadeSati data={data.sade_sati} />
      <div className="flex flex-wrap gap-[10px]">
        {pills.map(([id, label]) => (
          <FilterPill key={id} active={group === id} onClick={() => setGroup(id)}>
            {label} {counts[id]}
          </FilterPill>
        ))}
      </div>
      {months.length === 0 ? (
        <Panel className="px-5 py-5 text-[14px] leading-5 text-body">{t("No events of this kind in the window.")}</Panel>
      ) : (
        months.map((m) => (
          <Panel key={m.key} className="flex flex-col">
            <div className="border-b border-rule bg-sidebar-wash px-5 py-[10px] text-[13px] font-bold leading-4 text-soft">{m.label}</div>
            {m.events.map((e, i) => (
              <div
                key={`${e.date}-${e.planet}-${e.kind}-${e.target ?? ""}-${i}`}
                className={`flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-[11px] ${i === m.events.length - 1 ? "" : "border-b border-rule"}`}
              >
                <span className="w-[52px] shrink-0 text-[13px] leading-4 text-soft">{f.day(e.date)}</span>
                <span className="min-w-[220px] grow basis-0 text-[14px] font-bold leading-[18px] text-ink">{text(e)}</span>
                <span className="flex flex-wrap gap-2">
                  {e.kind === "aspect" && e.aspect ? <Chip tone="accent">{t("Drishti {n}", { n: e.aspect })}</Chip> : null}
                  {e.kind !== "sade_sati" ? (
                    <>
                      <Chip tone="ink">{t("House {n} from lagna", { n: e.house_from_lagna })}</Chip>
                      <Chip tone="muted">{t("House {n} from Moon", { n: e.house_from_moon })}</Chip>
                    </>
                  ) : null}
                </span>
              </div>
            ))}
          </Panel>
        ))
      )}
    </section>
  );
}
