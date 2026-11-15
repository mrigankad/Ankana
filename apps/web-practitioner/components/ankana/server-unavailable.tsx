"use client";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/data";
import { Panel } from "@/components/ankana/ui";
import { useT } from "@/lib/i18n/provider";

/**
 * One calm state for every "the API is not reachable" case: clay astrolabe, one helpful sentence, Retry.
 * Pages that can show sample content in fixtures mode should do that instead and only fall back to this in live mode.
 */
export function ServerUnavailable({
  title = "Ankana cannot reach its server",
  description = "Start the API, or switch to sample data.",
  onRetry,
  bare,
  className,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  /** Render without the surrounding card (use inside an existing panel). */
  bare?: boolean;
  className?: string;
}) {
  const t = useT();
  const body = (
    <EmptyState
      className={className}
      illustration={
        // eslint-disable-next-line @next/next/no-img-element
        <img src="/illustrations/illus-astrolabe@2x.png" alt="" width={132} height={132} className="size-[132px] object-contain" />
      }
      title={t(title)}
      description={t(description)}
      action={
        onRetry ? (
          <Button variant="outline" size="md" onClick={onRetry}>
            {t("Retry")}
          </Button>
        ) : undefined
      }
    />
  );
  return bare ? body : <Panel className="mx-auto w-full max-w-[560px]">{body}</Panel>;
}

/** Small honest label for content that comes from the built-in sample data. */
export function SampleBadge({ className }: { className?: string }) {
  const t = useT();
  return (
    <span className={`inline-flex items-center rounded-full bg-wash px-[10px] py-1 text-[12px] font-bold leading-[14px] text-accent-text ${className ?? ""}`}>
      {t("Sample")}
    </span>
  );
}
