"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import * as api from "@/lib/api/ai";
import type { AiConnection, AiRouting, ProviderKind, ProvidersOut, TestResult } from "@/lib/api/ai";
import { SampleBadge, ServerUnavailable } from "@/components/ankana/server-unavailable";
import { Btn, Chip, Panel } from "@/components/ankana/ui";
import { Banner } from "@/components/ui/data";
import { problemMessage } from "@/lib/api/v1";
import { useT } from "@/lib/i18n/provider";
import { ConfirmDialog } from "@/components/ui/dialog";
import { ProviderLogo } from "@/components/ui/provider-logo";
import { Select } from "@/components/ui/select";

const DOT: Record<api.Dot, string> = { ok: "var(--success)", bad: "var(--text-primary)", idle: "var(--rule-strong)" };
const DOT_LABEL: Record<api.Dot, string> = { ok: "Working", bad: "Needs attention", idle: "Not tested" };
const FIELD =
  "w-full rounded-[6px] border border-rule bg-white px-3 py-2 text-[14px] leading-[18px] text-ink outline-none focus:border-sindoor";

function Logo({ file, size = 28 }: { file: string; size?: number }) {
  return <ProviderLogo kind={file} size={size} />;
}

function message(e: unknown) {
  return problemMessage(e, e instanceof Error && e.message.length < 160 ? e.message : "Something went wrong.");
}

const ROLES = ["classify", "narrate", "synthesise", "report"];

