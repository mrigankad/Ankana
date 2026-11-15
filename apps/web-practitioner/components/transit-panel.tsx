import type { TransitEvent, TransitSnapshot } from "@astro/astrology-core";
import { AlertTriangle, CalendarClock, Radar, RotateCcw } from "lucide-react";

function formatDate(iso: string): string {
  const d = new Date(iso.slice(0, 10) + "T00:00:00");
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function TransitPanel({
  snapshot,
  timeline,
}: {
  snapshot: TransitSnapshot;
  timeline: TransitEvent[];
}) {
  return (
    <section className="nk-card" aria-label="Transits" id="transits">
      <h2 className="nk-h2"><Radar size={16} aria-hidden /> Transits (Gochar)</h2>
      <p className="nk-muted">
        Sky positions on{" "}
        <span className="data">{formatDate(snapshot.date)}</span>, read against
        the natal chart.
      </p>

      {snapshot.sadeSati.active ? (
        <p className="nk-sade-sati"><AlertTriangle size={14} aria-hidden />{" "}
          Sade Sati active, {snapshot.sadeSati.phase} phase.{" "}
          <span className="data">{snapshot.sadeSati.evidence[1]}</span>
        </p>
      ) : null}

      <div className="nk-table-wrap">
        <table className="nk-table">
          <thead>
            <tr>
              <th>Planet</th>
              <th>Transit sign</th>
              <th>Nakshatra</th>
              <th>House from lagna</th>
              <th>House from Moon</th>
              <th>Motion</th>
            </tr>
          </thead>
          <tbody>
            {snapshot.planets.map((planet) => (
              <tr key={planet.planet} id={`transit-${planet.planet}`}>
                <td className="nk-planet">{planet.planet}</td>
                <td>{planet.signName}</td>
                <td>{planet.nakshatra}</td>
                <td className="data">{planet.houseFromLagna}</td>
                <td className="data">{planet.houseFromMoon}</td>
                <td>
                  {planet.retrograde ? (
                    <span className="nk-badge nk-badge-ink"><RotateCcw size={11} aria-hidden /> retrograde</span>
                  ) : (
                    <span className="nk-badge nk-badge-muted">direct</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {timeline.length ? (
        <>
          <h3 className="nk-subhead nk-h2"><CalendarClock size={14} aria-hidden /> Upcoming events</h3>
          <ul className="nk-event-list">
            {timeline.slice(0, 18).map((event) => (
              <li key={`${event.planet}-${event.date}-${event.kind}`}>
                <span className="data">{formatDate(event.date)}</span>{" "}
                {event.detail}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
