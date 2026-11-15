"use client";

import type { LocationSearchResult } from "@astro/shared-types";

interface LocationSearchProps {
  results: LocationSearchResult[];
  onConfirm: (location: LocationSearchResult) => void;
}

export function LocationSearch({ results, onConfirm }: LocationSearchProps) {
  if (!results.length) {
    return (
      <p className="nk-muted">
        No matching places. Try adding the district or state, e.g.
        &ldquo;Raiganj, West Bengal&rdquo;.
      </p>
    );
  }

  return (
    <ul className="nk-loc-list" aria-label="Location matches">
      {results.map((location) => (
        <li key={location.providerPlaceId}>
          <button
            type="button"
            className="nk-loc-option"
            aria-label={`Confirm ${location.displayName}`}
            onClick={() => onConfirm(location)}
          >
            <span className="nk-loc-name">{location.displayName}</span>
            <span className="nk-loc-meta data">
              {location.latitude.toFixed(4)}, {location.longitude.toFixed(4)} ·{" "}
              {location.timezoneName}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
