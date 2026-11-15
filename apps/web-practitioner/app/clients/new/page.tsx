"use client";

import { IntakeForm } from "@/components/ankana/intake-form";
import { Topbar } from "@/components/ankana/topbar";
import { useT } from "@/lib/i18n/provider";

export default function NewChartPage() {
  const t = useT();
  return (
    <>
      <Topbar crumbs={[{ label: "Clients", href: "/clients" }, { label: "New chart" }]} />
      <main className="flex flex-1 flex-col gap-5 px-5 py-7 lg:px-10">
        <div className="flex flex-col gap-1">
          <h1 className="m-0 text-[28px] font-bold leading-[34px] tracking-[-0.02em] text-ink lg:text-[32px] lg:leading-[38px]">{t("New chart")}</h1>
          <p className="m-0 text-[15px] leading-5 text-body">
            {t("Every field is typed and echoed back, so a wrong date or time is caught before the chart is cast.")}
          </p>
        </div>
        <IntakeForm />
      </main>
    </>
  );
}
