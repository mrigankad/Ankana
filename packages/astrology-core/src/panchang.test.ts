import { describe, expect, it } from "vitest";

import { computePanchang } from "./panchang";

describe("computePanchang", () => {
  it("returns Shukla Pratipada just after the new moon", () => {
    const panchang = computePanchang(10, 15, 0);
    expect(panchang.tithi.name).toBe("Pratipada");
    expect(panchang.tithi.paksha).toBe("shukla");
    expect(panchang.tithi.index).toBe(1);
  });

  it("returns Purnima at full moon", () => {
    const panchang = computePanchang(10, 10 + 179, 1);
    expect(panchang.tithi.name).toBe("Purnima");
    expect(panchang.tithi.index).toBe(15);
  });

  it("returns Amavasya just before the new moon", () => {
    const panchang = computePanchang(10, 10 + 359, 2);
    expect(panchang.tithi.name).toBe("Amavasya");
    expect(panchang.tithi.paksha).toBe("krishna");
  });

  it("starts the karana cycle with Kimstughna", () => {
    expect(computePanchang(0, 3, 0).karana.name).toBe("Kimstughna");
    expect(computePanchang(0, 9, 0).karana.name).toBe("Bava");
    expect(computePanchang(0, 359, 0).karana.name).toBe("Naga");
  });

  it("computes the nitya yoga from the sum of longitudes", () => {
    expect(computePanchang(5, 5, 0).yoga.name).toBe("Vishkumbha");
    expect(computePanchang(10, 10 / 3 + 10 / 3, 0).yoga.index).toBe(2);
  });

  it("names the vara from the weekday", () => {
    expect(computePanchang(0, 0, 4).vara.name).toBe("Guruvara");
  });

  it("includes the moon nakshatra", () => {
    const panchang = computePanchang(0, 40.5, 0);
    expect(panchang.moonNakshatra.name).toBe("Rohini");
  });
});
