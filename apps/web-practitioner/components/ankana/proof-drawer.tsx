"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import type { ProofView } from "@/lib/api/depth-views";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

const ProofContext = createContext<{ open: (p: ProofView) => void }>({ open: () => undefined });

export const useProof = () => useContext(ProofContext);

/** One drawer per tab: any number on the tab opens it with how that number was derived. */
export function ProofProvider({ children }: { children: ReactNode }) {
  const t = useT();
  const [proof, setProof] = useState<ProofView | null>(null);
  const [isOpen, setOpen] = useState(false);
  const open = useCallback((p: ProofView) => {
    setProof(p);
    setOpen(true);
  }, []);
  const value = useMemo(() => ({ open }), [open]);

  return (
    <ProofContext.Provider value={value}>
      {children}
      <Sheet open={isOpen} onOpenChange={setOpen}>
        <SheetContent
          side="right"
          className="w-full gap-0 overflow-y-auto border-rule bg-surface p-0 data-[side=right]:w-full data-[side=right]:sm:max-w-[440px]"
          data-testid="proof-drawer"
        >
          {proof ? (
            <>
              <SheetHeader className="gap-1 border-b border-rule px-5 pb-4 pt-5">
                <div className="text-[12px] font-bold uppercase leading-4 tracking-[0.06em] text-accent-text">{t("How this was worked out")}</div>
                <SheetTitle className="pr-8 text-[18px] font-bold leading-6 text-ink">{proof.title}</SheetTitle>
                <SheetDescription className="text-[26px] font-bold leading-8 tracking-[-0.01em] text-ink">{proof.value}</SheetDescription>
              </SheetHeader>
              <div className="flex flex-col gap-5 px-5 py-5">
                <section aria-label={t("Inputs")} className="flex flex-col gap-2">
                  <h3 className="m-0 text-[13px] font-bold leading-4 text-ink">{t("Inputs")}</h3>
                  <dl className="m-0 flex flex-col overflow-hidden rounded-[6px] border border-rule">
                    {proof.inputs.map((row, i) => (
                      <div key={i} className={cn("flex items-baseline justify-between gap-4 px-3 py-[9px]", i > 0 && "border-t border-rule")}>
                        <dt className="text-[13px] leading-[18px] text-body">{row.label}</dt>
                        <dd className="m-0 text-right text-[13px] font-bold leading-[18px] text-ink">{row.value}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
                <section aria-label={t("Rule")} className="flex flex-col gap-2">
                  <h3 className="m-0 text-[13px] font-bold leading-4 text-ink">{t("Rule")}</h3>
                  <p className="m-0 text-[14px] leading-[21px] text-body">{proof.rule}</p>
                </section>
                <section aria-label={t("Source")} className="flex flex-col gap-2 rounded-[6px] bg-wash-soft px-3 py-[10px]">
                  <h3 className="m-0 text-[13px] font-bold leading-4 text-ink">{t("Source")}</h3>
                  <p className="m-0 text-[13px] leading-[18px] text-body">{proof.source}</p>
                </section>
              </div>
            </>
          ) : null}
        </SheetContent>
      </Sheet>
    </ProofContext.Provider>
  );
}

/** A number or word on a tab that opens its proof. Dotted underline marks it as inspectable. */
export function ProofValue({
  proof,
  children,
  className,
  title,
}: {
  proof: ProofView;
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  const { open } = useProof();
  const t = useT();
  return (
    <button
      type="button"
      onClick={() => open(proof)}
      title={title ?? t("Show how this was worked out")}
      className={cn(
        "cursor-pointer rounded-[4px] border-0 bg-transparent p-0 text-left font-[inherit] text-inherit underline decoration-rule-strong decoration-dotted underline-offset-[3px] outline-none transition-colors hover:text-accent-text hover:decoration-sindoor focus-visible:ring-[3px] focus-visible:ring-hl/30 motion-reduce:transition-none",
        className,
      )}
    >
      {children}
    </button>
  );
}
