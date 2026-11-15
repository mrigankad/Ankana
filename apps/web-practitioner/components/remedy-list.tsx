import type { Remedy, RemedyKind } from "@astro/rule-engine";
import {
  AlertTriangle,
  Gem,
  HandHeart,
  HeartPulse,
  Leaf,
  Music4,
} from "lucide-react";

const KIND_META: Record<RemedyKind, { label: string; Icon: typeof Gem }> = {
  mantra: { label: "Mantra", Icon: Music4 },
  daan: { label: "Charity", Icon: HandHeart },
  fasting: { label: "Observance", Icon: Leaf },
  lifestyle: { label: "Lifestyle", Icon: HeartPulse },
  gemstone: { label: "Gemstone", Icon: Gem },
  rudraksha: { label: "Rudraksha", Icon: Gem },
};

export function RemedyList({ remedies }: { remedies: Remedy[] }) {
  return (
    <section className="nk-card" aria-label="Remedies" id="remedies">
      <h2 className="nk-h2">
        <HandHeart size={16} aria-hidden /> Suggested Remedies
      </h2>
      {remedies.length === 0 ? (
        <p className="nk-muted">
          No planet in this chart is weak or afflicted enough to call for
          remediation.
        </p>
      ) : (
        <div className="nk-remedy-grid">
          {remedies.map((remedy) => {
            const { label, Icon } = KIND_META[remedy.kind];
            return (
              <article
                key={`${remedy.planet}-${remedy.kind}-${remedy.title}`}
                className="nk-remedy"
              >
                <div className="nk-remedy-head">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`/icons3d/remedies/${remedy.kind === "lifestyle" ? "lotus" : remedy.kind}.webp`}
                    width={30}
                    height={30}
                    alt=""
                    aria-hidden
                    className="h-[30px] w-[30px] object-contain"
                  />
                  <span className="nk-badge nk-badge-ink">{label}</span>
                  <span className="nk-planet">{remedy.planet}</span>
                  <span
                    className={
                      remedy.strengthOfRecommendation === "strong"
                        ? "nk-badge nk-badge-ink"
                        : "nk-badge nk-badge-muted"
                    }
                  >
                    {remedy.strengthOfRecommendation}
                  </span>
                </div>
                <h3>{remedy.title}</h3>
                <p>{remedy.practice}</p>
                <p className="nk-muted">{remedy.rationale}</p>
                <details>
                  <summary>Chart evidence</summary>
                  <ul>
                    {remedy.evidence.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </details>
                {remedy.cautions.length > 0 ? (
                  <div className="nk-remedy-cautions">
                    <AlertTriangle size={13} aria-hidden />
                    <ul>
                      {remedy.cautions.map((caution) => (
                        <li key={caution}>{caution}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      )}
      <p className="nk-hint">
        Remedies are traditional practices offered for reflection - never a
        substitute for medical, legal, or financial action.
      </p>
    </section>
  );
}
