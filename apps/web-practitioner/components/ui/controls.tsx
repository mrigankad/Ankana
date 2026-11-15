"use client"

import * as React from "react"
import { Checkbox as CheckboxPrimitive, RadioGroup as RadioPrimitive, Switch as SwitchPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"
import { Check } from "@/components/ui/field"

const RING = "outline-none focus-visible:ring-[3px] focus-visible:ring-sindoor/30 focus-visible:border-sindoor"

/** Toggle. Replaces ad hoc role=switch buttons and checkboxes used as toggles. */
export function Switch({ className, ...props }: React.ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      data-slot="switch"
      className={cn(
        "inline-flex h-6 w-10 shrink-0 cursor-pointer items-center rounded-full border border-transparent px-[3px] transition-colors disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-(image:--fill-primary) data-[state=unchecked]:bg-rule motion-reduce:transition-none",
        RING,
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb className="block size-[18px] rounded-full bg-white shadow-[var(--shadow-raised)] transition-transform data-[state=checked]:translate-x-4 motion-reduce:transition-none" />
    </SwitchPrimitive.Root>
  )
}

/** Checkbox. Supports checked={"indeterminate"} for table select-all. Never use <input type="checkbox">. */
export function Checkbox({ className, ...props }: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        "flex size-5 shrink-0 items-center justify-center rounded-md border-[1.5px] border-rule-strong bg-white text-white transition-colors disabled:cursor-not-allowed disabled:bg-rule disabled:opacity-60 data-[state=checked]:border-ink data-[state=checked]:bg-(image:--fill-primary) data-[state=indeterminate]:border-ink data-[state=indeterminate]:bg-ink aria-invalid:border-alert motion-reduce:transition-none",
        RING,
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator>
        {props.checked === "indeterminate" ? <span className="block h-0.5 w-2.5 rounded bg-white" /> : <Check className="size-3.5" />}
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  )
}

/** Checkbox with a visible, clickable label. */
export function CheckboxField({
  label,
  description,
  id,
  className,
  ...props
}: React.ComponentProps<typeof CheckboxPrimitive.Root> & { label: React.ReactNode; description?: React.ReactNode }) {
  const autoId = React.useId()
  const cid = id ?? autoId
  return (
    <div className={cn("flex items-start gap-3", className)}>
      <Checkbox id={cid} className="mt-0.5" {...props} />
      <label htmlFor={cid} className="flex cursor-pointer flex-col text-[14px] font-medium text-ink">
        {label}
        {description ? <span className="text-[12px] font-normal text-body">{description}</span> : null}
      </label>
    </div>
  )
}

export const RadioGroup = RadioPrimitive.Root

/** Radio card: title and description in a selectable tile. Use inside RadioGroup. */
export function RadioCard({
  title,
  description,
  className,
  ...props
}: React.ComponentProps<typeof RadioPrimitive.Item> & { title: React.ReactNode; description?: React.ReactNode }) {
  return (
    <RadioPrimitive.Item
      data-slot="radio-card"
      className={cn(
        "flex flex-1 cursor-pointer flex-col items-start gap-1 rounded-[10px] border border-rule bg-white p-3.5 text-left transition-colors hover:border-rule-strong disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:border-sindoor data-[state=checked]:bg-accent-wash motion-reduce:transition-none",
        RING,
        className,
      )}
      {...props}
    >
      <span className="text-[14px] font-bold text-ink">{title}</span>
      {description ? <span className="text-[12px] text-body">{description}</span> : null}
    </RadioPrimitive.Item>
  )
}

export interface SegmentedOption<T extends string> {
  value: T
  label: React.ReactNode
  disabled?: boolean
}

/** Segmented control: a compact single-choice switcher (North/South, AM/PM, Day/Week). */
export function SegmentedControl<T extends string>({
  value,
  onValueChange,
  options,
  className,
  size = "md",
  ...aria
}: {
  value: T
  onValueChange: (value: T) => void
  options: SegmentedOption<T>[]
  size?: "sm" | "md"
  className?: string
  "aria-label"?: string
  "aria-labelledby"?: string
  disabled?: boolean
}) {
  return (
    <RadioPrimitive.Root
      value={value}
      onValueChange={(v) => onValueChange(v as T)}
      orientation="horizontal"
      className={cn("inline-flex gap-0.5 rounded-xl bg-sidebar-wash p-[3px]", className)}
      {...aria}
    >
      {options.map((o) => (
        <RadioPrimitive.Item
          key={o.value}
          value={o.value}
          disabled={o.disabled}
          className={cn(
            "rounded-[6px] font-semibold text-body outline-none transition-colors hover:text-ink focus-visible:ring-[3px] focus-visible:ring-sindoor/30 disabled:opacity-50 data-[state=checked]:bg-white data-[state=checked]:text-ink data-[state=checked]:shadow-[var(--shadow-raised)] motion-reduce:transition-none",
            size === "sm" ? "px-3 py-1 text-[12px]" : "px-4 py-[7px] text-[13px]",
          )}
        >
          {o.label}
        </RadioPrimitive.Item>
      ))}
    </RadioPrimitive.Root>
  )
}
