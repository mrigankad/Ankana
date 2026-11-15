"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";

import { ProofProvider } from "@/components/ankana/proof-drawer";
import { ServerUnavailable } from "@/components/ankana/server-unavailable";
import { Skeleton } from "@/components/ui/skeleton";

/** Load a depth view once per key; a failed load shows the calm unavailable state with Retry. */
export function useDepthData<T>(load: () => Promise<T>, key: string): { data: T | null; failed: boolean; retry: () => void } {
  const [state, setState] = useState<{ key: string; data: T | null; failed: boolean }>({ key, data: null, failed: false });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let cancelled = false;
    load()
      .then((data) => !cancelled && setState({ key, data, failed: false }))
      .catch(() => !cancelled && setState({ key, data: null, failed: true }));
    return () => {
      cancelled = true;
    };
    // `load` is a fresh closure each render; the key and attempt describe what to load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt]);
  const retry = useCallback(() => {
    setState({ key, data: null, failed: false });
    setAttempt((n) => n + 1);
  }, [key]);
  const current = state.key === key ? state : { key, data: null, failed: false };
  return { data: current.data, failed: current.failed, retry };
}

/** Wraps a depth view in its proof drawer. `bare` skips the page padding when the host already has it. */
export function DepthBody({ children, bare }: { children: ReactNode; bare?: boolean }) {
  return (
    <ProofProvider>
      <div className={bare ? "flex min-w-0 flex-col gap-4" : "flex min-w-0 flex-col gap-5 px-4 py-[22px] sm:px-8"}>{children}</div>
    </ProofProvider>
  );
}

export function DepthLoading({ rows = 3 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-3" aria-busy="true">
      <Skeleton className="h-8 w-56" />
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-14 w-full" />
      ))}
    </div>
  );
}

export function DepthFailed({ onRetry }: { onRetry: () => void }) {
  return <ServerUnavailable title="This view could not be loaded" description="The chart is fine. Try again in a moment." onRetry={onRetry} />;
}
