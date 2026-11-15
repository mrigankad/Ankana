"use client"

import * as React from "react"
import { Command as CommandPrimitive } from "cmdk"

import { cn } from "@/lib/utils"
import { Check, Chevron, FIELD_CLASS, OPTION_CLASS } from "@/components/ui/field"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"

export interface ComboboxOption {
  value: string
  label: string
  description?: string
  icon?: React.ReactNode
  disabled?: boolean
}

export interface ComboboxProps {
  /** Selected option value, or null. */
  value: string | null
  onChange: (value: string | null, option: ComboboxOption | null) => void
  /** Static options, filtered locally. Ignored when loadOptions is set. */
  options?: ComboboxOption[]
  /** Async search (places, clients). Called debounced with the query; abort signal cancels stale calls. */
  loadOptions?: (query: string, signal: AbortSignal) => Promise<ComboboxOption[]>
  /** When set, a "Create ..." row is offered for a query with no exact match. Return the created option to select it. */
  onCreate?: (query: string) => ComboboxOption | void | Promise<ComboboxOption | void>
  /** Label for the current value when it is not in options (async lookups). */
  selectedOption?: ComboboxOption | null
  placeholder?: string
  searchPlaceholder?: string
  emptyText?: string
  id?: string
  disabled?: boolean
  invalid?: boolean
  clearable?: boolean
  className?: string
  "aria-label"?: string
  "aria-labelledby"?: string
}

function useAsyncOptions(open: boolean, query: string, loadOptions: ComboboxProps["loadOptions"], debounceMs = 250) {
  const [items, setItems] = React.useState<ComboboxOption[]>([])
  const [loading, setLoading] = React.useState(false)
  React.useEffect(() => {
    if (!loadOptions || !open) return
    const ctl = new AbortController()
    setLoading(true)
    const t = setTimeout(() => {
      loadOptions(query, ctl.signal)
        .then((r) => {
          if (!ctl.signal.aborted) setItems(r)
        })
        .catch(() => {
          if (!ctl.signal.aborted) setItems([])
        })
        .finally(() => {
          if (!ctl.signal.aborted) setLoading(false)
        })
    }, debounceMs)
    return () => {
      clearTimeout(t)
      ctl.abort()
    }
  }, [open, query, loadOptions, debounceMs])
  return { items, loading }
}

/**
 * Searchable single-select. Replaces free-text-plus-datalist patterns (place search, client search).
 * The list is a real listbox (cmdk): type to search, Arrows move, Enter picks, Esc closes.
 */
