"use client";

import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"] as const;

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function toIso(year: number, monthIndex: number, day: number): string {
  return `${year}-${pad(monthIndex + 1)}-${pad(day)}`;
}

function parseIso(iso: string): { y: number; m: number; d: number } | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null;
  const y = Number(iso.slice(0, 4));
  const m = Number(iso.slice(5, 7)) - 1;
  const d = Number(iso.slice(8, 10));
  if (!y || m < 0 || m > 11 || d < 1) return null;
  return { y, m, d };
}

function daysInMonth(year: number, monthIndex: number): number {
  return new Date(year, monthIndex + 1, 0).getDate();
}

function startWeekday(year: number, monthIndex: number): number {
  return new Date(year, monthIndex, 1).getDay();
}

export interface BirthCalendarProps {
  value: string;
  onChange: (isoDate: string) => void;
  className?: string;
  /** Inclusive max year (default: current year). */
  maxYear?: number;
  minYear?: number;
}

export function BirthCalendar({
  value,
  onChange,
  className,
  maxYear = new Date().getFullYear(),
  minYear = 1900,
}: BirthCalendarProps) {
  const selected = parseIso(value);
  const today = useMemo(() => {
    const now = new Date();
    return {
      y: now.getFullYear(),
      m: now.getMonth(),
      d: now.getDate(),
      iso: toIso(now.getFullYear(), now.getMonth(), now.getDate()),
    };
  }, []);

  const [viewYear, setViewYear] = useState(
    () => selected?.y ?? Math.min(maxYear, 1990),
  );
  const [viewMonth, setViewMonth] = useState(() => selected?.m ?? 0);

  const cells = useMemo(() => {
    const total = daysInMonth(viewYear, viewMonth);
    const offset = startWeekday(viewYear, viewMonth);
    const items: Array<{ day: number | null; iso: string | null }> = [];
    for (let i = 0; i < offset; i += 1) {
      items.push({ day: null, iso: null });
    }
    for (let day = 1; day <= total; day += 1) {
      items.push({ day, iso: toIso(viewYear, viewMonth, day) });
    }
    while (items.length % 7 !== 0) {
      items.push({ day: null, iso: null });
    }
    return items;
  }, [viewYear, viewMonth]);

  function shiftMonth(delta: number) {
    const date = new Date(viewYear, viewMonth + delta, 1);
    const nextY = date.getFullYear();
    const nextM = date.getMonth();
    if (nextY < minYear || nextY > maxYear) return;
    setViewYear(nextY);
    setViewMonth(nextM);
  }

  const canPrev =
    viewYear > minYear || (viewYear === minYear && viewMonth > 0);
  const canNext =
    viewYear < maxYear || (viewYear === maxYear && viewMonth < 11);

  const selectedLabel = selected
    ? `${MONTHS[selected.m]} ${selected.d}, ${selected.y}`
    : "Select a date";

  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-white p-3 shadow-[0_1px_0_rgba(34,30,29,0.04)] sm:p-4",
        className,
      )}
    >
      <div className="mb-3 flex items-start justify-between gap-2 sm:gap-3">
        <div className="min-w-0">
          <p className="m-0 text-[0.65rem] font-bold tracking-wide text-soft">
            Certificate date
          </p>
          <p className="mt-1 mb-0 truncate font-display text-[0.95rem] font-bold tracking-tight text-ink sm:text-[1.05rem]">
            {selectedLabel}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            disabled={!canPrev}
            aria-label="Previous month"
            onClick={() => shiftMonth(-1)}
          >
            <ChevronLeft size={16} aria-hidden />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            disabled={!canNext}
            aria-label="Next month"
            onClick={() => shiftMonth(1)}
          >
            <ChevronRight size={16} aria-hidden />
          </Button>
        </div>
      </div>

      <div className="mb-3 flex items-center gap-2">
        <Select
          aria-label="Calendar month"
          className="h-8 flex-1 px-2 text-sm"
          value={String(viewMonth)}
          onValueChange={(v) => setViewMonth(Number(v))}
          options={MONTHS.map((name, index) => ({ value: String(index), label: name }))}
        />
        <Select
          aria-label="Calendar year"
          className="h-8 w-[6rem] px-2 text-sm"
          value={String(viewYear)}
          onValueChange={(v) => setViewYear(Number(v))}
          options={Array.from({ length: maxYear - minYear + 1 }, (_, i) => String(maxYear - i)).map((y) => ({ value: y, label: y }))}
        />
      </div>

      <div
        role="grid"
        aria-label="Certificate date calendar"
        className="grid grid-cols-7 gap-1"
      >
        {WEEKDAYS.map((day) => (
          <div
            key={day}
            role="columnheader"
            className="py-1 text-center text-[0.65rem] font-bold tracking-wide text-soft"
          >
            {day}
          </div>
        ))}
        {cells.map((cell, index) => {
          if (!cell.day || !cell.iso) {
            return <div key={`empty-${index}`} className="aspect-square" />;
          }
          const isSelected = value === cell.iso;
          const isToday = cell.iso === today.iso;
          const isFuture = cell.iso > today.iso;

          return (
            <button
              key={cell.iso}
              type="button"
              role="gridcell"
              disabled={isFuture}
              aria-selected={isSelected}
              aria-label={`${MONTHS[viewMonth]} ${cell.day}, ${viewYear}`}
              onClick={() => onChange(cell.iso!)}
              className={cn(
                "aspect-square rounded-md text-[0.8rem] font-semibold transition-colors sm:rounded-lg sm:text-sm",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sindoor/30",
                isFuture && "cursor-not-allowed opacity-30",
                !isFuture && !isSelected && "text-ink hover:bg-wash-soft",
                isToday && !isSelected && "ring-1 ring-rule-strong",
                isSelected && "bg-sindoor text-white hover:bg-sindoor-hover hover:text-white",
              )}
            >
              {cell.day}
            </button>
          );
        })}
      </div>

      <p className="mt-3 mb-0 text-[0.72rem] text-muted-foreground">
        Local civil date on the birth certificate - not the Hindu tithi.
      </p>
    </div>
  );
}
