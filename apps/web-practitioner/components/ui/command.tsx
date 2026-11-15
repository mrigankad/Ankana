"use client"

import * as React from "react"
import { Command as CommandPrimitive } from "cmdk"
import { Dialog as DialogPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"
import { OPTION_CLASS } from "@/components/ui/field"

/** Command palette in a modal. Open with your own shortcut; items are real options (no kbd hints required). */
export function CommandDialog({
  open,
  onOpenChange,
  label = "Command palette",
  placeholder = "Search",
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  label?: string
  placeholder?: string
  children: React.ReactNode
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-ink/40 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in-0 motion-reduce:animate-none" />
        <DialogPrimitive.Content aria-label={label} className="fixed left-1/2 top-[18vh] z-50 w-[calc(100vw-32px)] max-w-[560px] -translate-x-1/2 overflow-hidden rounded-[10px] border border-rule bg-white shadow-[var(--shadow-modal)] outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 motion-reduce:animate-none">
          <DialogPrimitive.Title className="sr-only">{label}</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">Type to filter, use arrow keys to move, Enter to choose.</DialogPrimitive.Description>
          <CommandPrimitive loop label={label}>
            <CommandPrimitive.Input placeholder={placeholder} className="h-12 w-full border-b border-rule bg-transparent px-4 text-[15px] text-ink outline-none placeholder:text-soft" />
            <CommandPrimitive.List className="max-h-[340px] overflow-y-auto p-1.5">
              <CommandPrimitive.Empty className="px-3 py-6 text-center text-[13px] text-body">No results</CommandPrimitive.Empty>
              {children}
            </CommandPrimitive.List>
          </CommandPrimitive>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

export function CommandGroup({ className, ...props }: React.ComponentProps<typeof CommandPrimitive.Group>) {
  return <CommandPrimitive.Group className={cn("[&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-bold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.08em] [&_[cmdk-group-heading]]:text-soft", className)} {...props} />
}

export function CommandItem({ className, ...props }: React.ComponentProps<typeof CommandPrimitive.Item>) {
  return <CommandPrimitive.Item className={cn(OPTION_CLASS, "font-medium", className)} {...props} />
}
