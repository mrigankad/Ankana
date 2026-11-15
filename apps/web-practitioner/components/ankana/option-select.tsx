"use client";

import { ChevronDown } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export interface Option {
  value: string;
  label: string;
}

/**
 * The one place a "select" is drawn. A button opens a Radix radio menu, so there is no
 * native <select>. Swap the body for the design-system listbox when it lands.
 */
export function OptionSelect({ value, options, onChange, label, disabled }: {
  value: string;
  options: Option[];
  onChange: (value: string) => void;
  label: string;
  disabled?: boolean;
}) {
  const current = options.find((o) => o.value === value)?.label ?? value;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        disabled={disabled}
        aria-label={label}
        className="inline-flex items-center gap-2 rounded-[6px] border border-rule bg-white px-3 py-[7px] text-[14px] font-bold leading-[18px] text-ink disabled:opacity-50"
      >
        {current}
        <ChevronDown size={14} aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="max-h-72 overflow-auto">
        <DropdownMenuRadioGroup value={value} onValueChange={onChange}>
          {options.map((o) => (
            <DropdownMenuRadioItem key={o.value} value={o.value}>
              {o.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Custom on/off switch (a button with role=switch, not a native checkbox). */
export function Toggle({ on, onChange, label, disabled }: {
  on: boolean;
  onChange: (next: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!on)}
      className={`relative h-[22px] w-[40px] shrink-0 rounded-[8px] transition-colors disabled:opacity-50 ${on ? "bg-ok" : "bg-rule"}`}
    >
      <span className={`absolute top-[2px] size-[18px] rounded-[6px] bg-white transition-all ${on ? "left-[20px]" : "left-[2px]"}`} />
    </button>
  );
}
