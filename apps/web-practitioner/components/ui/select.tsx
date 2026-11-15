"use client"

import * as React from "react"
import { Select as SelectPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"
import { Check, Chevron, FIELD_CLASS, OPTION_CLASS, POPUP_CLASS } from "@/components/ui/field"

export interface SelectOption {
  value: string
  label: string
  description?: string
  /** Leading icon or logo. */
  icon?: React.ReactNode
  disabled?: boolean
  /** Options with the same group string render under one heading, in first-seen order. */
  group?: string
}

export interface SelectProps {
  value: string
  onValueChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  id?: string
  name?: string
  disabled?: boolean
  invalid?: boolean
  className?: string
  "aria-label"?: string
  "aria-labelledby"?: string
}

// Radix forbids "" as an item value; the empty option is mapped to a sentinel.
const EMPTY = "__ankana_empty__"
const enc = (v: string) => (v === "" ? EMPTY : v)
const dec = (v: string) => (v === EMPTY ? "" : v)

/**
 * Ankana Select: custom listbox popover (never a native <select>).
 * Keyboard: Enter/Space/Arrows open, type-ahead, Home/End, Esc closes. Supports groups,
 * descriptions, icons and disabled options. Use value "" for an explicit "none" option.
 */
export function Select({
  value,
  onValueChange,
  options,
  placeholder = "Select",
  invalid,
  className,
  disabled,
  id,
  name,
  ...aria
}: SelectProps) {
  const groups = React.useMemo(() => {
    const map = new Map<string, SelectOption[]>()
    for (const o of options) {
      const g = o.group ?? ""
      map.set(g, [...(map.get(g) ?? []), o])
    }
    return [...map.entries()]
  }, [options])
  const selected = options.find((o) => o.value === value)

  return (
    <SelectPrimitive.Root value={enc(value)} onValueChange={(v) => onValueChange(dec(v))} disabled={disabled} name={name}>
      <SelectPrimitive.Trigger
        id={id}
        data-slot="select-trigger"
        data-invalid={invalid || undefined}
        aria-invalid={invalid || undefined}
        className={cn(FIELD_CLASS, "group flex items-center justify-between gap-2 text-left data-[placeholder]:text-soft", className)}
        {...aria}
      >
        <span className="flex min-w-0 items-center gap-2 truncate">
          {selected?.icon}
          <SelectPrimitive.Value placeholder={placeholder}>{selected?.label}</SelectPrimitive.Value>
        </span>
        <SelectPrimitive.Icon asChild>
          <span className="group-data-[state=open]:rotate-180 transition-transform motion-reduce:transition-none">
            <Chevron />
          </span>
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          position="popper"
          sideOffset={6}
          collisionPadding={12}
          className={cn(POPUP_CLASS, "max-h-[min(360px,var(--radix-select-content-available-height))] min-w-[var(--radix-select-trigger-width)] overflow-hidden")}
        >
          <SelectPrimitive.Viewport className="max-h-[inherit] overflow-y-auto">
            {groups.map(([group, items]) => (
              <SelectPrimitive.Group key={group || "_"}>
                {group ? (
                  <SelectPrimitive.Label className="px-2.5 pb-1 pt-2 text-[11px] font-bold uppercase tracking-[0.08em] text-soft">
                    {group}
                  </SelectPrimitive.Label>
                ) : null}
                {items.map((o) => (
                  <SelectPrimitive.Item key={o.value} value={enc(o.value)} disabled={o.disabled} textValue={o.label} className={OPTION_CLASS}>
                    {o.icon ? <span className="shrink-0">{o.icon}</span> : null}
                    <span className="flex min-w-0 flex-1 flex-col">
                      <SelectPrimitive.ItemText>{o.label}</SelectPrimitive.ItemText>
                      {o.description ? <span className="text-[12px] font-normal text-body">{o.description}</span> : null}
                    </span>
                    <span className="flex w-4 shrink-0 justify-center text-accent-text">
                      <SelectPrimitive.ItemIndicator>
                        <Check />
                      </SelectPrimitive.ItemIndicator>
                    </span>
                  </SelectPrimitive.Item>
                ))}
              </SelectPrimitive.Group>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  )
}
