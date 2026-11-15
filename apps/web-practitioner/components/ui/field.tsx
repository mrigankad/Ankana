import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Shared surface for every text-like control (Input, Select trigger, Combobox, DateField...).
 * 42px, radius 10, accent focus ring. Invalid state is driven by aria-invalid or data-invalid.
 */
export const FIELD_CLASS =
  "h-[42px] w-full min-w-0 rounded-[6px] border border-rule bg-white px-3.5 text-[14px] leading-[18px] text-ink outline-none transition-[box-shadow,border-color] placeholder:text-soft hover:border-rule-strong focus-visible:border-sindoor focus-visible:ring-[3px] focus-visible:ring-sindoor/20 aria-invalid:border-alert aria-invalid:ring-alert/15 data-[invalid=true]:border-alert disabled:cursor-not-allowed disabled:bg-sidebar-wash disabled:text-soft data-[state=open]:border-sindoor data-[state=open]:ring-[3px] data-[state=open]:ring-sindoor/20"

/** Floating surface for Select, Combobox, Popover and menus. */
export const POPUP_CLASS =
  "z-50 rounded-[10px] border border-rule bg-white p-1.5 text-ink shadow-[var(--shadow-popup)] outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 motion-reduce:animate-none"

/** Option row used by Select, Combobox and MultiSelect. */
export const OPTION_CLASS =
  "relative flex w-full cursor-pointer select-none items-center gap-2.5 rounded-lg px-2.5 py-2 text-[14px] outline-none data-[highlighted]:bg-sidebar-wash data-[selected=true]:bg-sidebar-wash data-[state=checked]:bg-accent-wash data-[disabled]:pointer-events-none data-[disabled]:text-soft data-[disabled=true]:pointer-events-none data-[disabled=true]:text-soft"

export function Chevron({ open, className }: { open?: boolean; className?: string }) {
  return (
    <svg
      aria-hidden
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("shrink-0 text-body transition-transform motion-reduce:transition-none", open && "rotate-180", className)}
    >
      <path d="M4 6l4 4 4-4" />
    </svg>
  )
}

export function Check({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("shrink-0", className)}
    >
      <path d="M3 8.5l3.5 3.5L13 4.5" />
    </svg>
  )
}

/** Visible label above a control. Pair with htmlFor. */
export function Label({ className, ...props }: React.ComponentProps<"label">) {
  return <label className={cn("text-[13px] font-bold leading-4 text-ink", className)} {...props} />
}

/** Helper or error line under a control. Use tone="error" with role=alert semantics. */
export function FieldMessage({
  tone = "hint",
  className,
  ...props
}: React.ComponentProps<"p"> & { tone?: "hint" | "error" }) {
  return (
    <p
      role={tone === "error" ? "alert" : undefined}
      className={cn("m-0 text-[12px] leading-4", tone === "error" ? "text-alert" : "text-body", className)}
      {...props}
    />
  )
}

/** Label + control + message stack. */
export function Field({
  label,
  htmlFor,
  hint,
  error,
  className,
  children,
}: {
  label?: React.ReactNode
  htmlFor?: string
  hint?: React.ReactNode
  error?: React.ReactNode
  className?: string
  children: React.ReactNode
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {label ? <Label htmlFor={htmlFor}>{label}</Label> : null}
      {children}
      {error ? <FieldMessage tone="error">{error}</FieldMessage> : hint ? <FieldMessage>{hint}</FieldMessage> : null}
    </div>
  )
}
