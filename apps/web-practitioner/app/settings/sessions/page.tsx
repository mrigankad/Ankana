"use client";

import { SessionsSettings } from "@/components/ankana/sessions-settings";
import { Topbar } from "@/components/ankana/topbar";

export default function Page() {
  return (
    <>
      <Topbar crumbs={[{ label: "Settings" }, { label: "Sessions" }]} />
      <SessionsSettings />
    </>
  );
}
