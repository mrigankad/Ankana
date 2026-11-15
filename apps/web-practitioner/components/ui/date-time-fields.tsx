"use client"

import * as React from "react"

import { cn } from "@/lib/utils"
import { FIELD_CLASS } from "@/components/ui/field"
import { SegmentedControl } from "@/components/ui/controls"

const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
const digits = (s: string, max: number) => s.replace(/\D/g, "").slice(0, max)
const pad = (n: number, w = 2) => String(n).padStart(w, "0")

/** "YYYY-MM-DD" to parts, or null when not a real calendar date. */
export function parseIsoDate(iso: string): { d: number; m: number; y: number } | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  if (!m) return null
  return validDate(Number(m[3]), Number(m[2]), Number(m[1]))
}

function validDate(d: number, m: number, y: number) {
  if (y < 1 || m < 1 || m > 12 || d < 1) return null
  const dt = new Date(Date.UTC(y, m - 1, d))
  if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== m - 1 || dt.getUTCDate() !== d) return null
  return { d, m, y }
}

interface SegProps {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder: string
  width: string
  maxLen: number
  refEl: (el: HTMLInputElement | null) => void
  onFull: () => void
  onBack: () => void
  disabled?: boolean
  invalid?: boolean
}

function Segment({ label, value, onChange, placeholder, width, maxLen, refEl, onFull, onBack, disabled, invalid }: SegProps) {
  return (
    <input
      ref={refEl}
      aria-label={label}
      aria-invalid={invalid || undefined}
      inputMode="numeric"
      autoComplete="off"
      disabled={disabled}
      value={value}
      placeholder={placeholder}
      onChange={(e) => {
        const v = digits(e.target.value, maxLen)
        onChange(v)
        if (v.length === maxLen) onFull()
      }}
      onKeyDown={(e) => {
        if (e.key === "Backspace" && value === "") onBack()
      }}
      onFocus={(e) => e.currentTarget.select()}
      className={cn("bg-transparent p-0 text-center text-[14px] font-bold leading-[18px] text-ink outline-none placeholder:font-normal placeholder:text-soft disabled:text-soft", width)}
    />
  )
}

const WRAP = "flex items-center gap-1.5 focus-within:border-sindoor focus-within:ring-[3px] focus-within:ring-sindoor/20"

export interface DateFieldProps {
  /** ISO date "YYYY-MM-DD", or "" when empty or incomplete. */
  value: string
  onChange: (iso: string) => void
  id?: string
  disabled?: boolean
  /** Show the weekday for a valid date (default true). */
  showWeekday?: boolean
  /** Reject dates after this ISO date (inclusive max). */
  max?: string
  min?: string
  className?: string
  "aria-label"?: string
  /** Called with an error message (or null) as the typed value changes. */
  onErrorChange?: (error: string | null) => void
}

/**
 * Typed date: DD MM YYYY, auto-advancing, with a weekday echo ("Saturday") as a typo check.
 * There is deliberately no native date picker. Emits an ISO string only for a real date.
 */
