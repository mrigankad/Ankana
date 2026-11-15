import type { ReactNode } from "react";

/** 16px line glyphs from the Paper shell. Stroke follows `color`. */
const PATHS: Record<string, ReactNode> = {
  home: <path d="M2 7 L8 2 L14 7 V14 H2 Z" strokeLinejoin="round" />,
  flag: <path d="M3 14 V2 H12 L10 5 L12 8 H3" strokeLinejoin="round" />,
  people: (
    <>
      <circle cx="6" cy="5" r="2.6" />
      <path d="M1.5 14 C2 10.5 10 10.5 10.5 14" />
      <path d="M11 3 A2.4 2.4 0 0 1 11 8 M12 10.5 C13.5 11 14.3 12.3 14.5 14" />
    </>
  ),
  calendar: (
    <>
      <rect x="2" y="3" width="12" height="11" rx="2" />
      <path d="M2 7 H14 M5 1.5 V4 M11 1.5 V4" />
    </>
  ),
  book: <path d="M3 2 H11 A2 2 0 0 1 13 4 V14 H5 A2 2 0 0 1 3 12 Z M3 12 A2 2 0 0 1 5 10 H13" strokeLinejoin="round" />,
  heart: <path d="M8 14 C3 10 2 7 4 4.5 C5.5 3 7 3.5 8 5 C9 3.5 10.5 3 12 4.5 C14 7 13 10 8 14 Z" strokeLinejoin="round" />,
  doc: (
    <>
      <rect x="3" y="1.5" width="10" height="13" rx="1.5" />
      <path d="M5.5 5 H10.5 M5.5 8 H10.5 M5.5 11 H8.5" />
    </>
  ),
  gear: (
    <>
      <circle cx="8" cy="8" r="2.5" />
      <path d="M8 1.5 V3.5 M8 12.5 V14.5 M1.5 8 H3.5 M12.5 8 H14.5 M3.4 3.4 L4.8 4.8 M11.2 11.2 L12.6 12.6 M3.4 12.6 L4.8 11.2 M11.2 4.8 L12.6 3.4" />
    </>
  ),
  search: (
    <>
      <circle cx="7" cy="7" r="5" />
      <path d="M11 11 L14 14" />
    </>
  ),
  bell: <path d="M4 11 V7 A4 4 0 0 1 12 7 V11 L13 12.5 H3 Z M6.5 14 H9.5" strokeLinejoin="round" />,
  menu: <path d="M2 4 H14 M2 8 H14 M2 12 H14" />,
  device: (
    <>
      <rect x="1.5" y="2.5" width="10" height="7.5" rx="1.2" />
      <path d="M4 13 H9" />
      <rect x="11" y="6" width="3.5" height="7.5" rx="0.8" />
    </>
  ),
  building: (
    <>
      <path d="M2.5 14 V3.5 L8 1.8 V14 M8 5.5 H13.5 V14 M1.5 14 H14.5" strokeLinejoin="round" />
      <path d="M4.5 6 H6 M4.5 9 H6 M10 8.5 H11.5 M10 11 H11.5" />
    </>
  ),
  brush: (
    <>
      <path d="M13.8 2.2 L7.5 8.5" />
      <path d="M7.2 8.8 C5 8.3 3.2 9.8 3.4 12 C3.5 13 2.8 13.8 2 14 C5 14.6 8.2 13.2 7.2 8.8 Z" strokeLinejoin="round" />
    </>
  ),
  wallet: (
    <>
      <rect x="1.5" y="3.5" width="13" height="10" rx="2" />
      <path d="M10.5 8.5 H14.5 M4 3.5 L11 1.5 L11.6 3.5" strokeLinejoin="round" />
    </>
  ),
  sliders: <path d="M2 4.5 H9 M12 4.5 H14 M2 11.5 H4 M7 11.5 H14 M10.5 2.8 V6.2 M5.5 9.8 V13.2" />,
};

export type GlyphName = keyof typeof PATHS;

export function Glyph({
  name,
  size = 16,
  color = "var(--text-body)",
  stroke = 1.6,
}: {
  name: GlyphName;
  size?: number;
  color?: string;
  stroke?: number;
}) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={stroke} className="shrink-0" aria-hidden>
      {PATHS[name]}
    </svg>
  );
}
