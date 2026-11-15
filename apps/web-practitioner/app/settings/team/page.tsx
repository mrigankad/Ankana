"use client";

import { TeamSettings } from "@/components/ankana/team-settings";
import { Topbar } from "@/components/ankana/topbar";

export default function Page() {
  return (
    <>
      <Topbar crumbs={[{ label: "Settings" }, { label: "Team" }]} />
      <TeamSettings />
    </>
  );
}
