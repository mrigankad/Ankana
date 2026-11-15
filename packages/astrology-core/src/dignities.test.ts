import { describe, expect, it } from "vitest";

import { dignityOf, isCombust } from "./dignities";

describe("dignityOf", () => {
  it("marks exaltations", () => {
    expect(dignityOf("sun", 10)).toBe("exalted"); // Aries
    expect(dignityOf("saturn", 200)).toBe("exalted"); // Libra
    expect(dignityOf("jupiter", 95)).toBe("exalted"); // Cancer
  });

  it("marks debilitations opposite exaltation", () => {
    expect(dignityOf("sun", 190)).toBe("debilitated"); // Libra
    expect(dignityOf("moon", 220)).toBe("debilitated"); // Scorpio
  });

  it("marks moolatrikona ranges before own sign", () => {
    expect(dignityOf("sun", 130)).toBe("moolatrikona"); // Leo 10deg
    expect(dignityOf("sun", 145)).toBe("own"); // Leo 25deg
    expect(dignityOf("mars", 5)).toBe("moolatrikona"); // Aries 5deg
    expect(dignityOf("mars", 15)).toBe("own"); // Aries 15deg
  });

  it("classifies friendship placements", () => {
    expect(dignityOf("jupiter", 130)).toBe("friend"); // Jupiter in Leo (Sun's sign)
    expect(dignityOf("venus", 130)).toBe("enemy"); // Venus in Leo
    expect(dignityOf("saturn", 70)).toBe("friend"); // Saturn in Gemini (Mercury's)
  });

  it("treats nodes as neutral", () => {
    expect(dignityOf("rahu", 45)).toBe("neutral");
  });
});

describe("isCombust", () => {
  it("uses classical orbs per planet", () => {
    expect(isCombust("mercury", 100, 110, false)).toBe(true); // 10 < 14
    expect(isCombust("mercury", 100, 113.5, true)).toBe(false); // 13.5 > 12R
    expect(isCombust("venus", 100, 109, false)).toBe(true);
    expect(isCombust("venus", 100, 111, false)).toBe(false);
  });

  it("handles wraparound separations", () => {
    expect(isCombust("saturn", 358, 8, false)).toBe(true); // 10 deg apart
  });

  it("never marks the sun or nodes combust", () => {
    expect(isCombust("sun", 100, 100, false)).toBe(false);
    expect(isCombust("rahu", 100, 100, false)).toBe(false);
  });
});
