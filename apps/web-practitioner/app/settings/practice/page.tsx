"use client";

import { PracticeSettings } from "@/components/ankana/practice-settings";
import { Topbar } from "@/components/ankana/topbar";

export default function Page() {
  return (
    <>
      <Topbar crumbs={[{ label: "Settings" }, { label: "Practice" }]} />
      <PracticeSettings />
    </>
  );
}
