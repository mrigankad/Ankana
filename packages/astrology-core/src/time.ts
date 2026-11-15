const MS_PER_MINUTE = 60_000;

function zoneOffsetMinutes(timezoneName: string, utcInstant: Date): number {
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone: timezoneName,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

  const parts = Object.fromEntries(
    formatter.formatToParts(utcInstant).map((part) => [part.type, part.value]),
  );

  const wallClockAsUtc = Date.UTC(
    Number(parts.year),
    Number(parts.month) - 1,
    Number(parts.day),
    Number(parts.hour) % 24,
    Number(parts.minute),
    Number(parts.second),
  );

  return (wallClockAsUtc - utcInstant.getTime()) / MS_PER_MINUTE;
}

export function toUtcDate(
  birthDate: string,
  birthTime: string,
  timezoneName: string,
): Date {
  const [year, month, day] = birthDate.split("-").map(Number);
  const [hour, minute] = birthTime.split(":").map(Number);

  const naiveUtc = Date.UTC(year, month - 1, day, hour, minute, 0);

  // Two passes converge for all fixed-offset instants and DST edges,
  // because the second probe evaluates the offset at the candidate instant.
  let candidate = new Date(naiveUtc);
  for (let i = 0; i < 2; i += 1) {
    const offset = zoneOffsetMinutes(timezoneName, candidate);
    candidate = new Date(naiveUtc - offset * MS_PER_MINUTE);
  }

  return candidate;
}

export function julianDay(date: Date): number {
  return date.getTime() / 86_400_000 + 2_440_587.5;
}
