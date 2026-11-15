/** Compact north-style kundali used on consult tiles (Paper U01). House 1 is the top diamond. */
const POS: Record<number, [number, number]> = {
  1: [48, 27], 2: [24, 11], 3: [8, 27], 4: [24, 51], 5: [8, 75], 6: [24, 91],
  7: [48, 75], 8: [72, 91], 9: [88, 75], 10: [72, 51], 11: [88, 27], 12: [72, 11],
};

const FONT = "var(--font-urbanist), Urbanist, sans-serif";

export function MiniKundali({
  houses,
  wash = "var(--surface-2)",
  size = 96,
}: {
  houses: Record<number, string[]>;
  wash?: string;
  size?: number;
}) {
  return (
    <svg width={size} height={size} viewBox="0 0 96 96" className="shrink-0" aria-hidden>
      <path d="M48 0.7 L72 24 L48 48 L24 24 Z" fill={wash} />
      <g fill="none" stroke="var(--text-primary)" strokeWidth="1.4" strokeLinejoin="round">
        <rect x="0.7" y="0.7" width="94.6" height="94.6" />
        <path d="M0.7 0.7 L95.3 95.3 M95.3 0.7 L0.7 95.3" />
        <path d="M48 0.7 L95.3 48 L48 95.3 L0.7 48 Z" />
      </g>
      {Object.entries(houses).flatMap(([h, planets]) => {
        const [x, y] = POS[Number(h)]!;
        return planets.map((p, i) => {
          const dy = (i - (planets.length - 1) / 2) * 9;
          return (
            <text
              key={`${h}-${p}`}
              x={x}
              y={y + dy}
              textAnchor="middle"
              dominantBaseline="central"
              fontFamily={FONT}
              fontWeight={700}
              fontSize={Number(h) === 1 ? 9 : 8}
              fill={Number(h) === 1 ? "var(--accent-hover)" : "var(--text-primary)"}
            >
              {p}
            </text>
          );
        });
      })}
    </svg>
  );
}

/** Matching tile glyph: two overlaid charts (Paper U01 fourth tile). */
export function MatchGlyph({ size = 96 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" className="shrink-0" aria-hidden>
      <path d="M60 4 L88 32 L60 60 L32 32 Z" fill="var(--rule)" />
      <rect x="4" y="4" width="112" height="112" fill="none" stroke="var(--text-primary)" strokeWidth="1.4" />
      <path d="M60 4 L116 60 L60 116 L4 60 Z M4 4 L116 116 M116 4 L4 116" fill="none" stroke="var(--text-primary)" strokeWidth="0.9" />
      <text x="60" y="38" textAnchor="middle" fontFamily={FONT} fontSize="11" fontWeight="700" fill="var(--text-primary)">Ju Ma</text>
      <text x="98" y="62" textAnchor="middle" fontFamily={FONT} fontSize="9" fill="var(--text-primary)">Sa</text>
    </svg>
  );
}
