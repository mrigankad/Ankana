"use client"

import * as React from "react"
import { Progress as ProgressPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Check } from "@/components/ui/field"

/* ---------- Table ---------- */

export function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div className="overflow-x-auto rounded-[10px] border border-rule bg-white">
      <table className={cn("w-full border-collapse text-left text-[14px] text-ink", className)} {...props} />
    </div>
  )
}
export const TableHead = (p: React.ComponentProps<"thead">) => <thead className="bg-sidebar-wash" {...p} />
export const TableBody = (p: React.ComponentProps<"tbody">) => <tbody {...p} />
export function TableRow({ className, selected, ...props }: React.ComponentProps<"tr"> & { selected?: boolean }) {
  return <tr data-selected={selected || undefined} className={cn("border-t border-rule first:border-t-0 data-[selected]:bg-accent-wash", className)} {...props} />
}
export function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return <td className={cn("px-4 py-3 align-middle", className)} {...props} />
}

/** Sortable header cell. Renders a button inside th with aria-sort. */
export function TableHeaderCell({
  className,
  sortDirection,
  onSort,
  children,
  ...props
}: React.ComponentProps<"th"> & { sortDirection?: "asc" | "desc" | null; onSort?: () => void }) {
  return (
    <th
      scope="col"
      aria-sort={onSort ? (sortDirection === "asc" ? "ascending" : sortDirection === "desc" ? "descending" : "none") : undefined}
      className={cn("px-4 py-2.5 text-[12px] font-bold text-body", className)}
      {...props}
    >
      {onSort ? (
        <button type="button" onClick={onSort} className="inline-flex items-center gap-1 rounded outline-none hover:text-ink focus-visible:ring-[3px] focus-visible:ring-sindoor/30">
          {children}
          <svg aria-hidden width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={cn(!sortDirection && "opacity-40", sortDirection === "desc" && "rotate-180")}>
            <path d="M3 7l3-3 3 3" />
          </svg>
        </button>
      ) : (
        children
      )}
    </th>
  )
}

