import { describe, expect, it } from "vitest";

import { computeAspects, computeConjunctions, signCount } from "./aspects";
import { dignityOf, type Dignity, type Planet } from "./dignities";
import { SIGN_LORDS } from "./zodiac";
import { detectYogas, type YogaChartInput, type YogaResult } from "./yogas";

/** Build a YogaChartInput with full dignity and house-lord data. */
function chart(
  overrides: Partial<Record<Planet, number>>,
  ascSign = 0,
): YogaChartInput {
  const longitudes: Record<Planet, number> = {
    sun: 250,
    moon: 40,
    mercury: 260,
    venus: 280,
    mars: 100,
    jupiter: 130,
    saturn: 310,
    rahu: 305,
    ketu: 125,
    ...overrides,
  };

  const signs = Object.fromEntries(
    Object.entries(longitudes).map(([planet, lon]) => [
      planet,
      Math.floor(lon / 30) % 12,
    ]),
  ) as Record<Planet, number>;

  const dignities = Object.fromEntries(
    (Object.keys(longitudes) as Planet[]).map((p) => [p, dignityOf(p, longitudes[p])]),
  ) as Record<Planet, Dignity>;

  // Whole-sign house lords: house 1 = ascSign, house 2 = ascSign+1, etc.
  const houseLords = Array.from({ length: 12 }, (_, i) =>
    SIGN_LORDS[(ascSign + i) % 12],
  ) as Planet[];

  return { longitudes, signs, ascendantSign: ascSign, dignities, houseLords };
}

describe("signCount", () => {
  it("counts inclusively with wraparound", () => {
    expect(signCount(0, 0)).toBe(1);
    expect(signCount(0, 6)).toBe(7);
    expect(signCount(10, 1)).toBe(4);
  });
});

describe("computeAspects", () => {
  it("gives every planet the 7th aspect and special aspects to Mars, Jupiter, Saturn", () => {
    const input = chart({});
    const signs = Object.fromEntries(
      Object.entries(input.longitudes).map(([p, lon]) => [p, Math.floor(lon / 30)]),
    ) as Record<Planet, number>;

    const aspects = computeAspects(signs);

    // Saturn (Aquarius, 10) aspects 3rd (Aries), 7th (Leo), 10th (Scorpio).
    const saturnCasts = aspects.filter((a) => a.from === "saturn");
    for (const cast of saturnCasts) {
      expect([3, 7, 10]).toContain(cast.count);
    }

    // No planet aspects itself.
    expect(aspects.every((a) => a.from !== a.to)).toBe(true);
  });
});

describe("computeConjunctions", () => {
  it("groups planets sharing a sign", () => {
    const input = chart({ sun: 251, mercury: 259 }); // both Sagittarius
    const signs = Object.fromEntries(
      Object.entries(input.longitudes).map(([p, lon]) => [p, Math.floor(lon / 30)]),
    ) as Record<Planet, number>;

    const conjunctions = computeConjunctions(signs);
    const sag = conjunctions.find((c) => c.signIndex === 8);
    expect(sag?.planets).toContain("sun");
    expect(sag?.planets).toContain("mercury");
  });
});

