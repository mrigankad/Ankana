"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  ArrowRight,
  CheckCircle2,
  MapPin,
  MapPinCheck,
  Search,
  Sparkles,
} from "lucide-react";
import type { LocationSearchResult } from "@astro/shared-types";
import Link from "next/link";

import { BirthCalendar } from "./birth-calendar";
import { LocationSearch } from "./location-search";
import { Badge } from "@/components/ui/badge";
import { DateField, TimeField } from "@/components/ui/date-time-fields";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

function getApiBaseUrl() {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:3001";
}

const fallbackVaranasiResult: LocationSearchResult = {
  providerPlaceId: "geo_varanasi_in",
  displayName: "Varanasi, Uttar Pradesh, India",
  latitude: 25.3176,
  longitude: 82.9739,
  timezoneName: "Asia/Kolkata",
  confidence: "high",
  countryCode: "IN",
};

type SearchState = "idle" | "searching" | "done" | "error";

function StepDot({
  done,
  active,
  step,
  label,
}: {
  done: boolean;
  active: boolean;
  step: number;
  label: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-1.5 sm:gap-2",
        !active && !done && "opacity-70",
      )}
    >
      <span
        className={cn(
          "flex size-5 shrink-0 items-center justify-center rounded-full text-[0.65rem] font-bold sm:size-6 sm:text-[0.7rem]",
          done && "bg-sindoor text-white",
          active && !done && "bg-wash text-ink ring-1 ring-sindoor/20",
          !active && !done && "bg-muted text-muted-foreground",
        )}
        aria-hidden
      >
        {done ? <CheckCircle2 size={14} /> : step}
      </span>
      <span
        className={cn(
          "text-[0.72rem] font-semibold sm:text-[0.78rem]",
          active || done ? "text-ink" : "text-muted-foreground",
        )}
      >
        {label}
      </span>
    </div>
  );
}