export function EngineSettings() {
  const t = useT();
  const [sample, setSample] = useState(false);
  const [unreachable, setUnreachable] = useState(false);
  const [providers, setProviders] = useState<ProvidersOut | null>(null);
  const [conns, setConns] = useState<AiConnection[]>([]);
  const [routing, setRouting] = useState<AiRouting | null>(null);
  const [tests, setTests] = useState<Record<string, TestResult>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<AiConnection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    try {
      const [p, c, r, smp] = await Promise.all([api.listProviders(), api.listConnections(), api.getRouting(), api.engineIsSample()]);
      setSample(smp);
      setUnreachable(false);
      setProviders(p);
      setConns(c);
      setRouting(r);
      setError(null);
    } catch (e) {
      if (e instanceof TypeError || (e instanceof DOMException && e.name === "AbortError")) setUnreachable(true);
      else setError(message(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const kindOf = (k: string): ProviderKind | undefined => providers?.kinds.find((x) => x.kind === k);

  async function run<T>(key: string, fn: () => Promise<T>): Promise<{ value: T } | undefined> {
    setBusy(key);
    setError(null);
    try {
      return { value: await fn() };
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(null);
    }
  }

  async function onTest(c: AiConnection) {
    const r = await run(`test-${c.id}`, () => api.testConnection(c.id));
    if (r) setTests((t) => ({ ...t, [c.id]: r.value }));
  }

  async function onToggle(c: AiConnection) {
    if (await run(`toggle-${c.id}`, () => api.updateConnection(c.id, { enabled: !c.enabled }))) await load();
  }

  async function doDelete(c: AiConnection) {
    if (await run(`del-${c.id}`, () => api.deleteConnection(c.id))) await load();
  }

  async function onPreset(p: string) {
    const r = await run(`preset-${p}`, () => api.applyPreset(p));
    if (r) setRouting(r.value);
  }

  async function onRoute(role: string, connection_id: string | null, model: string | null) {
    const r = await run(`route-${role}`, () => api.setRouting([{ role, connection_id, model }]));
    if (r) setRouting(r.value);
  }

  if (loading) return <p className="px-6 py-9 text-[16px] text-body lg:px-10">{t("Loading engine settings...")}</p>;
  if (unreachable) {
    return (
      <div className="flex flex-col gap-8 px-6 py-9 lg:px-10">
        <h1 className="m-0 text-[32px] font-bold leading-10 tracking-[-0.02em] text-ink">Engine &amp; models</h1>
        <ServerUnavailable
          onRetry={() => {
            setLoading(true);
            void load();
          }}
        />
      </div>
    );
  }

  const readOnly = sample;
  const roles = routing?.roles?.length ? routing.roles : ROLES;
  const routeFor = (role: string) => routing?.routes.find((r) => r.role === role);

  return (
    <div className="flex flex-col gap-8 px-6 py-9 lg:px-10">
      <header className="flex flex-col gap-1">
        <h1 className="m-0 flex items-center gap-3 text-[32px] font-bold leading-10 tracking-[-0.02em] text-ink">
          Engine &amp; models
          {sample ? <SampleBadge /> : null}
        </h1>
        <p className="m-0 max-w-[640px] text-[16px] leading-6 text-body">
          Choose which AI answers your questions. Connect more than one so a failure never stops a reading: the next
          connection takes over. Every answer is still checked against the chart.
        </p>
      </header>

      {sample ? (
        <Banner tone="info" title={t("Sample connections")}>
          {t("These are examples so you can see how routing works. Start the API to connect your own engines.")}
        </Banner>
      ) : null}
      {error ? <Banner tone="error">{error}</Banner> : null}
      {providers && !providers.secret_key_configured ? (
        <div className="rounded-[6px] bg-wash px-4 py-3 text-[14px] text-accent-text">
          API keys cannot be saved until the server has ANKANA_SECRET_KEY set. Connections that use your own login
          need no key.
        </div>
      ) : null}

      <section aria-labelledby="conns" className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-4">
          <h2 id="conns" className="m-0 text-[20px] font-bold leading-6 text-ink">
            Connections
          </h2>
          <Btn variant="primary" disabled={readOnly} onClick={() => setAdding(true)}>
            Add connection
          </Btn>
        </div>
        {conns.length === 0 ? (
          <Panel className="p-6 text-[15px] leading-6 text-body">
            No connections yet. Add one to start. Without one, the server default is used.
          </Panel>
        ) : (
          <ul className="m-0 grid list-none grid-cols-1 gap-4 p-0 md:grid-cols-2 xl:grid-cols-3">
            {conns.map((c) => {
              const kind = kindOf(c.kind);
              const test = tests[c.id];
              const dot = api.dotFor(c, kind, test);
              return (
                <li key={c.id}>
                  <Panel className="flex h-full flex-col gap-3 p-5" data-testid="connection-card">
                    <div className="flex items-start gap-3">
                      <Logo file={kind?.logo ?? "ankana.svg"} />
                      <div className="min-w-0 flex-1">
                        <p className="m-0 truncate text-[16px] font-bold leading-5 text-ink">{c.label}</p>
                        <p className="m-0 truncate text-[13px] leading-4 text-body">{kind?.label ?? c.kind}</p>
                      </div>
                      <span className="flex items-center gap-[6px] text-[13px] font-bold leading-4 text-body">
                        <span
                          aria-hidden
                          data-testid="status-dot"
                          data-state={dot}
                          className="inline-block h-[9px] w-[9px] rounded-full"
                          style={{ background: DOT[dot] }}
                        />
                        <span>{!c.enabled ? "Off" : !c.allowed ? "Disabled here" : DOT_LABEL[dot]}</span>
                      </span>
                    </div>
                    <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[13px] leading-4">
                      {(["top", "strong", "fast"] as const).map((t) => (
                        <div key={t} className="contents">
                          <dt className="text-soft">{t[0].toUpperCase() + t.slice(1)}</dt>
                          <dd className="m-0 truncate text-ink">{c.effective_models[t] || "CLI default"}</dd>
                        </div>
                      ))}
                    </dl>
                    <div className="flex flex-wrap items-center gap-2">
                      {c.has_key ? <Chip tone="muted">Key saved</Chip> : null}
                      {c.local ? <Chip tone="accent">This computer</Chip> : null}
                    </div>
                    {test ? (
                      <p className="m-0 text-[13px] leading-4" style={{ color: test.ok ? "var(--success)" : "var(--text-primary)" }}>
                        {test.ok
                          ? `Answered in ${test.latency_ms} ms${test.model ? ` with ${test.model}` : ""}.`
                          : test.error}
                      </p>
                    ) : kind && !kind.available ? (
                      <p className="m-0 text-[13px] leading-4 text-body">{kind.detail}</p>
                    ) : null}
                    <div className="mt-auto flex flex-wrap gap-2 pt-1">
                      <Btn variant="outline" disabled={readOnly || busy !== null || !c.allowed} onClick={() => onTest(c)}>
                        {busy === `test-${c.id}` ? "Testing..." : "Test"}
                      </Btn>
                      <Btn variant="outline" disabled={readOnly || busy !== null} onClick={() => onToggle(c)}>
                        {c.enabled ? "Turn off" : "Turn on"}
                      </Btn>
                      <Btn variant="text" disabled={readOnly || busy !== null} onClick={() => setPendingDelete(c)}>
                        Remove
                      </Btn>
                    </div>
                  </Panel>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section aria-labelledby="routing" className="flex flex-col gap-4">
        <h2 id="routing" className="m-0 text-[20px] font-bold leading-6 text-ink">
          Routing
        </h2>
        <div role="group" aria-label="Presets" className="flex flex-wrap gap-3">
          {(routing?.presets ?? []).map((p) => {
            const copy = api.PRESET_COPY[p] ?? { title: p, note: "" };
            const active = routing?.preset === p;
            return (
              <button
                key={p}
                type="button"
                aria-pressed={active}
                disabled={readOnly || busy !== null || conns.length === 0}
                onClick={() => onPreset(p)}
                className="flex w-[220px] flex-col gap-1 rounded-[8px] border p-4 text-left disabled:opacity-50"
                style={{ borderColor: active ? "var(--accent)" : "var(--rule)", background: active ? "var(--surface)" : "#fff" }}
              >
                <span className="text-[15px] font-bold leading-5 text-ink">{copy.title}</span>
                <span className="text-[13px] leading-4 text-body">{copy.note}</span>
              </button>
            );
          })}
        </div>
        <Panel className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-[14px]">
            <thead>
              <tr className="border-b border-rule text-[13px] text-soft">
                <th className="px-5 py-3 font-bold">Job</th>
                <th className="px-5 py-3 font-bold">Connection</th>
                <th className="px-5 py-3 font-bold">Model</th>
              </tr>
            </thead>
            <tbody>
              {roles.map((role) => {
                const r = routeFor(role);
                const copy = api.ROLE_COPY[role] ?? { title: role, note: "" };
                const conn = conns.find((c) => c.id === r?.connection_id);
                return (
                  <tr key={role} className="border-b border-rule last:border-0">
                    <td className="px-5 py-3">
                      <p className="m-0 font-bold text-ink">{copy.title}</p>
                      <p className="m-0 text-[13px] text-body">{copy.note}</p>
                    </td>
                    <td className="px-5 py-3">
                      {conns.length === 0 ? (
                        <span className="text-[14px] font-bold text-ink">{t("Server default")}</span>
                      ) : (
                      <Select
                        aria-label={`${copy.title} connection`}
                        value={r?.connection_id ?? ""}
                        disabled={readOnly || busy !== null}
                        onValueChange={(v) => void onRoute(role, v || null, null)}
                        options={[
                          { value: "", label: "First available" },
                          ...conns.map((c) => ({ value: c.id, label: c.label, icon: <ProviderLogo kind={c.kind} size={16} /> })),
                        ]}
                      />
                      )}
                    </td>
                    <td className="px-5 py-3">
                      {conns.length === 0 ? (
                        <span className="text-[13px] text-soft">{t("Add a connection to choose a model for this job.")}</span>
                      ) : (
                      <input
                        aria-label={`${copy.title} model`}
                        className={FIELD}
                        key={`${role}-${r?.connection_id}-${r?.model}`}
                        defaultValue={r?.model ?? ""}
                        placeholder={conn ? `Auto (${conn.effective_models.strong || "CLI default"})` : "Auto"}
                        disabled={!r?.connection_id}
                        onBlur={(e) => {
                          const v = e.target.value.trim();
                          if (r?.connection_id && v !== (r.model ?? "")) void onRoute(role, r.connection_id, v || null);
                        }}
                      />
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Panel>
        <p className="m-0 text-[13px] leading-5 text-body">
          If a connection fails, the next enabled connection answers. Leave the model empty to match each question to
          the top, strong or fast model of that connection.
        </p>
      </section>

      {providers ? (
        <AddDialog
          open={adding}
          providers={providers}
          onClose={() => setAdding(false)}
          onCreated={async () => {
            setAdding(false);
            await load();
          }}
        />
      ) : null}
      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(o) => !o && setPendingDelete(null)}
        title={`Remove ${pendingDelete?.label ?? "connection"}?`}
        description="Its stored key is deleted."
        confirmLabel="Remove"
        tone="danger"
        onConfirm={async () => {
          if (pendingDelete) await doDelete(pendingDelete);
        }}
      />
    </div>
  );
}

function AddDialog({
  open,
  providers,
  onClose,
  onCreated,
}: {
  open: boolean;
  providers: ProvidersOut;
  onClose: () => void;
  onCreated: () => Promise<void>;
}) {
  const [kind, setKind] = useState<ProviderKind | null>(null);
  const [label, setLabel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [key, setKey] = useState("");
  const [models, setModels] = useState({ top: "", strong: "", fast: "" });
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function pick(k: ProviderKind) {
    setKind(k);
    setLabel(k.label.replace(/ \(this computer\)/, ""));
    setBaseUrl(k.default_base_url ?? "");
    setKey("");
    setModels({ top: "", strong: "", fast: "" });
    setErr(null);
  }

  function close() {
    setKind(null);
    onClose();
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!kind) return;
    setSaving(true);
    setErr(null);
    try {
      await api.createConnection({
        kind: kind.kind,
        label,
        base_url: kind.requires_base_url || baseUrl !== (kind.default_base_url ?? "") ? baseUrl || null : null,
        api_key: key || null,
        models: { top: models.top || null, strong: models.strong || null, fast: models.fast || null },
      });
      setKind(null);
      await onCreated();
    } catch (e2) {
      setErr(message(e2));
    } finally {
      setSaving(false);
    }
  }

  const showUrl = kind && (kind.requires_base_url || kind.kind === "ollama_cloud" || kind.kind === "gemini");
  const showKey = kind && (kind.requires_key || kind.kind === "openai_compatible");

  return (
    <Dialog.Root open={open} onOpenChange={(o) => (!o ? close() : undefined)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-[rgba(34,30,29,0.35)]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[min(640px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-[10px] bg-white p-6">
          <Dialog.Title className="m-0 text-[22px] font-bold leading-7 text-ink">Add connection</Dialog.Title>
          <Dialog.Description className="m-0 mb-4 text-[14px] leading-5 text-body">
            Pick a provider. Local ones use your own login and need no key.
          </Dialog.Description>
          {!kind ? (
            <ul className="m-0 grid list-none grid-cols-1 gap-3 p-0 sm:grid-cols-2">
              {providers.kinds.map((k) => (
                <li key={k.kind}>
                  <button
                    type="button"
                    disabled={!k.allowed}
                    onClick={() => pick(k)}
                    className="flex h-full w-full items-start gap-3 rounded-[8px] border border-rule bg-white p-3 text-left hover:border-sindoor disabled:opacity-50"
                  >
                    <Logo file={k.logo} size={24} />
                    <span className="flex flex-col gap-[2px]">
                      <span className="text-[14px] font-bold leading-[18px] text-ink">{k.label}</span>
                      <span className="text-[12px] leading-4 text-body">
                        {k.allowed ? k.description : "Turned off on this server."}
                      </span>
                      {k.allowed && k.local ? (
                        <span
                          className="text-[12px] font-bold leading-4"
                          style={{ color: k.available ? "var(--success)" : "var(--warning)" }}
                        >
                          {k.available ? "Found on this computer" : k.detail}
                        </span>
                      ) : null}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <form onSubmit={submit} className="flex flex-col gap-4">
              <div className="flex items-center gap-3">
                <Logo file={kind.logo} />
                <div>
                  <p className="m-0 text-[16px] font-bold text-ink">{kind.label}</p>
                  <button
                    type="button"
                    className="m-0 border-0 bg-transparent p-0 text-[13px] text-accent-text"
                    onClick={() => setKind(null)}
                  >
                    Choose another provider
                  </button>
                </div>
              </div>
              <label className="flex flex-col gap-1 text-[13px] font-bold text-ink">
                Name
                <input className={FIELD} value={label} onChange={(e) => setLabel(e.target.value)} required maxLength={120} />
              </label>
              {showUrl ? (
                <label className="flex flex-col gap-1 text-[13px] font-bold text-ink">
                  Base URL
                  <input
                    className={FIELD}
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    required={kind.requires_base_url}
                  />
                </label>
              ) : null}
              {showKey ? (
                <label className="flex flex-col gap-1 text-[13px] font-bold text-ink">
                  API key {kind.requires_key ? "" : "(optional)"}
                  <input
                    className={FIELD}
                    type="password"
                    autoComplete="off"
                    value={key}
                    onChange={(e) => setKey(e.target.value)}
                    required={kind.requires_key}
                  />
                  <span className="text-[12px] font-normal text-body">Stored encrypted and never shown again.</span>
                </label>
              ) : null}
              <fieldset className="m-0 grid grid-cols-1 gap-3 border-0 p-0 sm:grid-cols-3">
                <legend className="mb-1 p-0 text-[13px] font-bold text-ink">Models (leave empty for the defaults)</legend>
                {(["top", "strong", "fast"] as const).map((t) => (
                  <label key={t} className="flex flex-col gap-1 text-[12px] text-body">
                    {t[0].toUpperCase() + t.slice(1)}
                    <input
                      className={FIELD}
                      value={models[t]}
                      placeholder={kind.default_models[t] || "CLI default"}
                      onChange={(e) => setModels((m) => ({ ...m, [t]: e.target.value }))}
                    />
                  </label>
                ))}
              </fieldset>
              {err ? (
                <p role="alert" className="m-0 text-[14px] font-bold text-alert">
                  {err}
                </p>
              ) : null}
              <div className="flex justify-end gap-2">
                <Btn variant="outline" type="button" onClick={close}>
                  Cancel
                </Btn>
                <Btn variant="primary" type="submit" disabled={saving}>
                  {saving ? "Saving..." : "Add connection"}
                </Btn>
              </div>
            </form>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
