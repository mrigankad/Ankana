import { notFound } from "next/navigation";

import { DesignShowcase } from "./showcase";

export const metadata = { title: "Ankana design system" };

/** Dev-only component gallery. 404s in production builds. */
export default function DesignPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <DesignShowcase />;
}