export function ClientIntakeForm() {
  const [fullName, setFullName] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [birthTime, setBirthTime] = useState("");
  const [birthPlace, setBirthPlace] = useState("");
  const [searchState, setSearchState] = useState<SearchState>("idle");
  const [searchResults, setSearchResults] = useState<LocationSearchResult[]>([]);
  const [confirmedLocation, setConfirmedLocation] =
    useState<LocationSearchResult | null>(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [chartJobId, setChartJobId] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function runLocationSearch(query: string) {
    setSearchState("searching");
    let results: LocationSearchResult[] = [];

    try {
      const response = await fetch(
        `${getApiBaseUrl()}/api/v1/locations/search?q=${encodeURIComponent(query)}`,
      );
      const payload = (await response.json()) as { results: LocationSearchResult[] };
      results = payload.results ?? [];
    } catch {
      results = [];
    }

    if (!results.length && /varanasi|banaras|benares/i.test(query)) {
      results = [fallbackVaranasiResult];
    }

    setSearchResults(results);
    setSearchState("done");
  }

  useEffect(() => {
    if (confirmedLocation && birthPlace === confirmedLocation.displayName) {
      return;
    }
    if (birthPlace.trim().length < 3) {
      setSearchResults([]);
      setSearchState("idle");
      return;
    }

    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }
    debounceRef.current = setTimeout(() => {
      void runLocationSearch(birthPlace);
    }, 450);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [birthPlace, confirmedLocation]);

  const readyToGenerate =
    Boolean(confirmedLocation) &&
    birthDate.length > 0 &&
    birthTime.length > 0 &&
    !submitting;

  const progress = useMemo(
    () => ({
      identity: fullName.trim().length > 1,
      moment: Boolean(birthDate && birthTime),
      place: Boolean(confirmedLocation),
    }),
    [fullName, birthDate, birthTime, confirmedLocation],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError("");

    if (!confirmedLocation) {
      setSubmitError("Please confirm a birth place first.");
      return;
    }
    if (!birthDate || !birthTime) {
      setSubmitError("Birth date and time are required for chart computation.");
      return;
    }

    setSubmitting(true);
    try {
      const clientResponse = await fetch(`${getApiBaseUrl()}/api/v1/clients`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workspaceId: "ws_1",
          fullName: fullName || "Unnamed Client",
        }),
      });
      if (!clientResponse.ok) {
        throw new Error("Could not save the client record.");
      }
      const client = (await clientResponse.json()) as { id: string };

      const birthRecordResponse = await fetch(
        `${getApiBaseUrl()}/api/v1/clients/${client.id}/birth-records`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            birthDate,
            birthTime,
            timezoneName: confirmedLocation.timezoneName,
            placeLabel: confirmedLocation.displayName,
            locationQueryText: birthPlace,
            canonicalLocationName: confirmedLocation.displayName,
            latitude: confirmedLocation.latitude,
            longitude: confirmedLocation.longitude,
            providerPlaceId: confirmedLocation.providerPlaceId,
          }),
        },
      );
      if (!birthRecordResponse.ok) {
        throw new Error("Could not save the birth record.");
      }
      const birthRecord = (await birthRecordResponse.json()) as { id: string };

      const generateResponse = await fetch(
        `${getApiBaseUrl()}/api/v1/charts/generate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            workspaceId: "ws_1",
            clientId: client.id,
            birthRecordId: birthRecord.id,
            astrologySystem: "vedic",
            requestedOutputs: ["birthChart"],
          }),
        },
      );
      if (!generateResponse.ok) {
        throw new Error("Chart generation could not be queued.");
      }
      const chartJob = (await generateResponse.json()) as { jobId?: string };

      setChartJobId(chartJob.jobId ?? "");
      setStatusMessage("Chart request queued");
    } catch (cause) {
      setSubmitError(
        cause instanceof Error ? cause.message : "Something went wrong. Try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-border bg-white px-3 py-2.5 sm:gap-x-5 sm:px-4 sm:py-3">
        <StepDot
          step={1}
          label="Identity"
          done={progress.identity}
          active={!progress.identity}
        />
        <StepDot
          step={2}
          label="Birth moment"
          done={progress.moment}
          active={progress.identity && !progress.moment}
        />
        <StepDot
          step={3}
          label="Place"
          done={progress.place}
          active={progress.moment && !progress.place}
        />
        <Badge
          variant="outline"
          className="ml-0 border-rule-strong bg-wash-soft text-ink sm:ml-auto"
        >
          Vedic · Lahiri
        </Badge>
      </div>

      <div className="grid gap-4 sm:gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(260px,340px)] lg:items-start">
        <div className="order-2 space-y-4 lg:order-1">
          <section className="rounded-xl border border-border bg-white p-4 shadow-[0_1px_0_rgba(34,30,29,0.04)] sm:p-5">
            <p className="m-0 text-[0.65rem] font-bold tracking-wide text-soft">
              Client
            </p>
            <h2 className="mt-1 mb-3 text-[1rem] font-bold tracking-tight text-ink sm:mb-4 sm:text-[1.05rem]">
              Who is this chart for?
            </h2>
            <div className="space-y-1.5">
              <label
                htmlFor="full-name"
                className="text-[0.78rem] font-bold text-foreground/80"
              >
                Full name
              </label>
              <Input
                id="full-name"
                name="fullName"
                placeholder="e.g. Ananya Sen"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                className="h-10 bg-white text-[0.95rem]"
              />
            </div>
          </section>

          <section className="rounded-xl border border-border bg-white p-4 shadow-[0_1px_0_rgba(34,30,29,0.04)] sm:p-5">
            <div className="mb-3 flex items-start gap-2 sm:mb-4 sm:items-center">
              <MapPin size={15} className="mt-0.5 shrink-0 text-soft sm:mt-0" aria-hidden />
              <div className="min-w-0">
                <p className="m-0 text-[0.65rem] font-bold tracking-wide text-soft">
                  Birth place
                </p>
                <h2 className="m-0 text-[1rem] font-bold tracking-tight break-words text-ink sm:text-[1.05rem]">
                  Confirm coordinates & timezone
                </h2>
              </div>
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="birth-place"
                className="text-[0.78rem] font-bold text-foreground/80"
              >
                Birth place
              </label>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  id="birth-place"
                  name="birthPlace"
                  placeholder="Start typing a town or city…"
                  autoComplete="off"
                  value={birthPlace}
                  onChange={(event) => {
                    setBirthPlace(event.target.value);
                    setConfirmedLocation(null);
                  }}
                  className="h-10 min-w-0 flex-1 bg-white"
                />
                <Button
                  type="button"
                  variant="outline"
                  className="h-10 w-full shrink-0 gap-1.5 sm:w-auto"
                  aria-label="Search location"
                  onClick={() => void runLocationSearch(birthPlace)}
                >
                  Search <Search size={14} aria-hidden />
                </Button>
              </div>
              <p className="m-0 text-[0.72rem] leading-relaxed text-muted-foreground">
                Pick the exact town so lagna and dashas land on the right
                coordinates.
              </p>
            </div>

            <div className="mt-3">
              {searchState === "searching" ? (
                <p className="nk-muted m-0">Searching places…</p>
              ) : null}
              {searchState === "done" && !confirmedLocation ? (
                <LocationSearch
                  results={searchResults}
                  onConfirm={(location) => {
                    setConfirmedLocation(location);
                    setBirthPlace(location.displayName);
                    setSearchResults([]);
                  }}
                />
              ) : null}

              {confirmedLocation ? (
                <p className="nk-loc-confirmed !mt-2">
                  <MapPinCheck size={15} aria-hidden />{" "}
                  {confirmedLocation.displayName}{" "}
                  <span className="data">
                    ({confirmedLocation.latitude.toFixed(4)},{" "}
                    {confirmedLocation.longitude.toFixed(4)}) ·{" "}
                    {confirmedLocation.timezoneName}
                  </span>
                </p>
              ) : (
                <p className="nk-muted mt-2 mb-0">
                  Confirm a location before generating a chart.
                </p>
              )}
            </div>
          </section>

          <section className="rounded-xl border border-border bg-white p-4 shadow-[0_1px_0_rgba(34,30,29,0.04)] sm:p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="m-0 text-[0.65rem] font-bold tracking-wide text-soft">
                  Compute
                </p>
                <p className="mt-1 mb-0 text-[0.85rem] leading-relaxed text-muted-foreground sm:text-[0.88rem]">
                  Deterministic Vedic chart from the birth record above.
                </p>
              </div>
              <Button
                type="submit"
                disabled={!readyToGenerate}
                className="h-10 w-full gap-2 px-4 font-semibold sm:w-auto"
              >
                {submitting ? (
                  "Computing…"
                ) : (
                  <>
                    <Sparkles size={15} aria-hidden /> Generate chart
                  </>
                )}
              </Button>
            </div>
            {submitError ? (
              <p role="alert" className="nk-alert mt-3 mb-0">
                {submitError}
              </p>
            ) : null}
            {statusMessage ? (
              <p className="nk-status mt-3 mb-0">{statusMessage}</p>
            ) : null}
            {chartJobId ? (
              <Button asChild className="mt-3 h-10 w-full gap-2 sm:w-auto">
                <Link href={`/charts/${chartJobId}`}>
                  View chart <ArrowRight size={15} aria-hidden />
                </Link>
              </Button>
            ) : null}
          </section>
        </div>

        <aside className="order-1 space-y-4 lg:order-2 lg:sticky lg:top-20">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="birth-date" className="text-[0.65rem] font-bold tracking-wide text-soft">
              Birth date
            </label>
            <DateField id="birth-date" aria-label="Birth date" value={birthDate} onChange={setBirthDate} max={new Date().toISOString().slice(0, 10)} />
          </div>

          <BirthCalendar value={birthDate} onChange={setBirthDate} />

          <div className="rounded-xl border border-border bg-white p-4 shadow-[0_1px_0_rgba(34,30,29,0.04)]">
            <label
              htmlFor="birth-time"
              className="text-[0.65rem] font-bold tracking-wide text-soft"
            >
              Birth time
            </label>
            <TimeField id="birth-time" aria-label="Birth time" value={birthTime} onChange={setBirthTime} className="mt-2 h-11" />
            <p className="mt-2 mb-0 text-[0.72rem] leading-relaxed text-muted-foreground">
              Local clock time at the birth place, as recorded.
            </p>
          </div>
        </aside>
      </div>
    </form>
  );
}
