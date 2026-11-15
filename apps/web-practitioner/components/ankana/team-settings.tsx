"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";

import { Banner, EmptyState } from "@/components/ui/data";
import { SampleBadge } from "@/components/ankana/server-unavailable";
import { isFixtures } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { ConfirmDialog, Dialog, DialogContent, DialogDescription, DialogFooter, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/components/auth/auth-provider";
import { Chip, Panel } from "@/components/ankana/ui";
import * as team from "@/lib/api/team";
import type { ClientOption, Invite, Member, MemberRole, StaffRole } from "@/lib/api/team";
import { problemMessage } from "@/lib/api/v1";
import { useT } from "@/lib/i18n/provider";

const LINK = "h-auto p-0 text-[14px] font-bold no-underline hover:no-underline";
const STAFF: StaffRole[] = ["owner", "astrologer", "assistant"];
const INVITE_ROLES: MemberRole[] = ["astrologer", "assistant", "owner", "client"];

const initials = (m: { name: string | null; email: string | null }) => {
  const parts = (m.name || m.email || "?").trim().split(/[\s@.]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "?") + (parts[1]?.[0] ?? "")).toUpperCase();
};

const daysLeft = (iso: string) => Math.max(0, Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000));

export function InviteDialog({
  open,
  onOpenChange,
  onSent,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onSent: (invite: Invite) => void;
}) {
  const t = useT();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<MemberRole>("astrologer");
  const [clientId, setClientId] = useState("");
  const [clients, setClients] = useState<ClientOption[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setEmail("");
    setRole("astrologer");
    setClientId("");
    setError(null);
  }, [open]);

  useEffect(() => {
    if (open && role === "client" && clients.length === 0) {
      team.listClientOptions().then(setClients).catch(() => setClients([]));
    }
  }, [open, role, clients.length]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (role === "client" && !clientId) {
      setError(t("Choose which client this portal is for."));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onSent(await team.createInvite({ email: email.trim(), role, client_id: role === "client" ? clientId : null }));
      onOpenChange(false);
    } catch (err) {
      setError(problemMessage(err, t("The invitation could not be sent.")));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>{t("Invite someone")}</DialogTitle>
        <DialogDescription>{t("They get an email with a link that works for 7 days and only for that address.")}</DialogDescription>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Field label={t("Email")} htmlFor="invite-email">
            <Input
              id="invite-email"
              type="email"
              autoComplete="off"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.in"
            />
          </Field>
          <Field label={t("Role")} hint={t(team.ROLE_CAN[role])}>
            <Select
              aria-label={t("Role")}
              value={role}
              onValueChange={(v) => setRole(v as MemberRole)}
              options={INVITE_ROLES.map((r) => ({ value: r, label: t(team.ROLE_LABEL[r]) }))}
            />
          </Field>
          {role === "client" ? (
            <Field label={t("Client")}>
              <Select
                aria-label={t("Client")}
                value={clientId}
                onValueChange={setClientId}
                placeholder={t("Choose a client")}
                options={clients.map((c) => ({ value: c.id, label: c.display_name }))}
              />
            </Field>
          ) : null}
          {error ? <Banner tone="error">{error}</Banner> : null}
          <DialogFooter>
            <Button type="button" variant="outline" size="md" onClick={() => onOpenChange(false)}>
              {t("Cancel")}
            </Button>
            <Button type="submit" size="md" loading={busy}>
              {t("Send invite")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function TeamSettings() {
  const t = useT();
  const toast = useToast();
  const { session } = useAuth();
  const [members, setMembers] = useState<Member[] | null>(null);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [removing, setRemoving] = useState<Member | null>(null);
  const [revoking, setRevoking] = useState<Invite | null>(null);
  const myId = session.user?.id ?? null;

  const load = useCallback(async () => {
    try {
      const [m, i] = await Promise.all([team.listMembers(), team.listInvites()]);
      setMembers(m);
      setInvites(i);
      setError(null);
    } catch (e) {
      setError(problemMessage(e, t("The team could not be loaded.")));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function changeRole(m: Member, role: StaffRole) {
    try {
      await team.changeRole(m.member_id, role);
      isFixtures() ? toast(t("Sample mode: changes are not saved")) : toast(t("Role changed"), { tone: "success" });
    } catch (e) {
      toast(problemMessage(e, t("The role could not be changed.")), { tone: "error" });
    }
    await load();
  }

  async function resend(i: Invite) {
    try {
      // Inviting the same address again replaces the old link with a fresh one.
      await team.createInvite({ email: i.email, role: i.role, client_id: i.client_id });
      if (isFixtures()) toast(t("Sample mode: changes are not saved"));
      else toast(t("Invite sent again to {email}", { email: i.email }), { tone: "success" });
      await load();
    } catch (e) {
      toast(problemMessage(e, t("The invitation could not be sent.")), { tone: "error" });
    }
  }

  const owners = (members ?? []).filter((m) => m.role === "owner").length;
  const count = members?.length ?? 0;

  return (
    <div className="flex flex-col gap-5 px-4 py-6 lg:px-10 lg:py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <div className="flex items-baseline gap-[10px]">
            <h1 className="m-0 text-[32px] font-bold leading-[38px] tracking-[-0.01em] text-ink">{t("Team")}</h1>
            {members ? <span className="text-[16px] leading-5 text-soft">{t("{n} people", { n: count })}</span> : null}
            {isFixtures() ? <SampleBadge /> : null}
          </div>
          <p className="m-0 text-[15px] leading-5 text-body">
            {t("Owners manage the practice. Astrologers read and advise. Assistants book and prepare.")}
          </p>
        </div>
        <Button size="md" onClick={() => setInviteOpen(true)}>
          {t("Invite someone")}
        </Button>
      </div>

      {error ? <Banner tone="error">{error}</Banner> : null}

      <Panel className="overflow-x-auto">
        {members && members.length === 0 ? (
          <EmptyState title={t("No team members yet")} description={t("Invite an astrologer or assistant and they appear here once they accept.")} className="py-10" />
        ) : (
        <table className="w-full min-w-[760px] table-fixed border-collapse text-left" aria-label={t("Team members")}>
          <colgroup>
            <col className="w-[30%]" />
            <col className="w-[200px]" />
            <col />
            <col className="w-[180px]" />
          </colgroup>
          <thead className="bg-sidebar-wash">
            <tr className="text-[12px] font-bold text-soft">
              <th scope="col" className="px-5 py-[11px] text-left font-bold">{t("PERSON")}</th>
              <th scope="col" className="px-2 py-[11px] text-left font-bold">{t("ROLE")}</th>
              <th scope="col" className="px-2 py-[11px] text-left font-bold">{t("CAN DO")}</th>
              <th scope="col" className="px-5 py-[11px] text-right font-bold">{t("ACTION")}</th>
            </tr>
          </thead>
          <tbody>
            {(members ?? []).map((m) => {
              const me = m.user_id === myId;
              const onlyOwner = m.role === "owner" && owners <= 1;
              return (
                <tr key={m.member_id} className={`border-t border-rule ${me ? "bg-wash-soft" : ""}`}>
                  <td className="px-5 py-[11px]">
                    <div className="flex items-center gap-3">
                      <span
                        aria-hidden
                        className={`flex size-9 shrink-0 items-center justify-center rounded-full text-[13px] font-bold ${m.role === "client" || me ? "bg-wash text-accent-text" : "bg-chip text-ink"}`}
                      >
                        {initials(m)}
                      </span>
                      <div className="flex min-w-0 flex-col">
                        <span className="truncate text-[15px] font-bold leading-[19px] text-ink">
                          {m.name || m.email}
                          {me ? <span className="font-normal text-soft"> · {t("you")}</span> : null}
                        </span>
                        <span className="truncate text-[12px] leading-4 text-soft">{m.email}</span>
                      </div>
                    </div>
                  </td>
                  <td className="px-2 py-[11px]">
                    {m.role === "client" ? (
                      <Chip tone="accent">{t(team.ROLE_LABEL.client)}</Chip>
                    ) : (
                      <Select
                        aria-label={t("Role for {name}", { name: m.name || m.email || "" })}
                        className="h-9 w-[150px]"
                        value={m.role}
                        disabled={onlyOwner}
                        onValueChange={(v) => void changeRole(m, v as StaffRole)}
                        options={STAFF.map((r) => ({ value: r, label: t(team.ROLE_LABEL[r]) }))}
                      />
                    )}
                  </td>
                  <td className="px-2 py-[11px] text-[14px] leading-[18px] text-body">{t(team.ROLE_CAN[m.role])}</td>
                  <td className="px-5 py-[11px] text-right">
                    {onlyOwner ? (
                      <span className="text-[13px] text-soft">{t("The only owner")}</span>
                    ) : (
                      <Button variant="link" size="sm" className={LINK + " text-alert"} onClick={() => setRemoving(m)}>
                        {t("Remove")}
                      </Button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        )}
      </Panel>

      <section className="flex flex-col gap-[10px]" aria-label={t("Pending invites")}>
        <div className="flex items-baseline gap-2">
          <h2 className="m-0 text-[20px] font-bold leading-[26px] text-ink">{t("Pending invites")}</h2>
          {invites.length > 0 ? <span className="text-[14px] text-soft">{t("{n} waiting", { n: invites.length })}</span> : null}
        </div>
        <Panel className="overflow-x-auto">
          {invites.length === 0 ? (
            <p className="m-0 px-5 py-6 text-[14px] text-body">{t("No invitations are waiting.")}</p>
          ) : (
            <table className="w-full min-w-[760px] table-fixed border-collapse text-left" aria-label={t("Pending invites")}>
              <colgroup>
                <col className="w-[30%]" />
                <col className="w-[200px]" />
                <col />
                <col className="w-[180px]" />
              </colgroup>
              <tbody>
                {invites.map((i) => (
                  <tr key={i.id} className="border-t border-rule first:border-t-0">
                    <td className="px-5 py-[14px] text-[15px] font-bold text-ink">{i.email}</td>
                    <td className="px-2 py-[14px] text-[14px] text-body">
                      {i.role === "client" ? <Chip tone="accent">{t(team.ROLE_LABEL.client)}</Chip> : t(team.ROLE_LABEL[i.role])}
                    </td>
                    <td className="px-2 py-[14px] text-[14px] text-body">{t("Expires in {n} days", { n: daysLeft(i.expires_at) })}</td>
                    <td className="px-5 py-[14px] text-right">
                      <span className="inline-flex gap-5">
                        <Button variant="link" size="sm" className={LINK + " text-accent-text"} onClick={() => void resend(i)}>
                          {t("Resend")}
                        </Button>
                        <Button variant="link" size="sm" className={LINK + " text-alert"} onClick={() => setRevoking(i)}>
                          {t("Revoke")}
                        </Button>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </section>

      <InviteDialog
        open={inviteOpen}
        onOpenChange={setInviteOpen}
        onSent={(i) => {
          if (isFixtures()) toast(t("Sample mode: changes are not saved"));
          else toast(t("Invitation sent to {email}", { email: i.email }), { tone: "success" });
          void load();
        }}
      />

      <ConfirmDialog
        open={!!removing}
        onOpenChange={(o) => !o && setRemoving(null)}
        tone="danger"
        title={t("Remove {name}?", { name: removing?.name || removing?.email || "" })}
        description={t("They lose access to this practice straight away. Notes and bookings stay with the practice. You can invite them again later.")}
        confirmLabel={t("Remove")}
        cancelLabel={t("Keep")}
        onConfirm={async () => {
          if (!removing) return;
          try {
            await team.removeMember(removing.member_id);
            isFixtures() ? toast(t("Sample mode: changes are not saved")) : toast(t("Removed"), { tone: "success" });
          } catch (e) {
            toast(problemMessage(e, t("That person could not be removed.")), { tone: "error" });
          }
          await load();
        }}
      />

      <ConfirmDialog
        open={!!revoking}
        onOpenChange={(o) => !o && setRevoking(null)}
        tone="danger"
        title={t("Revoke the invitation to {email}?", { email: revoking?.email ?? "" })}
        description={t("The link in their email stops working.")}
        confirmLabel={t("Revoke")}
        cancelLabel={t("Keep")}
        onConfirm={async () => {
          if (!revoking) return;
          try {
            await team.revokeInvite(revoking.id);
            isFixtures() ? toast(t("Sample mode: changes are not saved")) : toast(t("Invitation revoked"), { tone: "success" });
          } catch (e) {
            toast(problemMessage(e, t("The invitation could not be revoked.")), { tone: "error" });
          }
          await load();
        }}
      />
    </div>
  );
}
