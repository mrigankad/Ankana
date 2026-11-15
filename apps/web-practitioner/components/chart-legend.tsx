import type { ReactNode } from "react";

export type ChartLegendItem = {
  id: string;
  label: string;
  /** Optional short clarification shown after the label */
  hint?: string;
  /** Visual token: CSS class on a swatch, or custom node */
  swatchClassName?: string;
  swatch?: ReactNode;
};

type ChartLegendProps = {
  title?: string;
  items: ChartLegendItem[];
  className?: string;
};

export function ChartLegend({
  title = "Legend",
  items,
  className,
}: ChartLegendProps) {
  return (
    <div
      className={["nk-chart-legend", className].filter(Boolean).join(" ")}
      role="group"
      aria-label={title}
    >
      <p className="nk-chart-legend-title">{title}</p>
      <ul className="nk-chart-legend-list">
        {items.map((item) => (
          <li key={item.id} className="nk-chart-legend-item">
            {item.swatch ? (
              <span className="nk-chart-legend-swatch-slot" aria-hidden>
                {item.swatch}
              </span>
            ) : (
              <i
                className={[
                  "nk-chart-legend-swatch",
                  item.swatchClassName,
                ]
                  .filter(Boolean)
                  .join(" ")}
                aria-hidden
              />
            )}
            <span className="nk-chart-legend-label">
              {item.label}
              {item.hint ? (
                <span className="nk-chart-legend-hint"> {item.hint}</span>
              ) : null}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
