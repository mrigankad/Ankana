import { fmtDeg } from "./chart-views";
import type { ClientRowV1, TodayV1, UsageV1 } from "./live";
import type { ClientDetailReport, ClientRow, ConsultCard, NeedsYouItem, SkyItem, TodayView, WorkspaceMeta } from "./types";
import type { ClientReportV1 } from "./live";

/**
 * Pure mappers from the live /v1 payloads to the view models the screens already render.
 * Nothing here talks to the network, so it is all unit tested.
 */

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const SIGN_INDEX: Record<string, number> = {
  Aries: 0, Taurus: 1, Gemini: 2, Cancer: 3, Leo: 4, Virgo: 5, Libra: 6, Scorpio: 7, Sagittarius: 8, Capricorn: 9, Aquarius: 10, Pisces: 11,
};
const VARA_DEVA: Record<string, string> = {
  Ravivara: "रविवार", Somavara: "सोमवार", Mangalavara: "मंगलवार", Budhavara: "बुधवार",
  Guruvara: "गुरुवार", Shukravara: "शुक्रवार", Shanivara: "शनिवार",
};

export const cap = (s: string) => (s ? s[0]!.toUpperCase() + s.slice(1) : s);

function initialsOf(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("");
}

/** Wall-clock parts of an instant in an IANA zone. Falls back to UTC for an unknown zone. */
export function zoneParts(iso: string | Date, timeZone: string) {
  const date = typeof iso === "string" ? new Date(iso) : iso;
  let fmt: Intl.DateTimeFormat;
  try {
    fmt = new Intl.DateTimeFormat("en-GB", { timeZone, hourCycle: "h23", year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", weekday: "short" });
  } catch {
    fmt = new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", hourCycle: "h23", year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", weekday: "short" });
  }
  const p = Object.fromEntries(fmt.formatToParts(date).map((x) => [x.type, x.value]));
  return {
    year: Number(p.year),
    month: Number(p.month),
    day: Number(p.day),
    hour: String(p.hour).padStart(2, "0"),
    minute: String(p.minute).padStart(2, "0"),
    weekday: String(p.weekday),
  };
}

/** "21:04" in the zone. */
export function clock(iso: string, timeZone: string) {
  const p = zoneParts(iso, timeZone);
  return `${p.hour}:${p.minute}`;
}

/** "16 Nov" in the zone. */
export function dayMonth(iso: string, timeZone: string) {
  const p = zoneParts(iso, timeZone);
  return `${p.day} ${MONTHS[p.month - 1]}`;
}

/** "Tue 18 Nov" in the zone, or "Today" when it is the zone's current day. */
export function followUpLabel(dateIso: string, todayIso: string): string {
  if (dateIso === todayIso) return "Today";
  const [y, m, d] = dateIso.split("-").map(Number) as [number, number, number];
  const wd = WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
  return `${wd} ${d} ${MONTHS[m - 1]}`;
}

function localDateIso(now: Date, timeZone: string) {
  const p = zoneParts(now, timeZone);
  return `${p.year}-${String(p.month).padStart(2, "0")}-${String(p.day).padStart(2, "0")}`;
}

/* ------------------------------------------------------------- client rows */
export function clientRowFromV1(c: ClientRowV1, opts: { now?: Date; timeZone?: string } = {}): ClientRow {
  const now = opts.now ?? new Date();
  const tz = opts.timeZone ?? "Asia/Kolkata";
  const signIndex = c.lagna_sign ? (SIGN_INDEX[c.lagna_sign] ?? 0) : 0;
  const dasha = c.current_dasha;
  const booked = c.next_consultation_at ? followUpLabel(localDateIso(new Date(c.next_consultation_at), tz), localDateIso(now, tz)) : "";
  return {
    id: c.id,
    chartId: c.latest_chart_id,
    initials: initialsOf(c.display_name),
    name: c.display_name,
    birthLine: c.contact_email || c.contact_phone || "No contact details",
    lagna: c.lagna_sign && c.lagna_degree !== null ? `${c.lagna_sign} ${fmtDeg(c.lagna_degree, signIndex, false)}` : "",
    dasha: dasha ? `${cap(dasha.maha)}${dasha.antar ? ` / ${cap(dasha.antar)}` : ""}` : "",
    lastConsult: c.last_consultation_at ? dayMonth(c.last_consultation_at, tz) : "",
    nextFollowUp: c.next_follow_up ? followUpLabel(c.next_follow_up, localDateIso(now, tz)) : booked,
    tags: c.tags,
  };
}

