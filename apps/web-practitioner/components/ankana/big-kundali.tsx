const FONT = "var(--font-urbanist), Urbanist, sans-serif";

/** [number x, number y, planet y] per house; x is shared. House 1 is the top diamond. */
const SLOTS: Record<number, [number, number, number]> = {
  1: [140, 48, 68],
  2: [70, 11.2, 29.2],
  3: [23.2, 58, 76],
  4: [70, 118, 136],
  5: [23.2, 198, 216],
  6: [70, 244.8, 262.8],
  7: [140, 188, 208],
  8: [210, 244.8, 262.8],
  9: [256.8, 198, 216],
  10: [210, 118, 138],
  11: [256.8, 58, 76],
  12: [210, 11.2, 29.2],
};

/** 280px north-style chart with sign numbers, used by the intake live preview (Paper U04). */
export function BigKundali({
  houses,
  lagnaSign,
  size = 280,
}: {
  houses: Record<number, string[]>;
  /** 1 Aries .. 12 Pisces */
  lagnaSign: number;
  size?: number;
}) {
  return (
    <svg width={size} height={size} viewBox="0 0 280 280" className="shrink-0" role="img" aria-label="Preview of the birth chart">
      <path d="M140 0.8 L210 70 L140 140 L70 70 Z" fill="var(--accent-tint)" />
      <g fill="none" stroke="var(--text-primary)" strokeWidth="1.6" strokeLinejoin="round">
        <rect x="0.8" y="0.8" width="278.4" height="278.4" />
        <path d="M0.8 0.8 L279.2 279.2 M279.2 0.8 L0.8 279.2" />
        <path d="M140 0.8 L279.2 140 L140 279.2 L0.8 140 Z" />
      </g>
      {Array.from({ length: 12 }, (_, i) => i + 1).map((h) => {
        const [x, ny, py] = SLOTS[h]!;
        const sign = ((lagnaSign - 1 + h - 1) % 12) + 1;
        const planets = houses[h]?.join(" ");
        const first = h === 1;
        return (
          <g key={h} textAnchor="middle" fontFamily={FONT}>
            <text x={x} y={ny} fontWeight={600} fontSize={12} fill={first ? "var(--accent-hover)" : "var(--text-soft)"}>
              {sign}
            </text>
            {planets ? (
              <text x={x} y={py} fontWeight={700} fontSize={16} fill={first ? "var(--accent-hover)" : "var(--text-primary)"}>
                {planets}
              </text>
            ) : null}
          </g>
        );
      })}
    </svg>
  );
}
