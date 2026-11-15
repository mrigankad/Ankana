"use client"

import * as React from "react"
import { Dialog as DialogPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

export const Dialog = DialogPrimitive.Root
export const DialogTrigger = DialogPrimitive.Trigger
export const DialogClose = DialogPrimitive.Close

/** Centered modal. Focus is trapped, Esc and overlay click close it, focus returns to the trigger. */
export function DialogContent({
  className,
  children,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content>) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-ink/40 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 motion-reduce:animate-none" />
      <DialogPrimitive.Content
        data-slot="dialog-content"
        className={cn(
          "fixed left-1/2 top-1/2 z-50 flex w-[calc(100vw-32px)] max-w-[440px] -translate-x-1/2 -translate-y-1/2 flex-col gap-3 rounded-[10px] border border-rule bg-white p-6 shadow-[var(--shadow-modal)] outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 motion-reduce:animate-none",
          className,
        )}
        {...props}
      >
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
}

export function DialogTitle({ className, ...props }: React.ComponentProps<typeof DialogPrimitive.Title>) {
  return <DialogPrimitive.Title className={cn("m-0 text-[18px] font-bold leading-6 text-ink", className)} {...props} />
}

export function DialogDescription({ className, ...props }: React.ComponentProps<typeof DialogPrimitive.Description>) {
  return <DialogPrimitive.Description className={cn("m-0 text-[14px] leading-[21px] text-body", className)} {...props} />
}

export function DialogFooter({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("flex justify-end gap-2.5 pt-2", className)} {...props} />
}

export interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: React.ReactNode
  description?: React.ReactNode
  confirmLabel?: string
  cancelLabel?: string
  /** "danger" styles the confirm button as destructive. */
  tone?: "default" | "danger"
  loading?: boolean
  onConfirm: () => void | Promise<void>
}

/**
 * Replaces window.confirm / alert. Controlled:
 *   const [target, setTarget] = useState<Item | null>(null)
 *   <ConfirmDialog open={!!target} onOpenChange={(o) => !o && setTarget(null)} ... onConfirm={() => remove(target)} />
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "default",
  loading,
  onConfirm,
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent role="alertdialog">
        <DialogTitle>{title}</DialogTitle>
        {description ? <DialogDescription>{description}</DialogDescription> : <DialogDescription className="sr-only">{String(title)}</DialogDescription>}
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" size="md" type="button">
              {cancelLabel}
            </Button>
          </DialogClose>
          <Button
            variant={tone === "danger" ? "danger" : "default"}
            size="md"
            type="button"
            loading={loading}
            onClick={async () => {
              await onConfirm()
              onOpenChange(false)
            }}
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
