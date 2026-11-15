import * as React from "react"

import { cn } from "@/lib/utils"

const INK = "var(--color-ink)"
const BRAND: Record<string, { file: string; color: string }> = {
  claude: { file: "claude.svg", color: "var(--color-provider-claude)" },
  gemini: { file: "googlegemini.svg", color: "var(--color-provider-gemini)" },
  openrouter: { file: "openrouter.svg", color: "var(--color-provider-openrouter)" },
  ollama: { file: "ollama.svg", color: INK },
  openai: { file: "openai.svg", color: INK },
  anthropic: { file: "anthropic.svg", color: INK },
  ankana: { file: "ankana.svg", color: INK },
}

/** Resolve a provider kind ("claude_cli", "gemini_cli", "openai_compatible", ...) or logo file to a brand. */
function resolve(kind: string) {
  const k = kind.toLowerCase()
  if (k.includes("openrouter")) return BRAND.openrouter
  if (k.includes("claude")) return BRAND.claude
  if (k.includes("anthropic")) return BRAND.anthropic
  if (k.includes("gemini")) return BRAND.gemini
  if (k.includes("ollama")) return BRAND.ollama
  if (k.includes("openai") || k.includes("codex")) return BRAND.openai
  return BRAND.ankana
}

/**
 * Provider mark tinted via CSS mask from public/providers/*.svg.
 * Claude #D97757, Gemini #8E75B2, OpenRouter #6467F2, Ollama/OpenAI/Anthropic ink.
 * Pass the provider `kind` (or the API's `logo` file name). Decorative unless `label` is set.
 */
export function ProviderLogo({ kind, size = 20, label, className }: { kind: string; size?: number; label?: string; className?: string }) {
  const b = resolve(kind)
  const url = `url(/providers/${b.file})`
  return (
    <span
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      data-slot="provider-logo"
      className={cn("inline-block shrink-0", className)}
      style={{
        width: size,
        height: size,
        backgroundColor: b.color,
        WebkitMask: `${url} center / contain no-repeat`,
        mask: `${url} center / contain no-repeat`,
      }}
    />
  )
}
