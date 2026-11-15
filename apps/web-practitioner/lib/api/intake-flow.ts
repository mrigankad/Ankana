import { ProblemError } from "./v1";
import { v1Api } from "./live";
import type { IntakeSubmit } from "./intake";

export const CONSENT_NOTICE_VERSION = "2026-11";

/** The notice read to (or shown to) the client. Stored verbatim as evidence of consent. */
export const CONSENT_NOTICE_TEXT =
  "I agree that my birth details are stored by my astrologer and used to calculate my birth chart. " +
  "I can ask for my data to be corrected or deleted, and withdraw this consent at any time.";

/**
 * Client, consent, birth record, chart: the four steps behind "Generate chart".
 * Every step is safe to repeat: an existing client is reused, an identical birth
 * record is reused, and the chart call is idempotent on record and settings
 * (the API returns the existing chart with 200 instead of 201).
 */
export async function submitIntakeV1(input: IntakeSubmit): Promise<{ clientId: string; chartId: string; reused: boolean }> {
  let clientId = input.existingClientId ?? "";
  if (!clientId) {
    const c = await v1Api.createClient({ display_name: input.clientName || "Unnamed client" });
    clientId = c.id;
  }

  const consents = await v1Api.getConsents(clientId);
  if (!consents.active.chart_compute) {
    if (!input.consent) {
      throw new ProblemError(403, { code: "consent_required", purpose: "chart_compute", detail: "consent required" });
    }
    await v1Api.recordConsent(clientId, {
      purpose: "chart_compute",
      notice_version: input.consent.noticeVersion,
      notice_text: input.consent.noticeText,
      notice_language: "en",
      channel: input.consent.channel,
    });
  }

  const time = input.birthTime ? `${input.birthTime}:00` : null;
  const existing = input.existingClientId ? await v1Api.listBirthRecords(clientId).catch(() => []) : [];
  const same = existing.find(
    (r) =>
      r.birth_date === input.birthDate &&
      (r.birth_time ?? null) === time &&
      Math.abs(r.latitude - input.location.latitude) < 1e-4 &&
      Math.abs(r.longitude - input.location.longitude) < 1e-4 &&
      r.time_source === input.timeSource,
  );
  const record =
    same ??
    (await v1Api.createBirthRecord(clientId, {
      birth_date: input.birthDate,
      birth_time: time,
      time_source: input.timeSource,
      place_label: input.location.displayName,
      latitude: input.location.latitude,
      longitude: input.location.longitude,
      timezone_name: input.location.timezoneName,
    }));

  const res = await v1Api.generateChart(clientId, { birth_record_id: record.id, chart_style: input.style });
  return { clientId, chartId: res.chart.id, reused: res.chart.created === false };
}
