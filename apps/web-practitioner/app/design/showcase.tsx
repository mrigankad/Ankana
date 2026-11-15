"use client";

import { useState } from "react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CommandDialog, CommandGroup, CommandItem } from "@/components/ui/command";
import { Combobox, MultiSelect, type ComboboxOption } from "@/components/ui/combobox";
import { Checkbox, CheckboxField, RadioCard, RadioGroup, SegmentedControl, Switch } from "@/components/ui/controls";
import {
  Banner, Breadcrumb, EmptyState, FileDrop, LoadMore, Progress, StatusDot, Stepper,
  Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow, TableSkeletonRows,
} from "@/components/ui/data";
import { DateField, TimeField } from "@/components/ui/date-time-fields";
import { ConfirmDialog, Dialog, DialogContent, DialogDescription, DialogFooter, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ToastProvider, useToast } from "@/components/ui/toast";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const AYANAMSA = [
  { value: "lahiri", label: "Lahiri", description: "Indian government standard", group: "Ayanamsa" },
  { value: "raman", label: "Raman", description: "B. V. Raman tradition", group: "Ayanamsa" },
  { value: "kp", label: "Krishnamurti", description: "KP system", group: "Ayanamsa" },
  { value: "fagan", label: "Fagan Bradley", description: "Unavailable", group: "Western", disabled: true },
];

const PLACES: ComboboxOption[] = [
  { value: "kanpur", label: "Kanpur", description: "Uttar Pradesh, India" },
  { value: "kanpur-dehat", label: "Kanpur Dehat", description: "Uttar Pradesh, India" },
  { value: "kannur", label: "Kannur", description: "Kerala, India" },
  { value: "pune", label: "Pune", description: "Maharashtra, India" },
];

const TOPICS: ComboboxOption[] = ["Career", "Marriage", "Health", "Education", "Travel"].map((t) => ({ value: t.toLowerCase(), label: t }));

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="m-0 border-b border-rule pb-2 text-[20px] font-bold text-ink">{title}</h2>
      <div className="flex flex-wrap items-start gap-x-10 gap-y-6">{children}</div>
    </section>
  );
}

function Demo({ label, children, width = 300 }: { label: string; children: React.ReactNode; width?: number }) {
  return (
    <div className="flex flex-col gap-1.5" style={{ width }}>
      <span className="text-[12px] font-bold uppercase tracking-[0.08em] text-accent-text">{label}</span>
      {children}
    </div>
  );
}

