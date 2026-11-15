"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarCheck, FileText, Flower2, Target, UserRound, X } from "lucide-react";

import { useDateFmt } from "@/components/ankana/consult-brief";
import { StatusPill } from "@/components/ankana/consult-notes";
import { Panel } from "@/components/ankana/ui";
import { Banner } from "@/components/ui/data";
import { Button } from "@/components/ui/button";
import { DateField } from "@/components/ui/date-time-fields";
import { ConfirmDialog, Dialog, DialogContent, DialogDescription, DialogFooter, DialogTitle } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { SegmentedControl } from "@/components/ui/controls";
import { consultApi, LIFE_KINDS, onConsultChanged, type LifeKind, type PredictionStatus, type TimelineEventV1 } from "@/lib/api/consult";
import { problemMessage } from "@/lib/api/v1";
import { useT } from "@/lib/i18n/provider";

type Kind = TimelineEventV1["kind"];

const KIND_META: Record<Kind, { label: string; Icon: typeof Target; dot: string }> = {
  consultation: { label: "Consultation", Icon: CalendarCheck, dot: "bg-ink text-white" },
  prediction: { label: "Prediction", Icon: Target, dot: "bg-sindoor text-white" },
  remedy: { label: "Remedy", Icon: Flower2, dot: "bg-ok text-white" },
  report: { label: "Report", Icon: FileText, dot: "bg-soft text-white" },
  life_event: { label: "Life event", Icon: UserRound, dot: "bg-amber text-white" },
};

const KIND_LABEL: Record<LifeKind, string> = {
  marriage: "Marriage",
  child: "Child",
  job: "Job",
  business: "Business",
  move: "Move",
  education: "Education",
  health: "Health",
  loss: "Loss",
  travel: "Travel",
  other: "Other",
};

type Filter = "all" | Kind;

