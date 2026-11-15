import { describe, expect, it } from "vitest";

import { activeRole, homeFor, pathAllowed } from "./roles";

const membership = (role: "owner" | "astrologer" | "assistant" | "client", id = "p1") => ({
  member_id: "m",
  practice_id: id,
  practice_name: "P",
  role,
});

describe("role guard", () => {
  it("a client sees only the portal", () => {
    expect(pathAllowed("client", "/portal")).toBe(true);
    for (const p of ["/", "/clients", "/clients/abc", "/charts/1", "/settings/team", "/settings/sessions", "/library/remedies"]) {
      expect(pathAllowed("client", p), p).toBe(false);
    }
    expect(homeFor("client")).toBe("/portal");
  });

  it("staff never see the portal and land on Today", () => {
    for (const role of ["owner", "astrologer", "assistant"] as const) {
      expect(pathAllowed(role, "/portal")).toBe(false);
      expect(pathAllowed(role, "/clients")).toBe(true);
      expect(pathAllowed(role, "/settings/sessions")).toBe(true);
    }
    expect(homeFor("owner")).toBe("/");
  });

  it("team, practice and billing settings are owner-only", () => {
    for (const p of ["/settings/team", "/settings/practice", "/settings/billing"]) {
      expect(pathAllowed("owner", p)).toBe(true);
      expect(pathAllowed("astrologer", p), p).toBe(false);
      expect(pathAllowed("assistant", p), p).toBe(false);
    }
  });

  it("does not match prefixes by accident and allows everything when the role is unknown", () => {
    expect(pathAllowed("client", "/portals")).toBe(false);
    expect(pathAllowed("astrologer", "/settings/teammates")).toBe(true);
    expect(pathAllowed(null, "/settings/team")).toBe(true);
  });

  it("reads the role of the practice in view", () => {
    const memberships = [membership("owner", "p1"), membership("client", "p2")];
    expect(activeRole({ memberships, practiceId: "p2" })).toBe("client");
    expect(activeRole({ memberships, practiceId: "p1" })).toBe("owner");
    expect(activeRole({ memberships: [], practiceId: null })).toBeNull();
  });
});