export function DateField({ value, onChange, id, disabled, showWeekday = true, max, min, className, onErrorChange, ...aria }: DateFieldProps) {
  const init = parseIsoDate(value)
  const [dd, setDd] = React.useState(init ? pad(init.d) : "")
  const [mm, setMm] = React.useState(init ? pad(init.m) : "")
  const [yyyy, setYyyy] = React.useState(init ? pad(init.y, 4) : "")
  const refs = React.useRef<(HTMLInputElement | null)[]>([])

  // Adopt external changes without clobbering partial typing.
  React.useEffect(() => {
    const p = parseIsoDate(value)
    if (p) {
      setDd(pad(p.d))
      setMm(pad(p.m))
      setYyyy(pad(p.y, 4))
    } else if (value === "" && dd.length === 2 && mm.length === 2 && yyyy.length === 4 && validDate(+dd, +mm, +yyyy)) {
      setDd("")
      setMm("")
      setYyyy("")
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])

  const complete = dd.length > 0 && mm.length > 0 && yyyy.length === 4
  const parsed = complete ? validDate(+dd, +mm, +yyyy) : null
  const iso = parsed ? `${pad(parsed.y, 4)}-${pad(parsed.m)}-${pad(parsed.d)}` : ""
  let error: string | null = null
  if (complete && !parsed) error = "That date does not exist"
  else if (iso && max && iso > max) error = "Date is in the future"
  else if (iso && min && iso < min) error = "Date is too early"

  const last = React.useRef(value)
  React.useEffect(() => {
    const out = error ? "" : iso
    if (out !== last.current) {
      last.current = out
      onChange(out)
    }
    onErrorChange?.(error)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [iso, error])

  const weekday = parsed && !error ? WEEKDAYS[new Date(Date.UTC(parsed.y, parsed.m - 1, parsed.d)).getUTCDay()] : null
  const focus = (i: number) => refs.current[i]?.focus()
  const common = { disabled, invalid: Boolean(error) }

  return (
    <div
      id={id}
      role="group"
      aria-label={aria["aria-label"] ?? "Date"}
      data-invalid={error ? "true" : undefined}
      className={cn(FIELD_CLASS, WRAP, disabled && "bg-sidebar-wash", className)}
    >
      <Segment {...common} label="Day" value={dd} onChange={setDd} placeholder="DD" width="w-7" maxLen={2} refEl={(el) => (refs.current[0] = el)} onFull={() => focus(1)} onBack={() => {}} />
      <span aria-hidden className="text-soft">/</span>
      <Segment {...common} label="Month" value={mm} onChange={setMm} placeholder="MM" width="w-7" maxLen={2} refEl={(el) => (refs.current[1] = el)} onFull={() => focus(2)} onBack={() => focus(0)} />
      <span aria-hidden className="text-soft">/</span>
      <Segment {...common} label="Year" value={yyyy} onChange={setYyyy} placeholder="YYYY" width="w-11" maxLen={4} refEl={(el) => (refs.current[2] = el)} onFull={() => {}} onBack={() => focus(1)} />
      <span aria-live="polite" className={cn("ml-auto text-[12px] font-bold", error ? "text-alert" : "text-accent-text")}>
        {error ?? weekday ?? ""}
      </span>
    </div>
  )
}

export interface TimeFieldProps {
  /** 24-hour "HH:MM", or "" when incomplete. */
  value: string
  onChange: (hhmm: string) => void
  id?: string
  disabled?: boolean
  className?: string
  "aria-label"?: string
}

/** Typed time: HH MM with an AM/PM segmented control. Emits 24-hour "HH:MM". No native time picker. */
export function TimeField({ value, onChange, id, disabled, className, ...aria }: TimeFieldProps) {
  const m = /^(\d{2}):(\d{2})$/.exec(value)
  const h24 = m ? Number(m[1]) : null
  const [hh, setHh] = React.useState(m ? pad(h24 === 0 || h24 === 12 ? 12 : (h24 as number) % 12) : "")
  const [mi, setMi] = React.useState(m ? m[2] : "")
  const [ap, setAp] = React.useState<"AM" | "PM">(h24 !== null && h24 >= 12 ? "PM" : "AM")
  const refs = React.useRef<(HTMLInputElement | null)[]>([])

  React.useEffect(() => {
    const x = /^(\d{2}):(\d{2})$/.exec(value)
    if (x) {
      const h = Number(x[1])
      setHh(pad(h === 0 || h === 12 ? 12 : h % 12))
      setMi(x[2])
      setAp(h >= 12 ? "PM" : "AM")
    }
  }, [value])

  const hNum = Number(hh)
  const mNum = Number(mi)
  const valid = hh.length > 0 && mi.length === 2 && hNum >= 1 && hNum <= 12 && mNum <= 59
  const error = (hh.length > 0 && (hNum < 1 || hNum > 12)) || (mi.length === 2 && mNum > 59)
  const out = valid ? `${pad((hNum % 12) + (ap === "PM" ? 12 : 0))}:${pad(mNum)}` : ""
  const last = React.useRef(value)
  React.useEffect(() => {
    if (out !== last.current) {
      last.current = out
      onChange(out)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [out])

  return (
    <div id={id} role="group" aria-label={aria["aria-label"] ?? "Time"} data-invalid={error ? "true" : undefined} className={cn(FIELD_CLASS, WRAP, className)}>
      <Segment label="Hour" value={hh} onChange={setHh} placeholder="HH" width="w-7" maxLen={2} disabled={disabled} invalid={error} refEl={(el) => (refs.current[0] = el)} onFull={() => refs.current[1]?.focus()} onBack={() => {}} />
      <span aria-hidden className="text-soft">:</span>
      <Segment label="Minute" value={mi} onChange={setMi} placeholder="MM" width="w-7" maxLen={2} disabled={disabled} invalid={error} refEl={(el) => (refs.current[1] = el)} onFull={() => {}} onBack={() => refs.current[0]?.focus()} />
      <SegmentedControl
        size="sm"
        aria-label="AM or PM"
        className="ml-auto"
        disabled={disabled}
        value={ap}
        onValueChange={setAp}
        options={[
          { value: "AM", label: "AM" },
          { value: "PM", label: "PM" },
        ]}
      />
    </div>
  )
}
