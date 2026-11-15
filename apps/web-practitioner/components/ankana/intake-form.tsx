"use client";

import type { LocationSearchResult } from "@astro/shared-types";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { BigKundali } from "@/components/ankana/big-kundali";
import { PRIMARY_FILL, PRIMARY_SHADOW } from "@/components/ankana/ui";
import { api, isFixtures } from "@/lib/api/client";
import { CONSENT_NOTICE_TEXT, CONSENT_NOTICE_VERSION } from "@/lib/api/intake-flow";
import { v1Api } from "@/lib/api/live";
import { problemMessage } from "@/lib/api/v1";
import {
  TIME_SOURCES,
  formatCoords,
  hhmm,
  isoDate,
  parseDate,
  shiftTime,
  to24h,
  two,
  varanasiSample,
  weekdayOf,
  zoneInfo,
  type LagnaPreviewView,
  type TimeSource,
} from "@/lib/api/intake";
import type { ClientRow } from "@/lib/api/types";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";

const FIELD = "rounded-[6px] border border-rule bg-white";
const NUM_INPUT =
  "h-[46px] shrink-0 rounded-[6px] border border-rule bg-white p-0 text-center text-[18px] font-bold leading-[22px] text-ink outline-none focus:border-sindoor";

function Label({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return (
    <label htmlFor={htmlFor} className="text-[13px] font-bold leading-4 text-body">
      {children}
    </label>
  );
}

function Hint({ children }: { children: ReactNode }) {
  return <div className="text-[12px] leading-4 text-soft">{children}</div>;
}

function digits(v: string, max: number) {
  return v.replace(/\D/g, "").slice(0, max);
}

function InfoCell({ label, value, ok, grow, first }: { label: string; value: string; ok?: boolean; grow?: string; first?: boolean }) {
  return (
    <div className={cn("flex min-w-[150px] basis-0 flex-col gap-[2px] px-[14px] py-[10px]", !first && "border-l border-rule")} style={{ flexGrow: grow ?? "1" }}>
      <div className="text-[12px] font-bold uppercase leading-4 text-soft">{label}</div>
      <div className={cn("text-[14px] font-bold leading-[18px]", ok ? "text-ok" : "text-ink")}>{value}</div>
    </div>
  );
}

export function IntakeForm() {
  const router = useRouter();
  const tr = useT();
  // Only the fixtures (demo) mode opens with the sample client from the design.
  const sample = isFixtures();

  const [clientName, setClientName] = useState(sample ? "Ananya Sharma" : "");
  const [dd, setDd] = useState(sample ? "15" : "");
  const [mm, setMm] = useState(sample ? "03" : "");
  const [yyyy, setYyyy] = useState(sample ? "1995" : "");
  const [hh, setHh] = useState(sample ? "06" : "");
  const [mi, setMi] = useState(sample ? "42" : "");
  const [pm, setPm] = useState(false);
  const [source, setSource] = useState<TimeSource>("certificate");
  const [placeText, setPlaceText] = useState(sample ? varanasiSample.displayName : "");
  const [location, setLocation] = useState<LocationSearchResult | null>(sample ? varanasiSample : null);
  const [results, setResults] = useState<LocationSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [ayanamsha, setAyanamsha] = useState("lahiri");
  const [style, setStyle] = useState<"north" | "south">("north");
  const [consentActive, setConsentActive] = useState<boolean | null>(null);
  const [consentChecked, setConsentChecked] = useState(false);
  const [consentChannel, setConsentChannel] = useState("in_person");
  const [previewNote, setPreviewNote] = useState("");
  const [lalKitab, setLalKitab] = useState(true);
  const [clients, setClients] = useState<ClientRow[]>([]);
  const [preview, setPreview] = useState<LagnaPreviewView | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listClients().then(setClients).catch(() => undefined);
  }, []);

  const date = useMemo(() => parseDate(dd, mm, yyyy), [dd, mm, yyyy]);
  const time = useMemo(() => to24h(hh, mi, pm), [hh, mi, pm]);
  const zone = useMemo(() => (date && location ? zoneInfo(location.timezoneName, date) : null), [date, location]);
  const existing = useMemo(
    () => clients.find((c) => c.name.trim().toLowerCase() === clientName.trim().toLowerCase()) ?? null,
    [clients, clientName],
  );

  // Does the matched client already have chart consent? Unknown clients always need it captured.
  useEffect(() => {
    if (isFixtures()) {
      setConsentActive(true);
      return;
    }
    if (!existing) {
      setConsentActive(false);
      return;
    }
    let live = true;
    v1Api
      .getConsents(existing.id)
      .then((c) => live && setConsentActive(Boolean(c.active.chart_compute)))
      .catch(() => live && setConsentActive(false));
    return () => {
      live = false;
    };
  }, [existing]);

  // Debounced place search while the typed text is not a confirmed place.
  useEffect(() => {
    if (location && placeText === location.displayName) return;
    if (placeText.trim().length < 3) {
      setResults([]);
      return;
    }
    setSearching(true);
    const t = setTimeout(() => {
      api
        .searchLocations(placeText)
        .then(setResults)
        .catch(() => setResults([]))
        .finally(() => setSearching(false));
    }, 350);
    return () => clearTimeout(t);
  }, [placeText, location]);

  // Live lagna preview whenever the birth moment is complete.
  useEffect(() => {
    if (!date || !time || !location) {
      setPreview(null);
      return;
    }
    let live = true;
    const t = setTimeout(() => {
      setPreviewNote("");
      api
        .previewLagna({ birthDate: isoDate(date), birthTime: hhmm(time), location })
        .then((p) => live && setPreview(p))
        .catch((cause) => {
          if (!live) return;
          setPreview(null);
          setPreviewNote(problemMessage(cause, "The preview is not available right now. You can still generate the chart."));
        });
    }, 250);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [date, time, location]);

  const timeOk = Boolean(time) || source === "unknown";
  const consentOk = consentActive !== false || consentChecked;
  const ready = Boolean(date && timeOk && location && clientName.trim().length > 1 && consentOk) && !submitting;

  async function generate() {
    if (!date || !timeOk || !location) return;
    setError("");
    setSubmitting(true);
    try {
      const r = await api.submitIntake({
        clientName: clientName.trim(),
        existingClientId: existing?.id ?? null,
        birthDate: isoDate(date),
        birthTime: time ? hhmm(time) : "",
        timeSource: source,
        placeText,
        location,
        style,
        consent: consentActive === false && consentChecked ? { noticeVersion: CONSENT_NOTICE_VERSION, noticeText: CONSENT_NOTICE_TEXT, channel: consentChannel } : null,
      });
      router.push(r.chartId ? `/charts/${r.chartId}${r.reused ? "?reused=1" : ""}` : `/clients/${r.clientId}`);
    } catch (cause) {
      setError(problemMessage(cause, tr("Something went wrong. Try again.")));
      setSubmitting(false);
    }
  }

  const half = preview?.windowMinutes ?? 14;
  const rangeStart = time ? hhmm(shiftTime(time, -half)) : "";
  const rangeEnd = time ? hhmm(shiftTime(time, half)) : "";
  const recorded = time ? hhmm(time) : "";

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) void generate();
      }}
      className="flex flex-col gap-8 lg:flex-row lg:items-start"
    >
      <div className="flex w-full min-w-0 shrink-0 flex-col gap-4 lg:w-[660px]">
        <div className="flex flex-col gap-[6px]">
          <Label htmlFor="intake-client">{tr("Client")}</Label>
          <div className={cn(FIELD, "flex h-[46px] items-center justify-between gap-3 px-[14px] focus-within:border-sindoor")}>
            <input
              id="intake-client"
              value={clientName}
              onChange={(e) => setClientName(e.target.value)}
              placeholder={tr("Full name")}
              autoComplete="off"
              className="min-w-0 grow border-0 bg-transparent p-0 text-[16px] font-bold leading-5 text-ink outline-none placeholder:font-normal placeholder:text-soft"
            />
            <span className="shrink-0 text-[13px] leading-4 text-soft">{existing ? tr("Existing client") : clientName.trim() ? tr("New client") : ""}</span>
          </div>
        </div>

        <div className="flex flex-col gap-4 sm:flex-row">
          <div className="flex grow basis-0 flex-col gap-[6px]">
            <Label>{tr("Date of birth")}</Label>
            <div className="flex flex-wrap items-center gap-2 sm:flex-nowrap">
              <input aria-label={tr("Day")} inputMode="numeric" value={dd} onChange={(e) => setDd(digits(e.target.value, 2))} placeholder="DD" className={cn(NUM_INPUT, "w-[58px] placeholder:font-normal placeholder:text-soft")} />
              <input aria-label={tr("Month")} inputMode="numeric" value={mm} onChange={(e) => setMm(digits(e.target.value, 2))} placeholder="MM" className={cn(NUM_INPUT, "w-[58px] placeholder:font-normal placeholder:text-soft")} />
              <input aria-label={tr("Year")} inputMode="numeric" value={yyyy} onChange={(e) => setYyyy(digits(e.target.value, 4))} placeholder="YYYY" className={cn(NUM_INPUT, "w-[84px] placeholder:font-normal placeholder:text-soft")} />
              {date ? (
                <span className="flex items-center gap-[6px] rounded-[4px] bg-ok-wash px-[10px] py-[6px]">
                  <svg width="13" height="13" viewBox="0 0 14 14" aria-hidden className="shrink-0">
                    <path d="M2.5 7.5L5.5 10.5L11.5 3.5" fill="none" stroke="var(--success)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span className="whitespace-pre text-[13px] font-bold leading-4 text-ok">{weekdayOf(date)}</span>
                </span>
              ) : dd || mm || yyyy.length === 4 ? (
                <span className="rounded-[4px] bg-alert-wash px-[10px] py-[6px] text-[13px] font-bold leading-4 text-alert">{tr("Not a real date")}</span>
              ) : null}
            </div>
            <Hint>{tr("Type DD MM YYYY. No date picker to mis-click.")}</Hint>
          </div>

          <div className="flex grow basis-0 flex-col gap-[6px]">
            <Label>{tr("Time of birth")}</Label>
            <div className="flex items-center gap-2">
              <input aria-label={tr("Hour")} inputMode="numeric" value={hh} onChange={(e) => setHh(digits(e.target.value, 2))} placeholder="HH" className={cn(NUM_INPUT, "w-[58px] placeholder:font-normal placeholder:text-soft")} />
              <span className="text-[18px] font-bold leading-[22px] text-soft">:</span>
              <input aria-label={tr("Minute")} inputMode="numeric" value={mi} onChange={(e) => setMi(digits(e.target.value, 2))} placeholder="MM" className={cn(NUM_INPUT, "w-[58px] placeholder:font-normal placeholder:text-soft")} />
              <div role="radiogroup" aria-label={tr("AM or PM")} className={cn(FIELD, "flex h-[46px] overflow-clip")}>
                {[false, true].map((isPm) => (
                  <button
                    key={String(isPm)}
                    type="button"
                    role="radio"
                    aria-checked={pm === isPm}
                    onClick={() => setPm(isPm)}
                    className={cn("w-[50px] text-[14px] font-bold leading-[18px]", pm === isPm ? "bg-ink text-white" : "bg-white text-soft")}
                  >
                    {isPm ? "PM" : "AM"}
                  </button>
                ))}
              </div>
            </div>
            <Hint>
              {time
                ? tr("{time12}, which is {time24} on a 24 hour clock.", {
                    time12: `${two(Number(hh))}:${two(Number(mi))} ${pm ? "PM" : "AM"}`,
                    time24: hhmm(time),
                  })
                : tr("Type HH MM on a 12 hour clock, then pick AM or PM.")}
            </Hint>
          </div>
        </div>

        <div className="flex flex-col gap-[6px]">
          <Label>{tr("Where did the birth time come from")}</Label>
          <div role="radiogroup" aria-label={tr("Birth time source")} className="flex flex-wrap gap-2">
            {TIME_SOURCES.map((s) => {
              const on = source === s.id;
              return (
                <button
                  key={s.id}
                  type="button"
                  role="radio"
                  aria-checked={on}
                  onClick={() => setSource(s.id)}
                  className={cn(
                    "rounded-[6px] border px-[14px] py-[9px] text-[14px] font-bold leading-[18px]",
                    on ? "border-ink bg-sidebar-wash text-ink" : "border-rule bg-white text-body hover:text-ink",
                  )}
                >
                  {tr(s.label)}
                </button>
              );
            })}
          </div>
        </div>

        <div className="relative flex flex-col gap-[6px]">
          <Label htmlFor="intake-place">{tr("Place of birth")}</Label>
          <div className={cn(FIELD, "flex h-[46px] items-center gap-[10px] px-[14px] focus-within:border-sindoor")}>
            <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden className="shrink-0">
              <circle cx="6" cy="6" r="4.2" fill="none" stroke="var(--text-soft)" strokeWidth="1.5" strokeLinecap="round" />
              <path d="M9.2 9.2L12 12" fill="none" stroke="var(--text-soft)" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <input
              id="intake-place"
              value={placeText}
              autoComplete="off"
              onChange={(e) => {
                setPlaceText(e.target.value);
                setLocation(null);
              }}
              placeholder={tr("Start typing a town or city")}
              className="min-w-0 grow border-0 bg-transparent p-0 text-[16px] font-bold leading-5 text-ink outline-none placeholder:font-normal placeholder:text-soft"
            />
          </div>
          {!location && placeText.trim().length >= 3 ? (
            <ul aria-label={tr("Place matches")} className="absolute inset-x-0 top-[76px] z-10 m-0 list-none overflow-clip rounded-[6px] border border-rule bg-white p-0 shadow-[0_8px_24px_rgba(34,30,29,0.10)]">
              {results.map((r) => (
                <li key={r.providerPlaceId}>
                  <button
                    type="button"
                    aria-label={tr("Confirm {place}", { place: r.displayName })}
                    onClick={() => {
                      setLocation(r);
                      setPlaceText(r.displayName);
                      setResults([]);
                    }}
                    className="flex w-full items-baseline justify-between gap-3 border-b border-rule bg-white px-[14px] py-[10px] text-left last:border-b-0 hover:bg-wash-soft"
                  >
                    <span className="text-[14px] font-bold leading-[18px] text-ink">{r.displayName}</span>
                    <span className="text-[12px] leading-4 text-soft">{formatCoords(r.latitude, r.longitude)}</span>
                  </button>
                </li>
              ))}
              {!results.length ? (
                <li className="px-[14px] py-[10px] text-[13px] leading-4 text-body">
                  {searching ? tr("Searching") : tr("No matching places. Try adding the district or state.")}
                </li>
              ) : null}
            </ul>
          ) : null}
          <div className="flex flex-wrap rounded-[6px] border border-rule bg-sidebar-wash">
            <InfoCell first label={tr("Coordinates")} value={location ? formatCoords(location.latitude, location.longitude) : tr("Pick a place")} />
            <InfoCell label={tr("Timezone")} value={location ? `${location.timezoneName}${zone ? `, ${zone.offsetLabel}` : ""}` : tr("Pick a place")} />
            <InfoCell
              grow="1.3"
              label={date ? tr("DST in {year}", { year: date.getUTCFullYear() }) : tr("DST")}
              value={zone ? zone.dst : tr("Needs a date and place")}
              ok={Boolean(zone && !zone.isDst)}
            />
          </div>
        </div>

        <div className="flex flex-wrap items-end gap-4">
          <div className="flex min-w-[200px] grow basis-0 flex-col gap-[6px]">
            <Label htmlFor="intake-ayanamsha">{tr("Ayanamsha")}</Label>
            <Select
              id="intake-ayanamsha"
              value={ayanamsha}
              onValueChange={setAyanamsha}
              options={[{ value: "lahiri", label: tr("Lahiri (Chitrapaksha)") }]}
            />
          </div>
          <div className="flex flex-col gap-[6px]">
            <Label>{tr("Chart style")}</Label>
            <div role="radiogroup" aria-label={tr("Chart style")} className={cn(FIELD, "flex h-[42px] overflow-clip")}>
              {(["north", "south"] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  role="radio"
                  aria-checked={style === s}
                  onClick={() => setStyle(s)}
                  className={cn("w-[74px] text-[14px] font-bold leading-[18px]", style === s ? "bg-ink text-white" : "bg-white text-soft")}
                >
                  {s === "north" ? tr("North") : tr("South")}
                </button>
              ))}
            </div>
          </div>
          <button type="button" role="switch" aria-checked={lalKitab} onClick={() => setLalKitab((v) => !v)} className="flex h-[42px] items-center gap-[10px] bg-transparent p-0">
            <span className={cn("flex h-[22px] w-[38px] items-center rounded-[8px] px-[3px]", lalKitab ? "justify-end bg-sindoor" : "justify-start bg-[var(--rule-strong)]")}>
              <span className="size-4 rounded-full bg-white" />
            </span>
            <span className="whitespace-pre text-[14px] font-bold leading-[18px] text-ink">{lalKitab ? tr("Lal Kitab on") : tr("Lal Kitab off")}</span>
          </button>
        </div>

        {consentActive === false ? (
          <section aria-label="Client consent" className="flex flex-col gap-3 rounded-[10px] border border-rule bg-wash-soft p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="text-[15px] font-bold leading-[18px] text-ink">Consent to calculate the chart</div>
              <span className="rounded-full bg-wash px-[10px] py-[3px] text-[12px] font-bold leading-4 text-accent-text">Required once</span>
            </div>
            <p className="m-0 text-[14px] leading-5 text-body">{CONSENT_NOTICE_TEXT}</p>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <button
                type="button"
                role="checkbox"
                aria-checked={consentChecked}
                onClick={() => setConsentChecked((v) => !v)}
                className="flex items-center gap-[10px] bg-transparent p-0 text-left"
              >
                <span className={cn("flex size-5 shrink-0 items-center justify-center rounded-[4px] border", consentChecked ? "border-ink bg-ink" : "border-rule bg-white")}>
                  {consentChecked ? (
                    <svg width="12" height="12" viewBox="0 0 14 14" aria-hidden>
                      <path d="M2.5 7.5L5.5 10.5L11.5 3.5" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  ) : null}
                </span>
                <span className="text-[14px] font-bold leading-[18px] text-ink">The client has heard or read this notice and agrees</span>
              </button>
              <Select
                aria-label={tr("How consent was given")}
                className="h-[38px] w-[170px]"
                value={consentChannel}
                onValueChange={setConsentChannel}
                options={[
                    { value: "in_person", label: tr("In person") },
                    { value: "phone", label: tr("On the phone") },
                    { value: "whatsapp", label: "WhatsApp" },
                  ]}
              />
            </div>
          </section>
        ) : null}

        <button
          type="submit"
          disabled={!ready}
          className="flex h-14 items-center justify-center gap-[10px] rounded-xl text-[18px] font-bold leading-[22px] text-white disabled:opacity-50"
          style={{ backgroundColor: "var(--accent)", backgroundImage: PRIMARY_FILL, boxShadow: PRIMARY_SHADOW }}
        >
          {submitting ? tr("Casting chart") : tr("Generate chart")}
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden className="shrink-0">
            <path d="M3 9H15M10 4L15 9L10 14" fill="none" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        {error ? (
          <p role="alert" className="m-0 rounded-[6px] bg-alert-wash px-[14px] py-[10px] text-[14px] font-bold leading-[18px] text-alert">
            {error}
          </p>
        ) : null}
      </div>

      <aside aria-label={tr("Live lagna preview")} className="flex min-w-0 grow basis-0 flex-col">
        <div className="flex flex-col overflow-clip rounded-[10px] border border-rule">
          <div className="flex items-center justify-between border-b border-rule px-[18px] py-3">
            <div className="flex items-center gap-2">
              <span className="size-2 shrink-0 rounded bg-ok" />
              <span className="text-[13px] font-bold leading-4 text-ink">{tr("Live lagna preview")}</span>
            </div>
            <span className="text-[13px] leading-4 text-soft">{tr("Updates as you type")}</span>
          </div>
          <div className="flex min-h-[340px] flex-col items-center gap-[14px] bg-wash-soft px-[18px] py-[22px]">
            {preview ? (
              <>
                <BigKundali houses={preview.houses} lagnaSign={preview.lagnaSign} />
                <div className="flex flex-col items-center gap-[2px] text-center">
                  <div className="text-[24px] font-bold leading-[30px] tracking-[-0.01em] text-ink">{preview.lagna}</div>
                  <div className="text-[14px] leading-[18px] text-body">{preview.moon}</div>
                </div>
              </>
            ) : (
              <p className="m-auto max-w-[28ch] text-center text-[14px] leading-5 text-body">
                {previewNote || tr("Enter a valid date, time and place and the lagna appears here before you cast the chart.")}
              </p>
            )}
          </div>
        </div>

        {preview ? (
          <div className="mt-4 flex flex-col gap-3 rounded-[10px] bg-wash px-[18px] py-4">
            <div className="flex items-center gap-2">
              <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden className="shrink-0">
                <path d="M8 2L14.5 13.5H1.5Z" fill="none" stroke="var(--accent-hover)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M8 6.5V9.5M8 11.7V11.8" fill="none" stroke="var(--accent-hover)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <div className="text-[15px] font-bold leading-[18px] text-accent-text">{preview.navamsaNote}</div>
            </div>
            <div className="flex flex-col gap-[6px]">
              <div className="relative h-2 rounded bg-white">
                <div className="absolute left-0 top-0 h-2 w-full rounded bg-[var(--accent-200)]" />
                <div className="absolute top-[-3px] size-[14px] rounded-[5px] border-2 border-white bg-ink" style={{ left: "calc(50% - 7px)" }} />
              </div>
              <div className="flex justify-between text-[12px] font-bold leading-4">
                <span className="text-body">{rangeStart}</span>
                <span className="text-ink">{tr("{time} recorded", { time: recorded })}</span>
                <span className="text-body">{rangeEnd}</span>
              </div>
            </div>
            <div className="text-[14px] leading-[19px] text-body">{preview.safeNote}</div>
          </div>
        ) : null}
      </aside>
    </form>
  );
}