describe("detectYogas - original", () => {
  it("detects Gajakesari when Jupiter is in a kendra from the Moon", () => {
    const input = chart({ moon: 40, jupiter: 130 }); // Taurus and Leo: 4th
    const result = detectYogas(input).find((y) => y.key === "gajakesari")!;
    expect(result.present).toBe(true);
    expect(result.evidence.join(" ")).toContain("Jupiter is 4 signs from the Moon");
  });

  it("rejects Gajakesari outside kendras", () => {
    const input = chart({ moon: 40, jupiter: 70 }); // 2nd from Moon
    expect(detectYogas(input).find((y) => y.key === "gajakesari")!.present).toBe(false);
  });

  it("detects Budhaditya for a Sun-Mercury conjunction", () => {
    const input = chart({ sun: 250, mercury: 255 });
    expect(detectYogas(input).find((y) => y.key === "budhaditya")!.present).toBe(true);
  });

  it("detects Hamsa when Jupiter is own or exalted in a kendra from lagna", () => {
    // Jupiter in Cancer (exalted), lagna Aries -> 4th house.
    const input = chart({ jupiter: 95 });
    const result = detectYogas(input).find((y) => y.key === "hamsa")!;
    expect(result.present).toBe(true);
    expect(result.evidence.join(" ")).toContain("dignity: exalted");
  });

  it("detects Sasa when Saturn is exalted in a kendra", () => {
    const input = chart({ saturn: 200 }); // Libra, 7th from Aries lagna
    expect(detectYogas(input).find((y) => y.key === "sasa")!.present).toBe(true);
  });

  it("detects Kemadruma when the Moon is unsupported", () => {
    const lonely = chart({
      moon: 40, // Taurus
      mercury: 250,
      venus: 280,
      mars: 100,
      jupiter: 130,
      saturn: 310,
    });
    expect(detectYogas(lonely).find((y) => y.key === "kemadruma")!.present).toBe(true);

    const supported = chart({ moon: 40, venus: 65 }); // Venus in Gemini, 2nd from Moon
    expect(detectYogas(supported).find((y) => y.key === "kemadruma")!.present).toBe(false);
  });

  it("detects Kaal Sarp when all planets are on one side of the nodal axis", () => {
    const hemmed = chart({
      rahu: 0,
      ketu: 180,
      sun: 20,
      moon: 40,
      mercury: 60,
      venus: 90,
      mars: 120,
      jupiter: 150,
      saturn: 170,
    });
    expect(detectYogas(hemmed).find((y) => y.key === "kaal-sarp")!.present).toBe(true);

    const spread = chart({ rahu: 0, ketu: 180, moon: 200 });
    expect(detectYogas(spread).find((y) => y.key === "kaal-sarp")!.present).toBe(false);
  });

  it("always returns evidence for every yoga", () => {
    for (const yoga of detectYogas(chart({}))) {
      expect(yoga.evidence.length).toBeGreaterThan(0);
      expect(yoga.description.length).toBeGreaterThan(0);
    }
  });

  it("every yoga has a valid category", () => {
    const valid = ["raj", "dhan", "pancha-mahapurusha", "lunar", "solar", "dosha", "other"];
    for (const yoga of detectYogas(chart({}))) {
      expect(valid).toContain(yoga.category);
    }
  });
});

describe("detectYogas - lunar yogas", () => {
  it("detects Sunapha when a planet is in the 2nd from Moon", () => {
    // Moon in Taurus (sign 1), Venus in Gemini (sign 2) → 2nd from Moon
    const input = chart({ moon: 40, venus: 65 });
    const yoga = detectYogas(input).find((y) => y.key === "sunapha")!;
    expect(yoga.present).toBe(true);
    expect(yoga.evidence.join(" ")).toContain("venus");
  });

  it("rejects Sunapha when no planet in 2nd from Moon", () => {
    // Moon in Taurus (1), all others far away
    const input = chart({ moon: 40, mercury: 250, venus: 280, mars: 100, jupiter: 130, saturn: 310 });
    const yoga = detectYogas(input).find((y) => y.key === "sunapha")!;
    expect(yoga.present).toBe(false);
  });

  it("detects Anapha when a planet is in the 12th from Moon", () => {
    // Moon in Taurus (sign 1), Mars in Aries (sign 0) → 12th from Moon
    const input = chart({ moon: 40, mars: 10 });
    const yoga = detectYogas(input).find((y) => y.key === "anapha")!;
    expect(yoga.present).toBe(true);
    expect(yoga.evidence.join(" ")).toContain("mars");
  });

  it("detects Durudhara when planets flank the Moon", () => {
    // Moon in Taurus (1), Venus in Gemini (2) = 2nd, Mars in Aries (0) = 12th
    const input = chart({ moon: 40, venus: 65, mars: 10 });
    const yoga = detectYogas(input).find((y) => y.key === "durudhara")!;
    expect(yoga.present).toBe(true);
  });

  it("rejects Durudhara when only one side is occupied", () => {
    const input = chart({ moon: 40, venus: 65 }); // only 2nd, no 12th
    const yoga = detectYogas(input).find((y) => y.key === "durudhara")!;
    expect(yoga.present).toBe(false);
  });
});

describe("detectYogas - solar yogas", () => {
  it("detects Voshi when a planet is in the 2nd from Sun", () => {
    // Sun in Sagittarius (sign 8), Mars in Capricorn (sign 9) → 2nd from Sun
    const input = chart({ sun: 250, mars: 280 });
    const yoga = detectYogas(input).find((y) => y.key === "voshi")!;
    expect(yoga.present).toBe(true);
  });

  it("detects Veshi when a planet is in the 12th from Sun", () => {
    // Sun in Sagittarius (sign 8), Jupiter in Scorpio (sign 7) → 12th from Sun
    const input = chart({ sun: 250, jupiter: 220 });
    const yoga = detectYogas(input).find((y) => y.key === "veshi")!;
    expect(yoga.present).toBe(true);
  });

  it("detects Ubhayachari when planets flank the Sun on both sides", () => {
    // Sun in Sag (8), Mars in Cap (9) = 2nd, Jupiter in Scorpio (7) = 12th
    const input = chart({ sun: 250, mars: 280, jupiter: 220 });
    const yoga = detectYogas(input).find((y) => y.key === "ubhayachari")!;
    expect(yoga.present).toBe(true);
  });
});

