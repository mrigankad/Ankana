"use client";

import { BillingSettings } from "@/components/ankana/billing-settings";
import { Topbar } from "@/components/ankana/topbar";

export default function BillingPage() {
  return (
    <>
      <Topbar crumbs={[{ label: "Settings" }, { label: "Billing" }]} />
      <BillingSettings />
    </>
  );
}
