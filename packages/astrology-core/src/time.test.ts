import { describe, expect, it } from "vitest";

import { julianDay, toUtcDate } from "./time";

describe("toUtcDate", () => {
  it("converts IST wall clock to UTC", () => {
    const utc = toUtcDate("2020-06-15", "12:00", "Asia/Kolkata");
    expect(utc.toISOString()).toBe("2020-06-15T06:30:00.000Z");
  });

  it("handles daylight saving time offsets", () => {
    const utc = toUtcDate("2020-06-15", "12:00", "America/New_York");
    expect(utc.toISOString()).toBe("2020-06-15T16:00:00.000Z");
  });

  it("handles winter offsets in DST zones", () => {
    const utc = toUtcDate("2020-01-15", "12:00", "America/New_York");
    expect(utc.toISOString()).toBe("2020-01-15T17:00:00.000Z");
  });
});

describe("julianDay", () => {
  it("returns 2451545.0 for the J2000 epoch", () => {
    expect(julianDay(new Date("2000-01-01T12:00:00Z"))).toBeCloseTo(2451545.0, 6);
  });
});