/* ----------------------------------------------------------------- reports */
const REPORT_STATUS: Record<string, { label: string; tone: ClientDetailReport["tone"] }> = {
  done: { label: "Ready", tone: "ok" },
  queued: { label: "Queued", tone: "accent" },
  running: { label: "Rendering", tone: "accent" },
  failed: { label: "Failed", tone: "alert" },
};

export function reportViews(reports: ClientReportV1[], absolute: (url: string) => string, tz = "Asia/Kolkata"): ClientDetailReport[] {
  return reports.map((r) => {
    const st = REPORT_STATUS[r.status] ?? { label: cap(r.status), tone: "muted" as const };
    const n = r.sections?.length ?? 0;
    const when = dayMonth(r.created_at, tz);
    const lang = r.language === "hi" ? "Hindi" : "English";
    return {
      title: `${cap(r.template)} report${n ? `, ${n} sections` : ""}`,
      sent: `Generated ${when}, ${lang}`,
      sentKey: "Generated {date}, {lang}",
      sentParams: { date: when, lang },
      status: st.label,
      tone: st.tone,
      href: r.status === "done" && r.download_url ? absolute(r.download_url) : undefined,
    };
  });
}

/* ------------------------------------------------------------------- today */
const NEEDS: Record<TodayV1["needs_you"]["items"][number]["kind"], { tone: NeedsYouItem["tone"]; action: string }> = {
  followup: { tone: "amber", action: "Open" },
  missed_remedy: { tone: "amber", action: "Check in" },
  ended_plan: { tone: "amber", action: "Review" },
  failed_send: { tone: "alert", action: "Resend" },
};

export function needsYouItems(items: TodayV1["needs_you"]["items"]): NeedsYouItem[] {
  return items.map((i, idx): NeedsYouItem => {
    const base = { id: `${i.kind}-${i.client_id ?? idx}-${idx}`, who: i.client_name ?? "A client", action: NEEDS[i.kind].action, tone: NEEDS[i.kind].tone };
    const href = i.kind === "failed_send" ? "/needs-you" : i.client_id ? `/clients/${i.client_id}` : "/needs-you";
    if (i.kind === "followup") {
      const days = i.days ?? 0;
      const key = days <= 0 ? "follow-up is due today" : days === 1 ? "follow-up is 1 day overdue" : "follow-up is {n} days overdue";
      return { ...base, tone: days > 0 ? ("alert" as const) : base.tone, text: key.replace("{n}", String(days)), textKey: key, textParams: { n: days }, href };
    }
    if (i.kind === "missed_remedy") {
      const key = "missed a remedy day on {title}";
      return { ...base, text: key.replace("{title}", i.detail ?? ""), textKey: key, textParams: { title: i.detail ?? "" }, href };
    }
    if (i.kind === "ended_plan") {
      const key = "{title} has run its full cycle, close it or extend";
      return { ...base, text: key.replace("{title}", i.detail ?? ""), textKey: key, textParams: { title: i.detail ?? "" }, href };
    }
    const key = "a reminder could not be sent";
    return { ...base, text: key, textKey: key, textParams: {}, href };
  });
}

export function skyItems(events: TodayV1["sky"], tz: string): SkyItem[] {
  return events.map((e) => ({
    date: dayMonth(e.at, tz),
    title: skyTitle(e.kind, e.planet, e.sign),
    touched: e.clients_touched,
    kind: e.kind,
    planet: e.planet,
    sign: e.sign,
  }));
}

/** English title for a sky event; the Today screen writes its own in the language in use. */
export function skyTitle(kind: SkyItem["kind"], planet: string | undefined, sign: string | undefined): string {
  const p = planet ? cap(planet) : "";
  switch (kind) {
    case "ingress":
      return `${p} enters ${sign}`;
    case "retrograde-station":
      return `${p} stations retrograde in ${sign}`;
    case "direct-station":
      return `${p} stations direct in ${sign}`;
    case "amavasya":
      return `Amavasya in ${sign}`;
    case "purnima":
      return `Purnima in ${sign}`;
    default:
      return "";
  }
}

