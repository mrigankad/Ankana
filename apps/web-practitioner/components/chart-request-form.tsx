"use client";

interface ChartRequestFormProps {
  disabled: boolean;
}

/** Legacy submit control - intake now embeds the primary CTA. */
export function ChartRequestForm({ disabled }: ChartRequestFormProps) {
  return (
    <button disabled={disabled} type="submit" className="nk-btn nk-btn-primary">
      Generate Chart
    </button>
  );
}
