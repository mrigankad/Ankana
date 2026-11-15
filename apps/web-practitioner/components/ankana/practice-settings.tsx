"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { Panel } from "@/components/ankana/ui";
import { Banner } from "@/components/ui/data";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { api, isFixtures } from "@/lib/api/client";
import { SampleBadge } from "@/components/ankana/server-unavailable";
import { getPractice, getPracticePlace, renamePractice, setPracticePlace, setTimezone } from "@/lib/api/team";
import type { PracticePlace } from "@/lib/api/team";
import type { LocationSearchResult } from "@astro/shared-types";
import { problemMessage } from "@/lib/api/v1";
import { useT } from "@/lib/i18n/provider";
import { authEnabled, refreshSession } from "@/lib/auth/session";

const ZONES = [
  { value: "Asia/Kolkata", label: "India (IST)" },
  { value: "Asia/Dubai", label: "Gulf (GST)" },
  { value: "Asia/Singapore", label: "Singapore" },
  { value: "Europe/London", label: "United Kingdom" },
  { value: "America/New_York", label: "US Eastern" },
  { value: "America/Los_Angeles", label: "US Pacific" },
  { value: "Australia/Sydney", label: "Sydney" },
];

function parseCoord(v: string, min: number, max: number): number | null {
  if (!v.trim()) return null;
  const n = Number(v);
  return Number.isFinite(n) && n >= min && n <= max ? n : null;
}

function PlaceSection() {
  const t = useT();
  const toast = useToast();
  const found = useRef(new Map<string, LocationSearchResult>());
  const [loaded, setLoaded] = useState(false);
  const [label, setLabel] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [zone, setZone] = useState<string | null>(null);
  const [picked, setPicked] = useState<{ value: string; label: string } | null>(null);
  const [saved, setSaved] = useState<PracticePlace | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPracticePlace()
      .then((p) => {
        setSaved(p);
        if (p.source === "practice") {
          setLabel(p.label ?? "");
          setLat(p.latitude != null ? String(p.latitude) : "");
          setLon(p.longitude != null ? String(p.longitude) : "");
        }
        setLoaded(true);
      })
      .catch((e) => setError(problemMessage(e, t("The place could not be loaded."))));
  }, [t]);

  async function search(q: string) {
    if (q.trim().length < 3) return [];
    const rows = await api.searchLocations(q);
    return rows.map((r) => {
      found.current.set(r.providerPlaceId, r);
      return { value: r.providerPlaceId, label: r.displayName, description: `${r.latitude.toFixed(4)}, ${r.longitude.toFixed(4)}` };
    });
  }

  function choose(value: string | null) {
    const r = value ? found.current.get(value) : null;
    if (!r) {
      setPicked(null);
      return;
    }
    setPicked({ value: r.providerPlaceId, label: r.displayName });
    setLabel(r.displayName);
    setLat(String(r.latitude));
    setLon(String(r.longitude));
    setZone(r.timezoneName);
  }

  const latN = parseCoord(lat, -90, 90);
  const lonN = parseCoord(lon, -180, 180);
  const valid = Boolean(label.trim()) && latN != null && lonN != null;

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!valid || latN == null || lonN == null) return;
    setBusy(true);
    setError(null);
    try {
      const p = await setPracticePlace({ place_label: label.trim(), latitude: latN, longitude: lonN });
      if (zone) await setTimezone(zone);
      setSaved(p);
      isFixtures() ? toast(t("Sample mode: changes are not saved")) : toast(t("Place saved"), { tone: "success" });
    } catch (err) {
      setError(problemMessage(err, t("The place could not be saved.")));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel className="p-6">
      <form onSubmit={save} className="flex flex-col gap-5">
        <div className="flex flex-col gap-1">
          <h2 className="m-0 text-[20px] font-bold leading-[26px] text-ink">{t("Practice place")}</h2>
          <p className="m-0 text-[14px] leading-5 text-body">
            {saved && saved.source === "practice" ? t("Today's panchang is worked out for this place.") : t("Set where the practice sits and today's tithi, nakshatra and Rahu kaal appear on the Today page.")}
          </p>
        </div>
        {error ? <Banner tone="error">{error}</Banner> : null}
        <Field label={t("Search for a place")} hint={t("Type a town or city and pick a match. It fills the fields below.")}>
          <Combobox
            aria-label={t("Search for a place")}
            value={picked?.value ?? null}
            selectedOption={picked}
            onChange={(v) => choose(v)}
            loadOptions={search}
            disabled={!loaded}
            placeholder={t("Start typing a town or city")}
            searchPlaceholder={t("Town or city")}
            emptyText={t("No matching places. Try adding the district or state.")}
          />
        </Field>
        <Field label={t("Place name")} htmlFor="practice-place-label">
          <Input id="practice-place-label" maxLength={200} value={label} disabled={!loaded} onChange={(e) => setLabel(e.target.value)} />
        </Field>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label={t("Latitude")} htmlFor="practice-place-lat" hint={t("Between -90 and 90")}>
            <Input id="practice-place-lat" inputMode="decimal" value={lat} disabled={!loaded} onChange={(e) => setLat(e.target.value)} aria-invalid={lat.trim() !== "" && latN == null} />
          </Field>
          <Field label={t("Longitude")} htmlFor="practice-place-lon" hint={t("Between -180 and 180")}>
            <Input id="practice-place-lon" inputMode="decimal" value={lon} disabled={!loaded} onChange={(e) => setLon(e.target.value)} aria-invalid={lon.trim() !== "" && lonN == null} />
          </Field>
        </div>
        {zone ? <p className="m-0 text-[13px] leading-4 text-body">{t("Time zone {zone} will be applied when you save.", { zone })}</p> : null}
        <div className="flex justify-end">
          <Button type="submit" size="md" loading={busy} disabled={!loaded || !valid}>
            {t("Save place")}
          </Button>
        </div>
      </form>
    </Panel>
  );
}

