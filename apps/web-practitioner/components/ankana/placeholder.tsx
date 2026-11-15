import { Topbar } from "@/components/ankana/topbar";

export function SectionPlaceholder({ title, note }: { title: string; note: string }) {
  return (
    <>
      <Topbar crumbs={[{ label: title }]} />
      <div className="flex flex-col gap-1 px-6 py-9 lg:px-10">
        <h1 className="m-0 text-[32px] font-bold leading-10 tracking-[-0.02em] text-ink">{title}</h1>
        <p className="m-0 text-[16px] leading-5 text-body">{note}</p>
      </div>
    </>
  );
}
