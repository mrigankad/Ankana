"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Check } from "lucide-react";
import type { ReactNode } from "react";

import { Topbar } from "@/components/ankana/topbar";
import { SampleBadge, ServerUnavailable } from "@/components/ankana/server-unavailable";
import { Chip, Panel } from "@/components/ankana/ui";
import { Banner } from "@/components/ui/data";
import { Button } from "@/components/ui/button";
import { formatDay } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";
import { KIND_LABEL, notifyApi } from "@/lib/api/notify";
import type { NeedsYou } from "@/lib/api/notify";

function Section({ title, count, empty, children }: { title: string; count: number; empty: string; children: ReactNode }) {
  const t = useT();
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <h2 className="m-0 text-[20px] font-bold leading-6 text-ink">{t(title)}</h2>
        <span className="text-[13px] leading-4 text-soft">{count ? t("{n} waiting", { n: count }) : t("All clear")}</span>
      </div>
      {count ? (
        <Panel className="flex flex-col">{children}</Panel>
      ) : (
        <Panel className="flex items-center gap-3 px-4 py-3">
          <span aria-hidden className="grid size-6 shrink-0 place-items-center rounded-full bg-[var(--success-wash)] text-ok">
            <Check className="size-3.5" />
          </span>
          <span className="text-[14px] leading-5 text-body">{t(empty)}</span>
        </Panel>
      )}
    </section>
  );
}

function Row({ href, title, sub, chip, tone, last, action }: {
  href: string;
  title: string;
  sub: string;
  chip?: string;
  tone?: "ok" | "alert" | "accent" | "muted";
  last: boolean;
  action?: ReactNode;
}) {
  return (
    <div className={`flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3 transition-colors hover:bg-wash/40 ${last ? "" : "border-b border-rule"}`}>
      <Link href={href} className="flex min-w-0 grow basis-[220px] flex-col rounded-[4px] no-underline outline-none focus-visible:ring-2 focus-visible:ring-ring/50">
        <span className="text-[15px] font-bold leading-[18px] text-ink">{title}</span>
        <span className="text-[13px] leading-4 text-soft">{sub}</span>
      </Link>
      {chip ? <Chip tone={tone ?? "accent"} className="shrink-0 whitespace-nowrap py-[3px]">{chip}</Chip> : null}
      {action}
    </div>
  );
}

export default function NeedsYouPage() {
  const t = useT();
  const [d, setD] = useState<NeedsYou | null>(null);
  const [failed, setFailed] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(() => {
    notifyApi.needsYou().then(setD).catch(() => setFailed(true));
  }, []);
  useEffect(load, [load]);

  async function resend(id: string) {
    setMessage(null);
    try {
      await notifyApi.resend(id);
      setMessage(t("Queued to send again."));
      load();
    } catch (e) {
      setMessage(t("Could not resend. Try again."));
    }
  }

  const total = d ? d.followups.length + d.missed_remedies.length + d.ended_plans.length + d.failed_notifications.length : 0;
  return (
    <>
      <Topbar crumbs={[{ label: "Needs you" }]} />
      <main className="flex flex-1 flex-col gap-7 px-5 py-8 lg:px-10 lg:py-9">
        <div className="flex flex-col gap-1">
          <h1 className="m-0 flex items-center gap-3 text-[28px] font-bold leading-9 tracking-[-0.02em] text-ink lg:text-[32px] lg:leading-10">
            {t("Needs you")}
            {d?.sample ? <SampleBadge /> : null}
          </h1>
          <p className="m-0 text-[16px] leading-5 text-body">
            {d ? (total ? t(total === 1 ? "{n} thing waits on you." : "{n} things wait on you.", { n: total }) : t("Nothing is waiting on you.")) : t("Follow-ups, missed remedies and failed sends.")}
          </p>
        </div>
        {failed ? (
          <ServerUnavailable
            onRetry={() => {
              setFailed(false);
              load();
            }}
          />
        ) : null}
        {d?.sample ? (
          <Banner tone="info" title={t("Sample data")}>
            {t("These items are examples. Your own follow-ups, missed remedies and failed sends appear here once the API is connected.")}
          </Banner>
        ) : null}
        {message ? <p className="m-0 text-[14px] text-body" role="status">{message}</p> : null}
        {d ? (
          <>
            <Section title="Follow-ups due" count={d.followups.length} empty="No follow-ups are due.">
              {d.followups.map((f, i) => (
                <Row
                  key={f.consultation_id}
                  href={`/clients/${f.client_id}`}
                  title={f.client_name}
                  sub={f.topic ? t("{topic}, follow-up {date}", { topic: f.topic, date: formatDay(f.follow_up_date) }) : t("Follow-up {date}", { date: formatDay(f.follow_up_date) })}
                  chip={f.days_overdue > 0 ? t(f.days_overdue === 1 ? "{n} day overdue" : "{n} days overdue", { n: f.days_overdue }) : t("Due soon")}
                  tone={f.days_overdue > 0 ? "alert" : "accent"}
                  last={i === d.followups.length - 1}
                />
              ))}
            </Section>
            <Section title="Missed remedies" count={d.missed_remedies.length} empty="No remedies have been missed.">
              {d.missed_remedies.map((m, i) => (
                <Row
                  key={m.plan_id}
                  href={`/clients/${m.client_id}`}
                  title={m.client_name}
                  sub={t("{title}, day {day} of {total}. Missed {date}", { title: m.title, day: m.day_number, total: m.total_days, date: formatDay(m.last_missed_date) }) +
                    (m.restart_count ? t(", restarted {n}x", { n: m.restart_count }) : "") +
                    (m.extended_days ? t(", extended {n}d", { n: m.extended_days }) : "")}
                  chip={m.policy === "restart" ? t("Restarted") : m.policy === "extend" ? t("Extended") : t("Warned")}
                  tone="alert"
                  last={i === d.missed_remedies.length - 1}
                />
              ))}
            </Section>
            <Section title="Cycle finished" count={d.ended_plans.length} empty="No remedy cycles have just ended.">
              {d.ended_plans.map((p, i) => (
                <Row
                  key={p.plan_id}
                  href={`/clients/${p.client_id}`}
                  title={p.client_name}
                  sub={t("{title} ended {date}. Mark it complete or plan the next step.", { title: p.title, date: formatDay(p.end_date) })}
                  chip={t("Ended")}
                  tone="ok"
                  last={i === d.ended_plans.length - 1}
                />
              ))}
            </Section>
            <Section title="Failed sends" count={d.failed_notifications.length} empty="Every message went out.">
              {d.failed_notifications.map((n, i) => (
                <Row
                  key={n.id}
                  href={`/clients/${n.client_id}`}
                  title={n.client_name ?? t("Client")}
                  sub={t("{kind} by {channel}", { kind: t(KIND_LABEL[n.kind] ?? n.kind), channel: n.channel }) + (n.last_error ? `, ${n.last_error}` : "")}
                  chip={t("Failed")}
                  tone="alert"
                  last={i === d.failed_notifications.length - 1}
                  action={
                    <Button variant="ghost" size="sm" onClick={() => void resend(n.id)}>
                      {t("Resend")}
                    </Button>
                  }
                />
              ))}
            </Section>
          </>
        ) : null}
      </main>
    </>
  );
}