export function PracticeSettings() {
  const t = useT();
  const toast = useToast();
  const [name, setName] = useState("");
  const [zone, setZone] = useState("Asia/Kolkata");
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPractice()
      .then((p) => {
        setName(p.name);
        setZone(p.timezone);
        setLoaded(true);
      })
      .catch((e) => setError(problemMessage(e, t("The practice could not be loaded."))));
  }, [t]);

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await renamePractice(name.trim());
      await setTimezone(zone);
      if (authEnabled()) await refreshSession();
      isFixtures() ? toast(t("Sample mode: changes are not saved")) : toast(t("Practice saved"), { tone: "success" });
    } catch (err) {
      setError(problemMessage(err, t("The practice could not be saved.")));
    } finally {
      setBusy(false);
    }
  }

  const zones = ZONES.some((z) => z.value === zone) ? ZONES : [...ZONES, { value: zone, label: zone }];

  return (
    <div className="flex max-w-[760px] flex-col gap-6 px-4 py-6 lg:px-10 lg:py-8">
      <div className="flex flex-col gap-1">
        <h1 className="m-0 text-[32px] font-bold leading-[38px] tracking-[-0.01em] text-ink">{t("Practice")}{isFixtures() ? <SampleBadge className="ml-3 align-middle" /> : null}</h1>
        <p className="m-0 text-[15px] leading-5 text-body">{t("The name your clients see on invites, reminders and reports.")}</p>
      </div>
      {error ? <Banner tone="error">{error}</Banner> : null}
      <Panel className="p-6">
        <form onSubmit={save} className="flex flex-col gap-5">
          <Field label={t("Practice name")} htmlFor="practice-name">
            <Input id="practice-name" required maxLength={200} value={name} disabled={!loaded} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label={t("Time zone")} hint={t("Daily reminders go out in this zone.")}>
            <Select
              aria-label={t("Time zone")}
              value={zone}
              disabled={!loaded}
              onValueChange={setZone}
              options={zones.map((z) => ({ value: z.value, label: t(z.label) }))}
            />
          </Field>
          <div className="flex justify-end">
            <Button type="submit" size="md" loading={busy} disabled={!loaded || !name.trim()}>
              {t("Save practice")}
            </Button>
          </div>
        </form>
      </Panel>
      <PlaceSection />
      <Panel className="flex items-center justify-between gap-4 bg-wash-soft px-6 py-5">
        <div className="flex flex-col gap-[2px]">
          <span className="text-[16px] font-bold leading-5 text-ink">{t("Branding")}</span>
          <span className="text-[14px] leading-[18px] text-body">{t("Logo, colours and the footer on every report.")}</span>
        </div>
        <Link href="/settings/branding" className="text-[14px] font-bold text-accent-text no-underline hover:underline">
          {t("Open branding")}
        </Link>
      </Panel>
    </div>
  );
}
