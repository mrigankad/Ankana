import type { ReactNode } from "react";

/** Standard page title block: 32px title, one-line subtitle, optional badge and actions. */
export function PageHeader({ title, subtitle, badge, actions }: { title: string; subtitle?: string; badge?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="flex min-w-0 flex-col gap-1">
        <h1 className="m-0 flex items-center gap-3 text-[28px] font-bold leading-9 tracking-[-0.02em] text-ink lg:text-[32px] lg:leading-10">
          {title}
          {badge}
        </h1>
        {subtitle ? <p className="m-0 max-w-[640px] text-[16px] leading-6 text-body">{subtitle}</p> : null}
      </div>
      {actions}
    </header>
  );
}