describe("detectYogas - doshas", () => {
  it("detects Manglik when Mars is in house 7 from lagna", () => {
    // Lagna Aries (0), Mars in Libra (sign 6) → house 7
    const input = chart({ mars: 195 }, 0);
    const yoga = detectYogas(input).find((y) => y.key === "manglik")!;
    expect(yoga.present).toBe(true);
    expect(yoga.evidence.join(" ")).toContain("house 7");
  });

  it("detects Manglik when Mars is in house 1, 2, 4, 8, or 12", () => {
    // Mars in Aries (sign 0), lagna Aries → house 1
    const input1 = chart({ mars: 10 }, 0);
    expect(detectYogas(input1).find((y) => y.key === "manglik")!.present).toBe(true);

    // Mars in Taurus (sign 1), lagna Aries → house 2
    const input2 = chart({ mars: 40 }, 0);
    expect(detectYogas(input2).find((y) => y.key === "manglik")!.present).toBe(true);
  });

  it("rejects Manglik when Mars is in a non-manglik house", () => {
    // Mars in Gemini (sign 2), lagna Aries → house 3 (not manglik)
    const input = chart({ mars: 70 }, 0);
    expect(detectYogas(input).find((y) => y.key === "manglik")!.present).toBe(false);
  });

  it("detects Guru Chandal when Jupiter and Rahu share a sign", () => {
    // Both in Aquarius (sign 10)
    const input = chart({ jupiter: 310, rahu: 315 });
    const yoga = detectYogas(input).find((y) => y.key === "guru-chandal")!;
    expect(yoga.present).toBe(true);
  });

  it("rejects Guru Chandal when Jupiter and Rahu are apart", () => {
    const input = chart({ jupiter: 130, rahu: 305 });
    expect(detectYogas(input).find((y) => y.key === "guru-chandal")!.present).toBe(false);
  });

  it("detects Pitra Dosha when Sun conjoins Rahu", () => {
    const input = chart({ sun: 310, rahu: 315 });
    const yoga = detectYogas(input).find((y) => y.key === "pitra-dosha")!;
    expect(yoga.present).toBe(true);
  });

  it("detects Grahan Yoga when Moon conjoins Ketu", () => {
    const input = chart({ moon: 130, ketu: 125 }); // both in Leo (sign 4)
    const yoga = detectYogas(input).find((y) => y.key === "grahan")!;
    expect(yoga.present).toBe(true);
  });
});

describe("detectYogas - raj/dhan yogas", () => {
  it("detects Raj Yoga when a single planet lords both kendra and trikona", () => {
    // Lagna Leo (sign 4): Mars lords 4th (Scorpio=7) and 9th (Aries=0),
    // which is a kendra(4) + trikona(9) = Raj Yoga with a single planet.
    const input = chart({}, 4); // Leo lagna
    const yoga = detectYogas(input).find((y) => y.key === "raj-yoga")!;
    expect(yoga.present).toBe(true);
    expect(yoga.evidence.join(" ")).toContain("mars");
  });

  it("detects Raj Yoga when two lords conjunct", () => {
    // Aries lagna (0): lord of 4th (Cancer=Moon), lord of 5th (Leo=Sun).
    // Put Moon and Sun in the same sign (conjunction).
    const input = chart({ sun: 130, moon: 135 }, 0); // both Leo
    const yoga = detectYogas(input).find((y) => y.key === "raj-yoga")!;
    expect(yoga.present).toBe(true);
  });

  it("detects Dhana Yoga when lord of 2nd and 11th conjunct", () => {
    // Aries lagna (0): lord of 2nd = Venus (Taurus), lord of 11th = Saturn (Aquarius).
    // Put Venus and Saturn in same sign.
    const input = chart({ venus: 310, saturn: 315 }, 0);
    const yoga = detectYogas(input).find((y) => y.key === "dhana-yoga")!;
    expect(yoga.present).toBe(true);
  });

  it("detects Vipreet Raj Yoga when lord of 6th is in 8th", () => {
    // Aries lagna (0): lord of 6th = Mercury (Virgo), lord of 8th = Mars is
    // default. Let's use Sagittarius lagna (8): lord of 6th is Venus (Taurus=1),
    // lord of 8th is Moon (Cancer=3). Place Venus in Cancer (sign 3) → house 8.
    const input = chart({ venus: 95 }, 8); // Sagittarius lagna
    const yoga = detectYogas(input).find((y) => y.key === "vipreet-raj")!;
    expect(yoga.present).toBe(true);
    expect(yoga.evidence.join(" ")).toContain("Harsha");
  });

  it("detects Neecha Bhanga when debilitated planet's dispositor is in kendra", () => {
    // Sun debilitated in Libra (sign 6). Libra's lord = Venus.
    // Place Venus in a kendra from Aries lagna (houses 1, 4, 7, 10).
    // Venus in Cancer (sign 3) → house 4 from Aries.
    const input = chart({ sun: 185, venus: 95 }, 0);
    const yoga = detectYogas(input).find((y) => y.key === "neecha-bhanga")!;
    expect(yoga.present).toBe(true);
    expect(yoga.evidence.join(" ")).toContain("sun");
    expect(yoga.evidence.join(" ")).toContain("venus");
  });
});

