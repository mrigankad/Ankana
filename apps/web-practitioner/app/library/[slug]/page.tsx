import { EngineSettings } from "@/components/ankana/engine-settings";
import { LalKitabLibrary, RemediesLibrary, ReportTemplatesLibrary } from "@/components/ankana/library-pages";
import { SectionPlaceholder } from "@/components/ankana/placeholder";
import { Topbar } from "@/components/ankana/topbar";

const TITLES: Record<string, string> = {
  "lal-kitab": "Lal Kitab",
  remedies: "Remedies",
  "report-templates": "Report templates",
  engine: "Engine & models",
};

export default async function LibraryPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (slug === "engine") {
    return (
      <>
        <Topbar crumbs={[{ label: "Library" }, { label: TITLES.engine }]} />
        <EngineSettings />
      </>
    );
  }
  if (slug === "lal-kitab") return <LalKitabLibrary />;
  if (slug === "remedies") return <RemediesLibrary />;
  if (slug === "report-templates") return <ReportTemplatesLibrary />;
  return <SectionPlaceholder title={TITLES[slug] ?? "Library"} note="This part of the library is being built." />;
}
