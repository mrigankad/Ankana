import { describe, expect, it } from "vitest";

import { followUpDays } from "./clients";
import { formatCoords, hhmm, parseDate, shiftTime, to24h, weekdayOf, zoneInfo } from "./intake";

describe("intake helpers", () => {
  it("echoes the weekday for a typed date and rejects impossible ones", () => {
    expect(weekdayOf(parseDate("15", "03", "1995")!)).toBe("Wednesday");
    expect(parseDate("31", "02", "1995")).toBeNull();
    expect(parseDate("15", "13", "1995")).toBeNull();
  });

  it("converts 12 hour time to 24 hour", () => {
    expect(hhmm(to24h("06", "42", false)!)).toBe("06:42");
    expect(hhmm(to24h("12", "05", false)!)).toBe("00:05");
    expect(hhmm(to24h("12", "05", true)!)).toBe("12:05");
    expect(to24h("13", "00", false)).toBeNull();
  });

  it("shifts times around midnight", () => {
    expect(hhmm(shiftTime({ h: 0, m: 5 }, -14))).toBe("23:51");
    expect(hhmm(shiftTime({ h: 6, m: 42 }, 14))).toBe("06:56");
  });

  it("reports the offset and DST state from the tz database", () => {
    const z = zoneInfo("Asia/Kolkata", parseDate("15", "03", "1995")!);
    expect(z?.dst).toBe("None. +05:30 applied");
    expect(zoneInfo("Europe/London", parseDate("15", "07", "1995")!)?.isDst).toBe(true);
  });

  it("formats coordinates", () => {
    expect(formatCoords(25.3176, 82.9739)).toBe("25.3176 N, 82.9739 E");
  });

  it("reads follow-up labels", () => {
    expect(followUpDays("Today, 11:30")).toBe(0);
    expect(followUpDays("Not scheduled")).toBeNull();
  });
});
