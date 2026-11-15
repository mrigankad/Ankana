"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { TagChip } from "@/components/ankana/ui";
import { Combobox } from "@/components/ui/combobox";
import { v1Api } from "@/lib/api/live";
import { problemMessage } from "@/lib/api/v1";
import { useT } from "@/lib/i18n/provider";

const PRESETS = ["Lal Kitab", "Matching", "Rectify"];

/** A client's own tags: removable chips plus a searchable "Add tag" list that can also create a new tag. */
export function ClientTags({ clientId, initial, onChange }: { clientId: string; initial?: string[]; onChange?: (tags: string[]) => void }) {
  const t = useT();
  const [tags, setTags] = useState<string[]>(initial ?? []);
  const [known, setKnown] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    v1Api
      .getClientTags(clientId)
      .then((x) => !cancelled && setTags(x))
      .catch(() => undefined);
    v1Api
      .listClientTagCounts()
      .then((x) => !cancelled && setKnown(x.map((y) => y.tag)))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [clientId]);

  const save = useCallback(
    async (next: string[]) => {
      setBusy(true);
      setError("");
      try {
        const saved = await v1Api.setClientTags(clientId, next);
        setTags(saved);
        onChange?.(saved);
      } catch (cause) {
        setError(problemMessage(cause));
      } finally {
        setBusy(false);
      }
    },
    [clientId, onChange],
  );

  const options = useMemo(() => {
    const have = new Set(tags.map((x) => x.toLowerCase()));
    const all = [...new Set([...PRESETS, ...known])];
    return all.filter((x) => !have.has(x.toLowerCase())).map((x) => ({ value: x, label: t(x) }));
  }, [tags, known, t]);

  return (
    <div className="flex flex-wrap items-center gap-2" aria-label={t("Tags")} role="group">
      {tags.map((tag) => (
        <span key={tag} className="inline-flex items-center gap-1">
          <TagChip tag={tag} />
          <button
            type="button"
            aria-label={t("Remove tag {tag}", { tag })}
            disabled={busy}
            onClick={() => void save(tags.filter((x) => x !== tag))}
            className="flex size-5 items-center justify-center rounded-full text-soft outline-none hover:bg-chip hover:text-ink focus-visible:ring-2 focus-visible:ring-sindoor/40 disabled:opacity-50"
          >
            <svg aria-hidden width="10" height="10" viewBox="0 0 10 10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
              <path d="M2 2l6 6M8 2L2 8" />
            </svg>
          </button>
        </span>
      ))}
      <Combobox
        aria-label={t("Add tag")}
        className="h-[30px] min-h-0 w-[150px] py-0 text-[13px]"
        value={null}
        disabled={busy || tags.length >= 20}
        placeholder={t("Add tag")}
        searchPlaceholder={t("Find or create a tag")}
        emptyText={t("Type a name to create a tag")}
        options={options}
        onChange={(v) => {
          if (v && !tags.some((x) => x.toLowerCase() === v.toLowerCase())) void save([...tags, v]);
        }}
        onCreate={(q) => {
          const name = q.trim().replace(/\s+/g, " ").slice(0, 40);
          return name ? { value: name, label: name } : undefined;
        }}
      />
      {error ? (
        <span role="alert" className="text-[13px] font-bold leading-4 text-alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}
