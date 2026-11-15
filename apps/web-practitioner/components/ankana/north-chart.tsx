import type { HouseCell } from "@/lib/api/chart-views";

const FONT = "var(--font-urbanist), Urbanist, sans-serif";

/** Label anchor (x, y) per house in the 372px north chart, from Paper U05. */
const LABEL: Record<number, [number, number]> = {
  1: [186, 71], 2: [93, 18.9], 3: [30.9, 81], 4: [93, 164], 5: [30.9, 267], 6: [93, 329.1],
  7: [186, 257], 8: [279, 329.1], 9: [341.1, 267], 10: [279, 164], 11: [341.1, 81], 12: [279, 18.9],
};

function chunk<T>(items: T[], n: number) {
  const out: T[][] = [];
  for (let i = 0; i < items.length; i += n) out.push(items.slice(i, i + n));
  return out;
}

/** North-style D1 chart. House 1 is the top diamond; small numbers are sign numbers. */
export function NorthChart({ houses, ascLabel, size = 372 }: { houses: HouseCell[]; ascLabel: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 372 372" className="inline-block max-w-full shrink-0" role="img" aria-label="Rashi chart, north style">
      <path d="M186 0.8 L279 93 L186 186 L93 93 Z" fill="var(--accent-tint)" />
      <g fill="none" stroke="var(--text-primary)" strokeWidth="1.6" strokeLinejoin="round">
        <rect x="0.8" y="0.8" width="370.4" height="370.4" />
        <path d="M0.8 0.8 L371.2 371.2 M371.2 0.8 L0.8 371.2" />
        <path d="M186 0.8 L371.2 186 L186 371.2 L0.8 186 Z" />
      </g>
      {houses.map((h) => {
        const [x, y] = LABEL[h.house]!;
        const lagna = h.house === 1;
        const rows = chunk(h.planets, 2);
        return (
          <g key={h.house}>
            <text x={x} y={y} textAnchor="middle" fontFamily={FONT} fontWeight={600} fontSize={12} fill={lagna ? "var(--accent-hover)" : "var(--text-soft)"}>
              {h.sign}
            </text>
            {rows.map((r, i) => (
              <text
                key={i}
                x={x}
                y={y + (lagna ? 20 : 18) + i * 17}
                textAnchor="middle"
                fontFamily={FONT}
                fontWeight={700}
                fontSize={16}
                fill={lagna ? "var(--accent-hover)" : "var(--text-primary)"}
              >
                {r.join(" ")}
              </text>
            ))}
          </g>
        );
      })}
      <text x="186" y="124" textAnchor="middle" fontFamily={FONT} fontWeight={700} fontSize={11} fill="var(--accent-hover)">
        {ascLabel}
      </text>
    </svg>
  );
}

/** South-style D1 chart: fixed signs, Pisces top-left going clockwise. */
const SOUTH_CELLS: Array<[number, number]> = [
  // sign index -> [col, row]
  [1, 0], [2, 0], [3, 0], [3, 1], [3, 2], [3, 3], [2, 3], [1, 3], [0, 3], [0, 2], [0, 1], [0, 0],
];

export function SouthChart({ houses, lagnaSign, size = 372 }: { houses: HouseCell[]; lagnaSign: number; size?: number }) {
  const bySign = new Map(houses.map((h) => [h.sign - 1, h]));
  const cell = 372 / 4;
  return (
    <svg width={size} height={size} viewBox="0 0 372 372" className="inline-block max-w-full shrink-0" role="img" aria-label="Rashi chart, south style">
      <rect x="0.8" y="0.8" width="370.4" height="370.4" fill="none" stroke="var(--text-primary)" strokeWidth="1.6" />
      {SOUTH_CELLS.map(([c, r], signIdx) => {
        const h = bySign.get(signIdx);
        const lagna = signIdx === lagnaSign;
        return (
          <g key={signIdx}>
            <rect x={c * cell} y={r * cell} width={cell} height={cell} fill={lagna ? "var(--accent-tint)" : "none"} stroke="var(--text-primary)" strokeWidth="1.6" />
            <text x={c * cell + 8} y={r * cell + 16} fontFamily={FONT} fontWeight={600} fontSize={11} fill="var(--text-soft)">
              {signIdx + 1}
            </text>
            {chunk(h?.planets ?? [], 2).map((row, i) => (
              <text key={i} x={c * cell + cell / 2} y={r * cell + cell / 2 + 6 + i * 17 - ((chunk(h?.planets ?? [], 2).length - 1) * 17) / 2} textAnchor="middle" fontFamily={FONT} fontWeight={700} fontSize={15} fill={lagna ? "var(--accent-hover)" : "var(--text-primary)"}>
                {row.join(" ")}
              </text>
            ))}
          </g>
        );
      })}
    </svg>
  );
}
