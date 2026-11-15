"use client";

import { Languages } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useLanguage } from "@/lib/i18n/provider";
import { isLang, LANGUAGES } from "@/lib/i18n/translate";

/** Radio items for the language choice; drop into any open DropdownMenuContent (the user menu does). */
export function LanguageMenuItems() {
  const { lang, setLang, t } = useLanguage();
  return (
    <>
      <DropdownMenuLabel className="text-[12px] text-soft">{t("Language")}</DropdownMenuLabel>
      <DropdownMenuRadioGroup value={lang} onValueChange={(v) => isLang(v) && setLang(v)}>
        {LANGUAGES.map((l) => (
          <DropdownMenuRadioItem key={l.code} value={l.code} lang={l.code}>
            <span className={l.code === "hi" ? "deva" : undefined}>{l.label}</span>
          </DropdownMenuRadioItem>
        ))}
      </DropdownMenuRadioGroup>
    </>
  );
}

/** Standalone switcher for when built-in auth (and so the user menu) is off. */
export function LanguageSwitcher({ className, compact }: { className?: string; compact?: boolean }) {
  const { lang, t } = useLanguage();
  const current = LANGUAGES.find((l) => l.code === lang);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={t("Language")}
        title={compact ? current?.label : undefined}
        className={
          className ??
          (compact
            ? "flex size-8 shrink-0 items-center justify-center rounded-[6px] text-body outline-none hover:bg-white/70 focus-visible:ring-[3px] focus-visible:ring-sindoor/30"
            : null) ??
          "flex w-full items-center gap-2 rounded-[6px] px-[10px] py-[7px] text-left text-[14px] leading-[18px] text-body hover:bg-white/70"
        }
      >
        <Languages className="size-4 shrink-0" aria-hidden />
        {compact ? null : <span className={lang === "hi" ? "deva grow" : "grow"}>{current?.label}</span>}
      </DropdownMenuTrigger>
      <DropdownMenuContent side="top" align={compact ? "end" : "start"} className="w-[200px]">
        <LanguageMenuItems />
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
