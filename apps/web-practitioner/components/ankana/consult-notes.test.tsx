import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { encodeNote, FactChip, NoteBody } from "./consult-notes";
import type { NoteFact } from "@/lib/api/consult";
import { LanguageProvider } from "@/lib/i18n/provider";

afterEach(cleanup);

const saturn: NoteFact = { id: "s1", type: "planet", ref: "planet:saturn", label: "Saturn in Aquarius, house 12" };
const dasha: NoteFact = { id: "d1", type: "dasha", ref: "dasha:moon/mars", label: "Moon / Mars, until 2027-02" };

describe("encodeNote", () => {
  it("turns [[label]] tokens into markers and keeps their facts", () => {
    const r = encodeNote("Watch [[Saturn in Aquarius, house 12]] and [[Moon / Mars, until 2027-02]].", [saturn, dasha]);
    expect(r.body).toBe("Watch {{fact:s1}} and {{fact:d1}}.");
    expect(r.facts.map((f) => f.id)).toEqual(["s1", "d1"]);
  });

  it("drops a fact whose token the practitioner deleted or edited", () => {
    const r = encodeNote("Watch [[Saturn in Aquarius]] only", [saturn]);
    expect(r.facts).toEqual([]);
    expect(r.body).toBe("Watch [[Saturn in Aquarius]] only");
  });

  it("handles the same fact pinned twice", () => {
    const again = { ...saturn, id: "s2" };
    const r = encodeNote("[[Saturn in Aquarius, house 12]] then [[Saturn in Aquarius, house 12]]", [saturn, again]);
    expect(r.body).toBe("{{fact:s1}} then {{fact:s2}}");
  });
});

describe("NoteBody", () => {
  it("renders pinned facts as chips that link to the chart tab", () => {
    render(
      <LanguageProvider>
        <NoteBody body="Open with {{fact:s1}} then {{fact:d1}}." facts={[saturn, dasha]} chartId="chart-1" />
      </LanguageProvider>,
    );
    const chips = document.querySelectorAll("[data-fact-type]");
    expect(chips).toHaveLength(2);
    expect(screen.getByRole("link", { name: /Saturn in Aquarius/ })).toHaveAttribute("href", "/charts/chart-1?tab=planets");
    expect(screen.getByRole("link", { name: /Moon \/ Mars/ })).toHaveAttribute("href", "/charts/chart-1?tab=dashas");
    expect(document.body.textContent).toContain("Open with");
  });

  it("shows a chip without a link when the client has no chart", () => {
    render(
      <LanguageProvider>
        <FactChip fact={saturn} chartId={null} />
      </LanguageProvider>,
    );
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText(saturn.label)).toBeInTheDocument();
  });
});