function LifeEventDialog({ clientId, open, onOpenChange, onSaved }: { clientId: string; open: boolean; onOpenChange: (o: boolean) => void; onSaved: () => void }) {
  const t = useT();
  const [date, setDate] = useState("");
  const [kind, setKind] = useState<LifeKind>("other");
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setDate("");
      setKind("other");
      setTitle("");
      setNotes("");
      setError("");
    }
  }, [open]);

  async function save() {
    setBusy(true);
    setError("");
    try {
      await consultApi.createLifeEvent(clientId, { event_date: date, kind, title: title.trim(), notes: notes.trim() || null });
      onSaved();
      onOpenChange(false);
    } catch (e) {
      setError(problemMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>{t("Add a life event")}</DialogTitle>
        <DialogDescription>{t("Record what happened in the client's life, so it sits beside the consultations and predictions.")}</DialogDescription>
        {error ? <Banner tone="error">{error}</Banner> : null}
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <span className="text-[13px] font-bold leading-4 text-ink">{t("When")}</span>
            <DateField aria-label={t("Event date")} value={date} onChange={setDate} showWeekday={false} />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-[13px] font-bold leading-4 text-ink">{t("Kind")}</span>
            <Select value={kind} onValueChange={(v) => setKind(v as LifeKind)} aria-label={t("Kind")} options={LIFE_KINDS.map((k) => ({ value: k, label: t(KIND_LABEL[k]) }))} />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-[13px] font-bold leading-4 text-ink">{t("What happened")}</span>
            <Input aria-label={t("What happened")} value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t("For example Changed jobs")} />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-[13px] font-bold leading-4 text-ink">{t("Notes")}</span>
            <Textarea aria-label={t("Notes")} value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} />
          </div>
        </div>
        <DialogFooter>
          <Button type="button" variant="ghost" size="md" onClick={() => onOpenChange(false)}>
            {t("Cancel")}
          </Button>
          <Button type="button" size="md" onClick={() => void save()} disabled={!date || !title.trim()} loading={busy}>
            {t("Save event")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** One vertical timeline: consultations, predictions, remedies, reports and life events. */
export function ClientTimeline({ clientId }: { clientId: string }) {
  const t = useT();
  const f = useDateFmt();
  const [events, setEvents] = useState<TimelineEventV1[] | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<TimelineEventV1 | null>(null);

  const reload = useCallback(
    () =>
      consultApi
        .getTimeline(clientId)
        .then(setEvents)
        .catch((e) => (setError(problemMessage(e)), setEvents([]))),
    [clientId],
  );
  useEffect(() => void reload(), [reload]);
  useEffect(() => onConsultChanged(() => void reload()), [reload]);

  const windowText = (raw: string) => {
    const m = /^(\S+) to (\S+)$/.exec(raw);
    const fmt = (v: string) => (/^\d{4}-/.test(v) ? f.day(v) : "...");
    return m ? t("{from} to {to}", { from: fmt(m[1]!), to: fmt(m[2]!) }) : raw;
  };

  const shown = useMemo(() => (events ?? []).filter((e) => filter === "all" || e.kind === filter), [events, filter]);

  return (
    <section className="flex flex-col gap-3" aria-label={t("Life timeline")}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="m-0 text-[20px] font-bold leading-6 text-ink">{t("Life timeline")}</h2>
        <Button type="button" variant="outline" size="md" onClick={() => setAdding(true)}>
          {t("Add life event")}
        </Button>
      </div>
      {error ? <Banner tone="error">{error}</Banner> : null}
      <div className="nk-scroll -mx-1 overflow-x-auto px-1">
        <SegmentedControl<Filter>
          aria-label={t("Filter the timeline")}
          value={filter}
          onValueChange={setFilter}
          size="sm"
          options={[
            { value: "all", label: t("All") },
            { value: "consultation", label: t("Consultations") },
            { value: "prediction", label: t("Predictions") },
            { value: "remedy", label: t("Remedies") },
            { value: "report", label: t("Reports") },
            { value: "life_event", label: t("Life events") },
          ]}
        />
      </div>
      <Panel className="px-4 py-4">
        {events === null ? (
          <p className="m-0 text-[14px] leading-5 text-body">{t("Loading")}</p>
        ) : shown.length === 0 ? (
          <p className="m-0 text-[14px] leading-5 text-body">{t("Nothing on the timeline yet.")}</p>
        ) : (
          <ol className="m-0 flex list-none flex-col p-0">
            {shown.map((e, i) => {
              const meta = KIND_META[e.kind];
              const last = i === shown.length - 1;
              const Icon = meta.Icon;
              return (
                <li key={e.id} className="flex gap-3" data-kind={e.kind}>
                  <div className="flex w-7 shrink-0 flex-col items-center">
                    <span className={`flex size-7 shrink-0 items-center justify-center rounded-full ${meta.dot}`}>
                      <Icon aria-hidden className="size-[14px]" />
                    </span>
                    {last ? null : <span className="w-px grow bg-rule" />}
                  </div>
                  <div className={`flex min-w-0 grow flex-col gap-[2px] ${last ? "" : "pb-5"}`}>
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] leading-4 text-soft">
                      <span className="font-bold uppercase tracking-[0.06em]">{t(meta.label)}</span>
                      <span>{f.day(e.at)}</span>
                      {e.kind === "prediction" && e.status ? <StatusPill status={e.status as PredictionStatus} /> : null}
                      {e.kind === "remedy" && e.status ? <span className="rounded-[4px] bg-chip px-2 py-[2px] font-bold text-body">{t(e.status === "active" ? "Active" : e.status === "draft" ? "Draft" : e.status === "completed" ? "Completed" : "Cancelled")}</span> : null}
                      {e.kind === "life_event" && e.status ? <span className="rounded-[4px] bg-chip px-2 py-[2px] font-bold text-body">{t(KIND_LABEL[e.status as LifeKind] ?? "Other")}</span> : null}
                    </div>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 text-[15px] font-bold leading-5 text-ink">{e.title}</div>
                      {e.kind === "life_event" ? (
                        <button type="button" aria-label={t("Remove {item}", { item: e.title })} onClick={() => setRemoving(e)} className="inline-flex size-6 shrink-0 items-center justify-center rounded-[4px] text-soft hover:bg-chip hover:text-ink">
                          <X aria-hidden className="size-[14px]" />
                        </button>
                      ) : null}
                    </div>
                    {e.detail ? <div className="text-[14px] leading-5 text-body">{e.kind === "prediction" ? windowText(e.detail) : e.detail}</div> : null}
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </Panel>
      <LifeEventDialog clientId={clientId} open={adding} onOpenChange={setAdding} onSaved={() => void reload()} />
      <ConfirmDialog
        open={Boolean(removing)}
        onOpenChange={(o) => !o && setRemoving(null)}
        title={t("Remove this life event?")}
        description={removing?.title}
        confirmLabel={t("Remove")}
        cancelLabel={t("Cancel")}
        tone="danger"
        onConfirm={async () => {
          if (!removing?.ref_id) return;
          try {
            await consultApi.deleteLifeEvent(removing.ref_id);
            setRemoving(null);
            await reload();
          } catch (e) {
            setError(problemMessage(e));
            setRemoving(null);
          }
        }}
      />
    </section>
  );
}
