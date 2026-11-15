declare module "tz-lookup" {
  /** Returns the IANA timezone name for a coordinate pair. */
  export default function tzLookup(latitude: number, longitude: number): string;
}