export function Combobox({
  value,
  onChange,
  options = [],
  loadOptions,
  onCreate,
  selectedOption,
  placeholder = "Select",
  searchPlaceholder = "Search",
  emptyText = "No results",
  clearable,
  invalid,
  disabled,
  id,
  className,
  ...aria
}: ComboboxProps) {
  const [open, setOpen] = React.useState(false)
  const [query, setQuery] = React.useState("")
  const [picked, setPicked] = React.useState<ComboboxOption | null>(null)
  const async = useAsyncOptions(open, query, loadOptions)
  const list = loadOptions ? async.items : options
  const current = list.find((o) => o.value === value) ?? options.find((o) => o.value === value) ?? (picked?.value === value ? picked : null) ?? selectedOption ?? null
  const q = query.trim()
  const canCreate = Boolean(onCreate && q && !list.some((o) => o.label.toLowerCase() === q.toLowerCase()))

  function pick(o: ComboboxOption | null) {
    setPicked(o)
    onChange(o?.value ?? null, o)
    setOpen(false)
    setQuery("")
  }

  async function create() {
    const made = await onCreate?.(q)
    if (made) pick(made)
    else {
      setOpen(false)
      setQuery("")
    }
  }

  return (
    <Popover
      open={open}
      onOpenChange={(o) => {
        setOpen(o)
        if (!o) setQuery("")
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          id={id}
          role="combobox"
          aria-expanded={open}
          aria-haspopup="listbox"
          aria-invalid={invalid || undefined}
          disabled={disabled}
          data-state={open ? "open" : "closed"}
          className={cn(FIELD_CLASS, "flex items-center justify-between gap-2 text-left", className)}
          {...aria}
        >
          <span className={cn("flex min-w-0 items-center gap-2 truncate", !current && "text-soft")}>
            {current?.icon}
            {current?.label ?? placeholder}
          </span>
          <Chevron open={open} />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] min-w-[240px] p-1.5">
        <CommandPrimitive shouldFilter={!loadOptions} loop label={aria["aria-label"] ?? placeholder}>
          <div className="flex items-center gap-2 border-b border-rule px-2.5 pb-2 pt-1">
            <svg aria-hidden width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" className="shrink-0 text-soft">
              <circle cx="7" cy="7" r="4.5" />
              <path d="M10.5 10.5L14 14" />
            </svg>
            <CommandPrimitive.Input
              value={query}
              onValueChange={setQuery}
              placeholder={searchPlaceholder}
              className="h-7 w-full bg-transparent text-[14px] text-ink outline-none placeholder:text-soft"
            />
          </div>
          <CommandPrimitive.List className="max-h-[280px] overflow-y-auto pt-1.5">
            {async.loading && loadOptions ? (
              <div role="status" className="px-2.5 py-2 text-[13px] text-body">
                Searching
              </div>
            ) : (
              <CommandPrimitive.Empty className="px-2.5 py-3 text-[13px] text-body">{emptyText}</CommandPrimitive.Empty>
            )}
            {clearable && value ? (
              <CommandPrimitive.Item value="__clear__" onSelect={() => pick(null)} className={cn(OPTION_CLASS, "text-body")}>
                Clear selection
              </CommandPrimitive.Item>
            ) : null}
            {list.map((o) => (
              <CommandPrimitive.Item
                key={o.value}
                value={`${o.label} ${o.value}`}
                keywords={o.description ? [o.description] : undefined}
                disabled={o.disabled}
                onSelect={() => pick(o)}
                className={OPTION_CLASS}
              >
                {o.icon ? <span className="shrink-0">{o.icon}</span> : null}
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className={cn(o.value === value ? "font-bold" : "font-medium")}>{o.label}</span>
                  {o.description ? <span className="text-[12px] text-body">{o.description}</span> : null}
                </span>
                <span className="flex w-4 shrink-0 justify-center text-accent-text">{o.value === value ? <Check /> : null}</span>
              </CommandPrimitive.Item>
            ))}
            {canCreate ? (
              <>
                <div className="my-1 h-px bg-rule" />
                <CommandPrimitive.Item value={`__create__ ${q}`} forceMount onSelect={() => void create()} className={cn(OPTION_CLASS, "font-bold text-accent-text")}>
                  <svg aria-hidden width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                    <path d="M7 2v10M2 7h10" />
                  </svg>
                  Create &quot;{q}&quot;
                </CommandPrimitive.Item>
              </>
            ) : null}
          </CommandPrimitive.List>
        </CommandPrimitive>
      </PopoverContent>
    </Popover>
  )
}

export interface MultiSelectProps {
  value: string[]
  onChange: (value: string[]) => void
  options: ComboboxOption[]
  placeholder?: string
  searchPlaceholder?: string
  emptyText?: string
  id?: string
  disabled?: boolean
  invalid?: boolean
  className?: string
  "aria-label"?: string
}

/** Multi-select with removable chips. Same listbox behaviour as Combobox; the popover stays open while picking. */
export function MultiSelect({
  value,
  onChange,
  options,
  placeholder = "Select",
  searchPlaceholder = "Search",
  emptyText = "No results",
  invalid,
  disabled,
  id,
  className,
  ...aria
}: MultiSelectProps) {
  const [open, setOpen] = React.useState(false)
  const chosen = value.map((v) => options.find((o) => o.value === v)).filter((o): o is ComboboxOption => Boolean(o))
  const toggle = (v: string) => onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v])

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div
          id={id}
          role="combobox"
          tabIndex={disabled ? -1 : 0}
          aria-expanded={open}
          aria-haspopup="listbox"
          aria-disabled={disabled || undefined}
          aria-invalid={invalid || undefined}
          data-state={open ? "open" : "closed"}
          onKeyDown={(e) => {
            if ((e.key === "Enter" || e.key === " " || e.key === "ArrowDown") && e.target === e.currentTarget) {
              e.preventDefault()
              setOpen(true)
            }
          }}
          className={cn(FIELD_CLASS, "flex h-auto min-h-[42px] cursor-pointer flex-wrap items-center gap-1.5 py-1.5 pr-2.5", disabled && "pointer-events-none", className)}
          {...aria}
        >
          {chosen.map((o) => (
            <span key={o.value} className="inline-flex items-center gap-1.5 rounded-full border border-accent-line bg-accent-wash py-1 pl-2.5 pr-1.5 text-[12px] font-bold text-accent-text">
              {o.label}
              <button
                type="button"
                aria-label={`Remove ${o.label}`}
                onClick={(e) => {
                  e.stopPropagation()
                  toggle(o.value)
                }}
                className="flex size-4 items-center justify-center rounded-full outline-none hover:bg-track focus-visible:ring-2 focus-visible:ring-sindoor/40"
              >
                <svg aria-hidden width="10" height="10" viewBox="0 0 10 10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
                  <path d="M2 2l6 6M8 2L2 8" />
                </svg>
              </button>
            </span>
          ))}
          {chosen.length === 0 ? <span className="text-soft">{placeholder}</span> : null}
          <Chevron open={open} className="ml-auto" />
        </div>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] min-w-[240px] p-1.5">
        <CommandPrimitive loop label={aria["aria-label"] ?? placeholder}>
          <div className="border-b border-rule px-2.5 pb-2 pt-1">
            <CommandPrimitive.Input placeholder={searchPlaceholder} className="h-7 w-full bg-transparent text-[14px] text-ink outline-none placeholder:text-soft" />
          </div>
          <CommandPrimitive.List className="max-h-[280px] overflow-y-auto pt-1.5">
            <CommandPrimitive.Empty className="px-2.5 py-3 text-[13px] text-body">{emptyText}</CommandPrimitive.Empty>
            {options.map((o) => (
              <CommandPrimitive.Item key={o.value} value={`${o.label} ${o.value}`} disabled={o.disabled} onSelect={() => toggle(o.value)} className={OPTION_CLASS} aria-selected={value.includes(o.value)}>
                <span className={cn("flex size-[18px] shrink-0 items-center justify-center rounded-[5px] border", value.includes(o.value) ? "border-ink bg-ink text-white" : "border-rule-strong bg-white")}>
                  {value.includes(o.value) ? <Check className="size-3" /> : null}
                </span>
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="font-medium">{o.label}</span>
                  {o.description ? <span className="text-[12px] text-body">{o.description}</span> : null}
                </span>
              </CommandPrimitive.Item>
            ))}
          </CommandPrimitive.List>
        </CommandPrimitive>
      </PopoverContent>
    </Popover>
  )
}