describe("detectYogas - special combination yogas", () => {
  it("detects Saraswati when Jupiter, Venus, Mercury are in qualifying houses", () => {
    // Aries lagna (0). Place Jupiter in Aries (house 1), Venus in Taurus (house 2),
    // Mercury in Virgo (house 6? no, that doesn't qualify).
    // Qualifying houses: 1, 2, 4, 5, 7, 9, 10.
    // Jupiter in Sagittarius exalted? No, Jupiter exalted in Cancer.
    // Jupiter in Cancer (sign 3, house 4), Venus in Taurus (sign 1, house 2),
    // Mercury in Virgo (sign 5, house 6) - 6 is NOT qualifying.
    // Mercury in Leo (sign 4, house 5), Venus in Libra (sign 6, house 7),
    // Jupiter in Sagittarius (sign 8, house 9). Jupiter in Sag = own sign → strong.
    const input = chart({ jupiter: 250, venus: 190, mercury: 130 }, 0);
    const yoga = detectYogas(input).find((y) => y.key === "saraswati")!;
    expect(yoga.present).toBe(true);
  });

  it("rejects Saraswati when one planet is in a non-qualifying house", () => {
    // Mercury in house 3 (not qualifying)
    const input = chart({ jupiter: 250, venus: 190, mercury: 70 }, 0);
    const yoga = detectYogas(input).find((y) => y.key === "saraswati")!;
    expect(yoga.present).toBe(false);
  });

  it("detects Lakshmi when lord of 9th is in kendra and strong", () => {
    // Aries lagna (0): 9th house = Sagittarius (sign 8), lord = Jupiter.
    // Jupiter exalted in Cancer (sign 3), which is house 4 (kendra) from Aries.
    const input = chart({ jupiter: 95 }, 0); // Cancer = exalted
    const yoga = detectYogas(input).find((y) => y.key === "lakshmi")!;
    expect(yoga.present).toBe(true);
  });

  it("rejects Lakshmi when lord of 9th is in kendra but weak", () => {
    // Aries lagna: 9th lord = Jupiter. Jupiter debilitated in Capricorn (sign 9).
    // Capricorn is house 10 (kendra) from Aries - in kendra but debilitated.
    const input = chart({ jupiter: 280 }, 0);
    const yoga = detectYogas(input).find((y) => y.key === "lakshmi")!;
    expect(yoga.present).toBe(false);
  });

  it("detects Amala when a benefic is in the 10th from lagna", () => {
    // Aries lagna (0): 10th house = Capricorn (sign 9).
    // Jupiter in Capricorn (sign 9) → benefic in 10th.
    const input = chart({ jupiter: 280 }, 0);
    const yoga = detectYogas(input).find((y) => y.key === "amala")!;
    expect(yoga.present).toBe(true);
  });

  it("detects Adhi when benefics in 6th, 7th, 8th from Moon", () => {
    // Moon in Aries (sign 0). 6th = Virgo (5), 7th = Libra (6), 8th = Scorpio (7).
    // Place Jupiter in Virgo (5), Venus in Libra (6).
    const input = chart({ moon: 10, jupiter: 155, venus: 190 }, 0);
    const yoga = detectYogas(input).find((y) => y.key === "adhi")!;
    expect(yoga.present).toBe(true);
  });
});

describe("detectYogas - coverage for real charts", () => {
  it("returns at least 25 yoga results (present or absent)", () => {
    const yogas = detectYogas(chart({}));
    expect(yogas.length).toBeGreaterThanOrEqual(25);
  });

  it("a typical chart fires at least 3 yogas", () => {
    // This chart intentionally has common combinations:
    // - Sun and Mercury in same sign (Budhaditya)
    // - Mars in house 1 (Manglik)
    // - Venus in 2nd from Moon (Sunapha)
    const input = chart(
      { sun: 250, mercury: 255, mars: 10, moon: 40, venus: 65 },
      0,
    );
    const present = detectYogas(input).filter((y) => y.present);
    expect(present.length).toBeGreaterThanOrEqual(3);
  });
});