/** Skeleton rows for a table in loading state. */
export function TableSkeletonRows({ rows = 3, cols }: { rows?: number; cols: number }) {
  return (
    <>
      {Array.from({ length: rows }, (_, r) => (
        <tr key={r} className="border-t border-rule" aria-hidden>
          {Array.from({ length: cols }, (_, c) => (
            <td key={c} className="px-4 py-3.5">
              <div className="h-3.5 animate-pulse rounded-md bg-rule motion-reduce:animate-none" style={{ width: `${60 + ((r + c) % 3) * 15}%` }} />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}

/* ---------- Pagination (cursor) ---------- */

/** Cursor pagination: a single Load more button. Hide with hasMore=false. */
export function LoadMore({ hasMore, loading, onLoadMore, className }: { hasMore: boolean; loading?: boolean; onLoadMore: () => void; className?: string }) {
  if (!hasMore) return null
  return (
    <div className={cn("flex justify-center py-3", className)}>
      <Button type="button" variant="outline" size="md" loading={loading} onClick={onLoadMore}>
        Load more
      </Button>
    </div>
  )
}

/* ---------- Empty state ---------- */

export function EmptyState({
  title,
  description,
  illustration,
  action,
  className,
}: {
  title: React.ReactNode
  description?: React.ReactNode
  /** Clay illustration (img/svg). Pass a decorative node; it is aria-hidden. */
  illustration?: React.ReactNode
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex flex-col items-center gap-3 px-6 py-10 text-center", className)}>
      {illustration ? <div aria-hidden className="mb-1">{illustration}</div> : null}
      <p className="m-0 text-[16px] font-bold text-ink">{title}</p>
      {description ? <p className="m-0 max-w-[360px] text-[14px] leading-5 text-body">{description}</p> : null}
      {action}
    </div>
  )
}

/* ---------- Progress, Stepper ---------- */

export function Progress({ value, className, ...props }: React.ComponentProps<typeof ProgressPrimitive.Root> & { value: number }) {
  return (
    <ProgressPrimitive.Root value={value} className={cn("h-1.5 overflow-hidden rounded-full bg-rule", className)} {...props}>
      <ProgressPrimitive.Indicator
        className="h-full rounded-full bg-(image:--fill-accent) transition-[width] motion-reduce:transition-none"
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </ProgressPrimitive.Root>
  )
}

export function Stepper({ steps, current, className }: { steps: string[]; current: number; className?: string }) {
  return (
    <ol className={cn("m-0 flex list-none items-center gap-2 p-0", className)} aria-label="Progress">
      {steps.map((s, i) => {
        const done = i < current
        const active = i === current
        return (
          <React.Fragment key={s}>
            <li aria-current={active ? "step" : undefined} className="flex items-center gap-2">
              <span className={cn("flex size-[26px] items-center justify-center rounded-full text-[12px] font-bold", done && "bg-(image:--fill-primary) text-white", active && "border-2 border-sindoor text-accent-text", !done && !active && "bg-sidebar-wash text-soft")}>
                {done ? <Check className="size-3.5" /> : i + 1}
              </span>
              <span className={cn("text-[13px] font-bold", active ? "text-ink" : "text-body")}>{s}</span>
            </li>
            {i < steps.length - 1 ? <span aria-hidden className={cn("h-0.5 min-w-6 flex-1 rounded", done ? "bg-sindoor" : "bg-rule")} /> : null}
          </React.Fragment>
        )
      })}
    </ol>
  )
}

/* ---------- Banner, Breadcrumb, StatusDot, FileDrop ---------- */

const BANNER = {
  info: "border-rule bg-sidebar-wash",
  warning: "border-accent-line bg-accent-wash",
  success: "border-ok-line bg-ok-wash",
  error: "border-alert-line bg-alert-wash",
} as const
const DOT = { info: "bg-body", warning: "bg-sindoor", success: "bg-ok", error: "bg-alert" } as const

export function Banner({ tone = "info", title, children, action, className }: { tone?: keyof typeof BANNER; title?: React.ReactNode; children?: React.ReactNode; action?: React.ReactNode; className?: string }) {
  return (
    <div role={tone === "error" ? "alert" : "status"} className={cn("flex items-start gap-2.5 rounded-xl border px-3.5 py-3 text-[13px] leading-5 text-ink", BANNER[tone], className)}>
      <span aria-hidden className={cn("mt-1.5 size-2 shrink-0 rounded-full", DOT[tone])} />
      <div className="min-w-0 flex-1">
        {title ? <p className="m-0 font-bold">{title}</p> : null}
        {children ? <div className={cn(title && "text-body")}>{children}</div> : null}
      </div>
      {action}
    </div>
  )
}

export function Breadcrumb({ items }: { items: { label: string; href?: string }[] }) {
  return (
    <nav aria-label="Breadcrumb">
      <ol className="m-0 flex list-none items-center gap-2 p-0 text-[13px] font-semibold text-body">
        {items.map((it, i) => (
          <li key={it.label} className="flex items-center gap-2">
            {it.href && i < items.length - 1 ? (
              <a href={it.href} className="rounded outline-none hover:text-ink focus-visible:ring-[3px] focus-visible:ring-sindoor/30">{it.label}</a>
            ) : (
              <span aria-current={i === items.length - 1 ? "page" : undefined} className={i === items.length - 1 ? "text-ink" : undefined}>{it.label}</span>
            )}
            {i < items.length - 1 ? <span aria-hidden className="text-soft">/</span> : null}
          </li>
        ))}
      </ol>
    </nav>
  )
}

export function StatusDot({ tone = "ok", children, className }: { tone?: "ok" | "alert" | "accent" | "muted"; children?: React.ReactNode; className?: string }) {
  const c = { ok: "bg-ok", alert: "bg-alert", accent: "bg-sindoor", muted: "bg-soft" }[tone]
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-[12px] font-bold text-body", className)}>
      <span aria-hidden className={cn("size-2 rounded-full", c)} />
      {children}
    </span>
  )
}

/** Drag-and-drop or click-to-choose file area (logo upload). The file input is visually hidden but real. */
export function FileDrop({
  onFile,
  accept = "image/png,image/svg+xml,image/jpeg",
  maxBytes = 2 * 1024 * 1024,
  title = "Drop your logo here",
  hint = "PNG, SVG or JPG, up to 2 MB",
  disabled,
  className,
}: {
  onFile: (file: File) => void
  accept?: string
  maxBytes?: number
  title?: string
  hint?: string
  disabled?: boolean
  className?: string
}) {
  const [over, setOver] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const input = React.useRef<HTMLInputElement>(null)
  function take(f: File | undefined) {
    if (!f) return
    if (f.size > maxBytes) return setError(`File is larger than ${Math.round(maxBytes / 1024 / 1024)} MB`)
    if (accept && !accept.split(",").some((a) => f.type === a.trim())) return setError("That file type is not supported")
    setError(null)
    onFile(f)
  }
  return (
    <div className={className}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setOver(false)
          take(e.dataTransfer.files[0])
        }}
        className={cn("flex w-full flex-col items-center gap-1 rounded-[10px] border-[1.5px] border-dashed border-rule-strong bg-sidebar-wash px-5 py-5 outline-none transition-colors hover:border-sindoor focus-visible:border-sindoor focus-visible:ring-[3px] focus-visible:ring-sindoor/20 disabled:opacity-50", over && "border-sindoor bg-accent-wash")}
      >
        <span className="text-[14px] font-bold text-ink">{title}</span>
        <span className="text-[12px] text-body">{hint}</span>
      </button>
      <input ref={input} type="file" accept={accept} tabIndex={-1} aria-label={title} className="sr-only" onChange={(e) => take(e.target.files?.[0])} />
      {error ? <p role="alert" className="m-0 pt-1.5 text-[12px] text-alert">{error}</p> : null}
    </div>
  )
}
