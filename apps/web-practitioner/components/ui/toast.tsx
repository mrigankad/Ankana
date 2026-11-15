"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

type ToastTone = "default" | "success" | "error"
interface ToastItem {
  id: number
  message: React.ReactNode
  tone: ToastTone
}

const ToastContext = React.createContext<((message: React.ReactNode, opts?: { tone?: ToastTone; durationMs?: number }) => void) | null>(null)

/** Mount once near the root. Toasts announce via aria-live and dismiss themselves. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = React.useState<ToastItem[]>([])
  const next = React.useRef(1)
  const push = React.useCallback((message: React.ReactNode, opts?: { tone?: ToastTone; durationMs?: number }) => {
    const id = next.current++
    setItems((l) => [...l, { id, message, tone: opts?.tone ?? "default" }])
    setTimeout(() => setItems((l) => l.filter((t) => t.id !== id)), opts?.durationMs ?? 4000)
  }, [])
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div aria-live="polite" role="status" className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(360px,calc(100vw-32px))] flex-col gap-2">
        {items.map((t) => (
          <div
            key={t.id}
            className="pointer-events-auto flex items-center gap-2.5 rounded-xl bg-ink px-3.5 py-3 text-[14px] font-semibold text-white shadow-[var(--shadow-toast)] animate-in fade-in-0 slide-in-from-bottom-2 motion-reduce:animate-none"
          >
            <span className={cn("size-2 shrink-0 rounded-full", t.tone === "error" ? "bg-alert" : t.tone === "success" ? "bg-ok" : "bg-accent-light")} aria-hidden />
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

/** const toast = useToast(); toast("Chart saved", { tone: "success" }). No-ops outside a provider. */
export function useToast() {
  return React.useContext(ToastContext) ?? (() => {})
}
