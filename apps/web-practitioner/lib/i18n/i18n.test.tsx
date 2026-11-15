import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { HI } from "./hi";
import { LanguageProvider, useT } from "./provider";
import { readStoredLang, storageKey, tName, translate } from "./translate";
import { LanguageSwitcher } from "@/components/language-switcher";

vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => ({ enabled: true, session: { user: { id: "u1" } } }),
}));

function Probe() {
  const t = useT();
  return <p data-testid="probe">{t("Clients")}</p>;
}

beforeEach(() => window.localStorage.clear());
afterEach(cleanup);

describe("translate", () => {
  it("falls back to English and fills placeholders", () => {
    expect(translate("hi", "Not in the dictionary")).toBe("Not in the dictionary");
    expect(translate("hi", "{n} people", { n: 3 })).toBe("3 लोग");
    expect(translate("en", "{n} people", { n: 3 })).toBe("3 people");
  });

  it("translates names that carry a trailing number or pada", () => {
    const t = (s: string) => translate("hi", s);
    expect(tName(t, "Uttara Bhadrapada 3")).toBe("उत्तर भाद्रपद 3");
    expect(tName(t, "Magha, pada 2")).toBe("मघा, चरण 2");
  });

  it("keeps placeholder names identical between English key and Hindi text", () => {
    const names = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    for (const [en, hi] of Object.entries(HI)) {
      expect(names(hi), en).toEqual(names(en));
    }
  });

  it("covers every literal passed to t() in app and components", () => {
    const root = join(__dirname, "..", "..");
    const files: string[] = [];
    const walk = (d: string) => {
      for (const f of readdirSync(d)) {
        const p = join(d, f);
        if (f === "node_modules" || f === ".next") continue;
        if (statSync(p).isDirectory()) walk(p);
        else if (/\.tsx?$/.test(f) && !/\.test\./.test(f)) files.push(p);
      }
    };
    ["app", "components"].forEach((d) => walk(join(root, d)));
    const rx = new RegExp(String.raw`\b(?:t|tr)\(\s*"((?:[^"\\]|\\.)*)"`, "g");
    const missing = new Set<string>();
    for (const f of files) {
      const src = readFileSync(f, "utf8");
      for (const m of src.matchAll(rx)) if (!(m[1] in HI)) missing.add(m[1]);
    }
    expect([...missing]).toEqual([]);
  });
});

describe("language switcher", () => {
  it("switches the UI to Hindi, persists per user and sets the document language", async () => {
    render(
      <LanguageProvider>
        <LanguageSwitcher />
        <Probe />
      </LanguageProvider>,
    );
    expect(screen.getByTestId("probe")).toHaveTextContent("Clients");
    const trigger = screen.getByRole("button", { name: "Language" });
    fireEvent.keyDown(trigger, { key: "Enter" });
    const hindi = await screen.findByRole("menuitemradio", { name: "हिन्दी" });
    fireEvent.click(hindi);
    expect(screen.getByTestId("probe")).toHaveTextContent("ग्राहक");
    expect(document.documentElement.lang).toBe("hi");
    expect(window.localStorage.getItem(storageKey("u1"))).toBe("hi");
    expect(window.localStorage.getItem(storageKey(null))).toBeNull();
  });

  it("restores the saved language for that user on load", () => {
    window.localStorage.setItem(storageKey("u1"), "hi");
    expect(readStoredLang("u1")).toBe("hi");
    expect(readStoredLang("someone-else")).toBe("en");
    render(
      <LanguageProvider>
        <Probe />
      </LanguageProvider>,
    );
    expect(screen.getByTestId("probe")).toHaveTextContent("ग्राहक");
  });

  it("uses no native select element", () => {
    const { container } = render(
      <LanguageProvider>
        <LanguageSwitcher />
      </LanguageProvider>,
    );
    expect(container.querySelector("select")).toBeNull();
  });
});