function Inner() {
  const toast = useToast();
  const [sel, setSel] = useState("lahiri");
  const [place, setPlace] = useState<string | null>(null);
  const [asyncPlace, setAsyncPlace] = useState<string | null>(null);
  const [topics, setTopics] = useState<string[]>(["career", "marriage"]);
  const [seg, setSeg] = useState("week");
  const [on, setOn] = useState(true);
  const [dob, setDob] = useState("1992-11-14");
  const [tob, setTob] = useState("06:45");
  const [confirm, setConfirm] = useState(false);
  const [palette, setPalette] = useState(false);
  const [rows, setRows] = useState([true, false]);
  const [loading, setLoading] = useState(false);

  return (
    <main className="mx-auto flex max-w-[1180px] flex-col gap-12 px-6 py-12">
      <header>
        <p className="m-0 text-[13px] font-bold uppercase tracking-[0.12em] text-accent-text">Ankana design system</p>
        <h1 className="m-0 text-[40px] font-bold tracking-[-0.02em] text-ink">Components</h1>
        <p className="m-0 mt-1 max-w-[640px] text-[16px] text-body">Every control in its states. Matches Paper page 08. Dev only.</p>
      </header>

      <Section title="Button">
        <Demo label="Variants" width={900}>
          <div className="flex flex-wrap items-center gap-3">
            <Button size="md">Primary</Button>
            <Button size="md" variant="outline">Secondary</Button>
            <Button size="md" variant="ghost">Ghost</Button>
            <Button size="md" variant="destructive">Destructive</Button>
            <Button size="md" variant="danger">Danger</Button>
            <Button size="md" disabled>Disabled</Button>
            <Button size="md" loading={loading} onClick={() => { setLoading(true); setTimeout(() => setLoading(false), 1500); }}>Save</Button>
            <Button size="sm">Small</Button>
            <Button size="lg">Large</Button>
            <Button size="icon" variant="outline" aria-label="Add"><span aria-hidden>+</span></Button>
          </div>
        </Demo>
      </Section>

      <Section title="Input, Textarea">
        <Demo label="Default"><Input placeholder="Client name" aria-label="Client name" /></Demo>
        <Demo label="Error">
          <Field error="Enter a full email address"><Input aria-label="Email" aria-invalid defaultValue="asha@" /></Field>
        </Demo>
        <Demo label="Disabled"><Input aria-label="Locked" disabled defaultValue="Locked" /></Demo>
        <Demo label="Textarea"><Textarea aria-label="Notes" placeholder="Notes for this reading" /></Demo>
      </Section>

      <Section title="Select, Combobox, MultiSelect">
        <Demo label="Select (groups, descriptions, disabled)">
          <Select aria-label="Ayanamsa" value={sel} onValueChange={setSel} options={AYANAMSA} />
        </Demo>
        <Demo label="Select, error"><Select aria-label="Chart style" invalid value="" onValueChange={() => {}} options={AYANAMSA} placeholder="Choose" /></Demo>
        <Demo label="Select, disabled"><Select aria-label="Locked" disabled value="lahiri" onValueChange={() => {}} options={AYANAMSA} /></Demo>
        <Demo label="Combobox (local filter, create)">
          <Combobox aria-label="Place" value={place} onChange={(v) => setPlace(v)} options={PLACES} placeholder="Search a place" onCreate={(q) => ({ value: q.toLowerCase(), label: q })} clearable />
        </Demo>
        <Demo label="Combobox (async)">
          <Combobox
            aria-label="Client"
            value={asyncPlace}
            onChange={(v) => setAsyncPlace(v)}
            placeholder="Find a client"
            loadOptions={async (q) => {
              await new Promise((r) => setTimeout(r, 400));
              return PLACES.filter((p) => p.label.toLowerCase().includes(q.toLowerCase()));
            }}
          />
        </Demo>
        <Demo label="MultiSelect (chips)" width={380}>
          <MultiSelect aria-label="Topics" value={topics} onChange={setTopics} options={TOPICS} placeholder="Add topic" />
        </Demo>
      </Section>

      <Section title="Date and time (typed, no native picker)">
        <Demo label="DateField" width={320}><DateField aria-label="Birth date" value={dob} onChange={setDob} max="2026-11-14" /></Demo>
        <Demo label="DateField, empty" width={320}><DateField aria-label="Date" value="" onChange={() => {}} /></Demo>
        <Demo label="TimeField" width={320}><TimeField aria-label="Birth time" value={tob} onChange={setTob} /></Demo>
        <p className="m-0 self-end text-[13px] text-body">Values: {dob || "none"} / {tob || "none"}</p>
      </Section>

      <Section title="Selection">
        <Demo label="SegmentedControl">
          <SegmentedControl aria-label="Range" value={seg} onValueChange={setSeg} options={[{ value: "day", label: "Day" }, { value: "week", label: "Week" }, { value: "month", label: "Month" }]} />
        </Demo>
        <Demo label="Switch">
          <div className="flex items-center gap-3">
            <Switch aria-label="Lal Kitab" checked={on} onCheckedChange={setOn} />
            <Switch aria-label="Off" />
            <Switch aria-label="Disabled" disabled />
          </div>
        </Demo>
        <Demo label="Checkbox">
          <div className="flex items-center gap-3">
            <Checkbox aria-label="Checked" defaultChecked />
            <Checkbox aria-label="Unchecked" />
            <Checkbox aria-label="Mixed" checked="indeterminate" />
            <Checkbox aria-label="Disabled" disabled />
          </div>
          <CheckboxField label="Send me the chart PDF" description="Delivered to the client email" />
        </Demo>
        <Demo label="RadioCard" width={360}>
          <RadioGroup defaultValue="vedic" className="flex gap-3" aria-label="System">
            <RadioCard value="vedic" title="Vedic" description="Sidereal charts" />
            <RadioCard value="western" title="Western" description="Tropical charts" />
          </RadioGroup>
        </Demo>
      </Section>

      <Section title="Tabs, badges, status, avatar">
        <Demo label="Tabs" width={360}>
          <Tabs defaultValue="chart">
            <TabsList variant="line"><TabsTrigger value="chart">Chart</TabsTrigger><TabsTrigger value="timeline">Timeline</TabsTrigger></TabsList>
            <TabsContent value="chart" className="text-[14px] text-body">Chart content</TabsContent>
            <TabsContent value="timeline" className="text-[14px] text-body">Timeline content</TabsContent>
          </Tabs>
        </Demo>
        <Demo label="Badge, status, avatar" width={360}>
          <div className="flex flex-wrap items-center gap-2">
            <Badge>Accent</Badge><Badge variant="outline">Outline</Badge>
            <StatusDot tone="ok">Online</StatusDot><StatusDot tone="alert">Overdue</StatusDot>
            <Avatar><AvatarFallback>AV</AvatarFallback></Avatar>
          </div>
        </Demo>
        <Demo label="Skeleton, progress, stepper" width={360}>
          <Skeleton className="h-3.5 w-2/3" /><Skeleton className="h-3.5 w-full" />
          <Progress value={64} aria-label="Progress" />
          <Stepper steps={["Details", "Place", "Review"]} current={1} />
        </Demo>
      </Section>

      <Section title="Overlays">
        <Demo label="Dialog">
          <Dialog>
            <DialogTrigger asChild><Button variant="outline" size="md">Open dialog</Button></DialogTrigger>
            <DialogContent>
              <DialogTitle>Rename client</DialogTitle>
              <DialogDescription>Shown on charts and reports.</DialogDescription>
              <Input aria-label="Client name" defaultValue="Asha Verma" />
              <DialogFooter><Button size="md">Save</Button></DialogFooter>
            </DialogContent>
          </Dialog>
        </Demo>
        <Demo label="ConfirmDialog">
          <Button variant="destructive" size="md" onClick={() => setConfirm(true)}>Delete client</Button>
          <ConfirmDialog open={confirm} onOpenChange={setConfirm} title="Delete this client?" description="Their charts and notes move to archive for 30 days." confirmLabel="Delete client" tone="danger" onConfirm={() => toast("Client archived", { tone: "success" })} />
        </Demo>
        <Demo label="Drawer (Sheet)">
          <Sheet>
            <SheetTrigger asChild><Button variant="outline" size="md">Open drawer</Button></SheetTrigger>
            <SheetContent><SheetHeader><SheetTitle>Filters</SheetTitle><SheetDescription>Narrow the client list.</SheetDescription></SheetHeader></SheetContent>
          </Sheet>
        </Demo>
        <Demo label="Popover">
          <Popover><PopoverTrigger asChild><Button variant="outline" size="md">Open popover</Button></PopoverTrigger><PopoverContent><p className="m-0 text-[14px] text-body">Birth time is approximate.</p></PopoverContent></Popover>
        </Demo>
        <Demo label="DropdownMenu">
          <DropdownMenu><DropdownMenuTrigger asChild><Button variant="outline" size="md">Actions</Button></DropdownMenuTrigger>
            <DropdownMenuContent><DropdownMenuItem>Edit client</DropdownMenuItem><DropdownMenuItem>Duplicate</DropdownMenuItem><DropdownMenuItem variant="destructive">Archive</DropdownMenuItem></DropdownMenuContent></DropdownMenu>
        </Demo>
        <Demo label="Tooltip">
          <Tooltip><TooltipTrigger asChild><Button variant="outline" size="md">Hover me</Button></TooltipTrigger><TooltipContent>Copy link</TooltipContent></Tooltip>
        </Demo>
        <Demo label="Toast">
          <Button size="md" onClick={() => toast("Chart saved", { tone: "success" })}>Show toast</Button>
        </Demo>
        <Demo label="Command palette">
          <Button variant="outline" size="md" onClick={() => setPalette(true)}>Open palette</Button>
          <CommandDialog open={palette} onOpenChange={setPalette} placeholder="Search clients, charts, actions">
            <CommandGroup heading="Actions"><CommandItem onSelect={() => setPalette(false)}>New client</CommandItem><CommandItem onSelect={() => setPalette(false)}>Open panchang</CommandItem></CommandGroup>
          </CommandDialog>
        </Demo>
      </Section>

      <Section title="Data">
        <Demo label="Table (sortable, selectable)" width={620}>
          <Table>
            <TableHead>
              <tr>
                <TableHeaderCell className="w-10"><Checkbox aria-label="Select all" checked={rows.every(Boolean) ? true : rows.some(Boolean) ? "indeterminate" : false} onCheckedChange={(c) => setRows(rows.map(() => c === true))} /></TableHeaderCell>
                <TableHeaderCell sortDirection="asc" onSort={() => {}}>Client</TableHeaderCell>
                <TableHeaderCell onSort={() => {}}>Next dasha</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
              </tr>
            </TableHead>
            <TableBody>
              {["Asha Verma", "Rohit Nair"].map((n, i) => (
                <TableRow key={n} selected={rows[i]}>
                  <TableCell><Checkbox aria-label={`Select ${n}`} checked={rows[i]} onCheckedChange={(c) => setRows(rows.map((v, j) => (j === i ? c === true : v)))} /></TableCell>
                  <TableCell className="font-bold">{n}</TableCell><TableCell className="text-body">{i ? "Saturn" : "Jupiter"}</TableCell>
                  <TableCell><StatusDot tone={i ? "muted" : "ok"}>{i ? "Paused" : "Active"}</StatusDot></TableCell>
                </TableRow>
              ))}
              <TableSkeletonRows rows={1} cols={4} />
            </TableBody>
          </Table>
          <LoadMore hasMore onLoadMore={() => toast("Loading more")} />
        </Demo>
        <Demo label="EmptyState" width={420}>
          <Card><EmptyState title="No clients yet" description="Add your first client to cast a chart." action={<Button size="md">New client</Button>} /></Card>
        </Demo>
      </Section>

      <Section title="Feedback and navigation">
        <Demo label="Banner" width={420}>
          <Banner tone="warning" title="Birth time is approximate">Ascendant may shift.</Banner>
          <Banner tone="error" title="Could not save">Try again.</Banner>
          <Banner tone="success">Chart saved.</Banner>
        </Demo>
        <Demo label="Breadcrumb"><Breadcrumb items={[{ label: "Clients", href: "/clients" }, { label: "Asha Verma" }]} /></Demo>
        <Demo label="FileDrop" width={360}><FileDrop onFile={(f) => toast(`Got ${f.name}`)} /></Demo>
      </Section>
    </main>
  );
}

export function DesignShowcase() {
  return (
    <ToastProvider>
      <Inner />
    </ToastProvider>
  );
}
