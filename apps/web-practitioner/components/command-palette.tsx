"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { LayoutDashboard, Plus, UserRound, Users } from "lucide-react";

function getApiBaseUrl() {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:3001";
}

interface ClientHit {
  id: string;
  fullName: string;
  latestChartRequest: { id: string; status: string } | null;
}

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const [clients, setClients] = useState<ClientHit[]>([]);

  useEffect(() => {
    if (!open) {
      return;
    }
    let cancelled = false;
    fetch(`${getApiBaseUrl()}/api/v1/clients`)
      .then(async (response) => {
        if (!response.ok) return;
        const payload = (await response.json()) as { clients: ClientHit[] };
        if (!cancelled) setClients(payload.clients);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [open]);

  function go(path: string) {
    onOpenChange(false);
    router.push(path);
  }

  return (
    <Command.Dialog
      open={open}
      onOpenChange={onOpenChange}
      label="Command palette"
      className="nk-cmdk"
    >
      <Command.Input placeholder="Search clients or jump to…" />
      <Command.List className="nk-scroll">
        <Command.Empty>No results.</Command.Empty>
        <Command.Group heading="Go to">
          <Command.Item onSelect={() => go("/")}>
            <LayoutDashboard size={15} aria-hidden /> Dashboard
          </Command.Item>
          <Command.Item onSelect={() => go("/clients")}>
            <Users size={15} aria-hidden /> Clients
          </Command.Item>
          <Command.Item onSelect={() => go("/clients/new")}>
            <Plus size={15} aria-hidden /> New chart
          </Command.Item>
        </Command.Group>
        {clients.length > 0 ? (
          <Command.Group heading="Clients">
            {clients.slice(0, 8).map((client) => (
              <Command.Item
                key={client.id}
                value={`client ${client.fullName}`}
                onSelect={() => go(`/clients/${client.id}`)}
              >
                <UserRound size={15} aria-hidden /> {client.fullName}
              </Command.Item>
            ))}
          </Command.Group>
        ) : null}
      </Command.List>
    </Command.Dialog>
  );
}
