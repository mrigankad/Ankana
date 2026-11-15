"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { readStoredLang, translate, writeStoredLang, type Lang } from "./translate";

type TFn = (text: string, params?: Record<string, string | number>) => string;

interface LanguageContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: TFn;
}

const LanguageContext = createContext<LanguageContextValue>({
  lang: "en",
  setLang: () => undefined,
  t: (text, params) => translate("en", text, params),
});

export const useLanguage = () => useContext(LanguageContext);
export const useT = () => useContext(LanguageContext).t;

/** Holds the UI language, persists it per user, and marks the document (lang attr drives the font stack). */
export function LanguageProvider({ children }: { children: ReactNode }) {
  const userId = useAuth().session.user?.id ?? null;
  const [lang, setLangState] = useState<Lang>("en");

  // Load after mount (and again when the signed-in user changes) so server and client first paint match.
  useEffect(() => {
    setLangState(readStoredLang(userId));
  }, [userId]);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback(
    (next: Lang) => {
      setLangState(next);
      writeStoredLang(userId, next);
    },
    [userId],
  );

  const value = useMemo<LanguageContextValue>(
    () => ({ lang, setLang, t: (text, params) => translate(lang, text, params) }),
    [lang, setLang],
  );
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}