function consultCard(c: TodayV1["consultations"][number], tz: string): ConsultCard {
  const status =
    c.status === "prepared"
      ? { label: "Prepared", tone: "ok" as const }
      : c.status === "needs_birth_time"
        ? { label: "Needs birth time", tone: "alert" as const }
        : { label: "No chart yet", tone: "ink" as const };
  const houses: Record<number, string[]> = {};
  for (const [h, planets] of Object.entries(c.houses)) houses[Number(h)] = planets;
  return {
    id: c.id,
    clientId: c.client_id,
    time: clock(c.at, tz),
    clientName: c.client_name,
    chartId: c.chart_id,
    kind: "chart",
    status,
    topic: c.topic ?? "",
    headline: c.lagna_sign ? `${c.lagna_sign} lagna` : "",
    headlineKey: c.lagna_sign ? "{sign} lagna" : undefined,
    headlineParams: c.lagna_sign ? { sign: c.lagna_sign } : undefined,
    sub: "",
    dasha: c.maha ? { maha: c.maha, antar: c.antar } : undefined,
    miniHouses: Object.keys(houses).length ? houses : undefined,
  };
}

export function todayViewFromV1(t: TodayV1, practiceName = "", now = new Date()): TodayView {
  const tz = t.timezone;
  const name = t.practitioner_name ?? "";
  const pan = t.panchang;
  const place = t.place.label ?? "";
  const first = t.consultations[0];
  const ing = t.next_ingress;
  void now;
  return {
    practitioner: { name, firstName: name.split(/\s+/)[0] ?? "", practice: practiceName, initials: initialsOf(name || practiceName) },
    dateLine: "",
    consultCount: t.consultations.length,
    dateIso: t.date,
    timezone: tz,
    first: first ? { name: first.client_name, time: clock(first.at, tz), status: first.status } : undefined,
    panchang: pan
      ? {
          vara: pan.vara,
          varaDeva: VARA_DEVA[pan.vara] ?? "",
          sunrise: clock(pan.sunrise, tz),
          place,
          tithi: { name: pan.tithi.name, paksha: pan.paksha, until: `until ${clock(pan.tithi.ends_at, tz)}`, untilTime: clock(pan.tithi.ends_at, tz) },
          nakshatra: { name: pan.nakshatra.name, until: `until ${clock(pan.nakshatra.ends_at, tz)}`, untilTime: clock(pan.nakshatra.ends_at, tz) },
          rahuKaal: {
            range: `${clock(pan.rahu_kaal_start, tz)} to ${clock(pan.rahu_kaal_end, tz)}`,
            note: "avoid new starts",
            from: clock(pan.rahu_kaal_start, tz),
            to: clock(pan.rahu_kaal_end, tz),
          },
          ingress: ing
            ? {
                title: `${cap(ing.planet)} into ${ing.sign}`,
                note: `${dayMonth(ing.at, tz)}, touches ${ing.clients_touched} clients`,
                planet: ing.planet,
                sign: ing.sign,
                date: dayMonth(ing.at, tz),
                touched: ing.clients_touched,
              }
            : null,
        }
      : null,
    consults: t.consultations.map((c) => consultCard(c, tz)),
    needsYou: needsYouItems(t.needs_you.items),
    sky: skyItems(t.sky, tz),
  };
}

/* --------------------------------------------------------------- workspace */
export function workspaceFromLive(opts: { usage: UsageV1 | null; today: TodayV1 | null; practiceName: string; clientCount?: number }): WorkspaceMeta {
  const { usage, today, practiceName } = opts;
  const reports = usage?.meters.find((m) => m.metric === "reports");
  const clients = usage?.meters.find((m) => m.metric === "clients");
  const tz = today?.timezone ?? "Asia/Kolkata";
  return {
    clientCount: clients?.used ?? opts.clientCount ?? 0,
    needsYouCount: today?.needs_you.total ?? 0,
    reportsUsed: reports?.used ?? 0,
    reportsQuota: reports ? reports.limit : null,
    engine: "Engine v2 · Lahiri",
    practitioner: { name: practiceName, practice: practiceName, initials: initialsOf(practiceName) },
    consults: (today?.consultations ?? []).map((c, i) => ({ clientName: c.client_name, time: clock(c.at, tz), active: i === 0 })),
  };
}
