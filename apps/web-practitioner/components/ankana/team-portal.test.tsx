import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { chooseSelectOption } from "@/components/ui/test-utils";
import { ToastProvider } from "@/components/ui/toast";

vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => ({ enabled: true, session: { user: { id: "u-owner" }, memberships: [], practiceId: "p1", status: "authed" } }),
}));
vi.mock("@/lib/auth/session", () => ({
  getFreshToken: async () => "tok",
  signOut: async () => undefined,
  refreshSession: async () => null,
  authEnabled: () => true,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

const team = vi.hoisted(() => ({
  listMembers: vi.fn(),
  listInvites: vi.fn(),
  createInvite: vi.fn(),
  revokeInvite: vi.fn(),
  changeRole: vi.fn(),
  removeMember: vi.fn(),
  listClientOptions: vi.fn(),
  getPractice: vi.fn(),
  renamePractice: vi.fn(),
  setTimezone: vi.fn(),
}));
vi.mock("@/lib/api/team", async (orig) => ({ ...(await orig<typeof import("@/lib/api/team")>()), ...team }));

const portal = vi.hoisted(() => ({
  getSummary: vi.fn(),
  getActivePlan: vi.fn(),
  checkIn: vi.fn(),
  getConsents: vi.fn(),
  withdrawConsent: vi.fn(),
  getReceipts: vi.fn(),
  requestExport: vi.fn(),
  getPrivacyRequest: vi.fn(),
}));
vi.mock("@/lib/api/portal", async (orig) => ({ ...(await orig<typeof import("@/lib/api/portal")>()), ...portal }));

import { Portal } from "./portal";
import { PracticeSettings } from "./practice-settings";
import { deviceLabel } from "./sessions-settings";
import { TeamSettings } from "./team-settings";

const wrap = (ui: React.ReactNode) => render(<ToastProvider>{ui}</ToastProvider>);

const MEMBERS = [
  { member_id: "m1", user_id: "u-owner", email: "rohan@x.in", name: "Rohan Shastri", role: "owner", client_id: null },
  { member_id: "m2", user_id: "u2", email: "meenal@x.in", name: "Meenal Kulkarni", role: "astrologer", client_id: null },
  { member_id: "m3", user_id: "u3", email: "ananya@x.in", name: "Ananya Sharma", role: "client", client_id: "c1" },
];

beforeEach(() => {
  vi.clearAllMocks();
  team.listMembers.mockResolvedValue(MEMBERS);
  team.listInvites.mockResolvedValue([
    { id: "i1", email: "karan@x.in", role: "astrologer", client_id: null, expires_at: new Date(Date.now() + 6 * 86_400_000).toISOString() },
  ]);
  team.listClientOptions.mockResolvedValue([{ id: "c1", display_name: "Ananya Sharma" }]);
});
afterEach(cleanup);

describe("Team settings", () => {
  it("lists members and the pending invite, and the last owner cannot be removed", async () => {
    wrap(<TeamSettings />);
    expect(await screen.findByText("Meenal Kulkarni")).toBeInTheDocument();
    expect(screen.getByText("karan@x.in")).toBeInTheDocument();
    expect(screen.getByText("The only owner")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Role for Rohan Shastri" })).toBeDisabled();
  });

  it("changes a role through the Select", async () => {
    team.changeRole.mockResolvedValue({});
    wrap(<TeamSettings />);
    const select = await screen.findByRole("combobox", { name: "Role for Meenal Kulkarni" });
    chooseSelectOption(select, "Assistant");
    await waitFor(() => expect(team.changeRole).toHaveBeenCalledWith("m2", "assistant"));
  });

  it("invites an astrologer, and a client needs a client choice", async () => {
    team.createInvite.mockResolvedValue({ id: "i2", email: "new@x.in", role: "astrologer", client_id: null, expires_at: "2999-01-01" });
    wrap(<TeamSettings />);
    await screen.findByText("Meenal Kulkarni");
    fireEvent.click(screen.getByRole("button", { name: "Invite someone" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Email"), { target: { value: "new@x.in" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Send invite" }));
    await waitFor(() => expect(team.createInvite).toHaveBeenCalledWith({ email: "new@x.in", role: "astrologer", client_id: null }));

    fireEvent.click(screen.getByRole("button", { name: "Invite someone" }));
    const again = await screen.findByRole("dialog");
    fireEvent.change(within(again).getByLabelText("Email"), { target: { value: "p@x.in" } });
    chooseSelectOption(within(again).getByRole("combobox", { name: "Role" }), "Client portal");
    fireEvent.click(within(again).getByRole("button", { name: "Send invite" }));
    expect(await within(again).findByText("Choose which client this portal is for.")).toBeInTheDocument();
    expect(team.createInvite).toHaveBeenCalledTimes(1);
    chooseSelectOption(await within(again).findByRole("combobox", { name: "Client" }), "Ananya Sharma");
    fireEvent.click(within(again).getByRole("button", { name: "Send invite" }));
    await waitFor(() => expect(team.createInvite).toHaveBeenLastCalledWith({ email: "p@x.in", role: "client", client_id: "c1" }));
  });

  it("resends and revokes pending invites; removing a member asks first", async () => {
    team.createInvite.mockResolvedValue({});
    team.revokeInvite.mockResolvedValue(undefined);
    team.removeMember.mockResolvedValue(undefined);
    wrap(<TeamSettings />);
    await screen.findByText("karan@x.in");
    fireEvent.click(screen.getByRole("button", { name: "Resend" }));
    await waitFor(() => expect(team.createInvite).toHaveBeenCalledWith({ email: "karan@x.in", role: "astrologer", client_id: null }));

    fireEvent.click(screen.getByRole("button", { name: "Revoke" }));
    const confirmRevoke = await screen.findByRole("alertdialog");
    fireEvent.click(within(confirmRevoke).getByRole("button", { name: "Revoke" }));
    await waitFor(() => expect(team.revokeInvite).toHaveBeenCalledWith("i1"));

    fireEvent.click(screen.getAllByRole("button", { name: "Remove" })[0]!);
    expect(team.removeMember).not.toHaveBeenCalled();
    const confirm = await screen.findByRole("alertdialog");
    expect(within(confirm).getByText(/Remove Meenal Kulkarni\?/)).toBeInTheDocument();
    fireEvent.click(within(confirm).getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(team.removeMember).toHaveBeenCalledWith("m2"));
  });
});

describe("Practice settings", () => {
  it("saves the name and time zone", async () => {
    team.getPractice.mockResolvedValue({ id: "p1", name: "Shastri Jyotish", timezone: "Asia/Kolkata" });
    team.renamePractice.mockResolvedValue({});
    team.setTimezone.mockResolvedValue({});
    wrap(<PracticeSettings />);
    const name = await screen.findByLabelText("Practice name");
    await waitFor(() => expect(name).toHaveValue("Shastri Jyotish"));
    fireEvent.change(name, { target: { value: "Shastri Jyotish, Pune" } });
    chooseSelectOption(screen.getByRole("combobox", { name: "Time zone" }), "Singapore");
    fireEvent.click(screen.getByRole("button", { name: "Save practice" }));
    await waitFor(() => expect(team.renamePractice).toHaveBeenCalledWith("Shastri Jyotish, Pune"));
    expect(team.setTimezone).toHaveBeenCalledWith("Asia/Singapore");
    expect(screen.getByRole("link", { name: "Open branding" })).toHaveAttribute("href", "/settings/branding");
  });
});

describe("Sessions", () => {
  it("names a device from its user agent", () => {
    expect(deviceLabel("Mozilla/5.0 (Windows NT 10.0) Chrome/120 Safari/537")).toBe("Chrome on Windows");
    expect(deviceLabel("Mozilla/5.0 (iPhone) Safari/604")).toBe("Safari on iPhone");
    expect(deviceLabel(null)).toBe("Unknown device");
  });
});

describe("Client portal", () => {
  const plan = (doneToday: boolean) => ({
    id: "plan1",
    title: "Saturn, 43 days",
    status: "active",
    cycle_days: 43,
    start_date: "2026-11-01",
    end_date: "2026-12-13",
    day_number: 17,
    items: [{ id: "it1", title: "Light a sesame oil lamp", instructions: "At sunset", planet: "Saturn", done_days: 15, done_today: doneToday }],
  });

  beforeEach(() => {
    portal.getSummary.mockResolvedValue({
      client_id: "c1",
      display_name: "Ananya Sharma",
      practice_name: "Shastri Jyotish",
      next_appointment: { id: "x", at: null, date: "2999-11-18", mode: "video", topic: "Career", kind: "follow_up" },
      reports: [{ id: "r1", template: "standard", language: "en", created_at: "2026-10-24T10:00:00Z", size_bytes: 1258291, download_url: "http://x/report.pdf" }],
      today: "2026-11-14",
    });
    portal.getActivePlan.mockResolvedValue(plan(false));
    portal.getConsents.mockResolvedValue({
      consents: [{ id: "k1", purpose: "reminders", notice_version: "v1", granted_at: "2026-10-24T10:00:00Z", withdrawn_at: null }],
      active: { reminders: true },
    });
    portal.getReceipts.mockResolvedValue([
      { id: "rc1", consent_id: "k1", event: "granted", purpose: "reminders", notice_version: "v1", occurred_at: "2026-10-24T10:00:00Z", receipt_hash: "7f3a91c2deadbeef", verified: true, notice_text: null },
    ]);
  });

  it("shows the appointment, plan progress, reports, consents and the advisory line", async () => {
    wrap(<Portal />);
    expect(await screen.findByText("Namaste, Ananya")).toBeInTheDocument();
    expect(screen.getByText("Day 17 of 43")).toBeInTheDocument();
    expect(screen.getByText("15 done")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "43 day progress" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download" })).toHaveAttribute("href", "http://x/report.pdf");
    expect(screen.getByText("Reminders")).toBeInTheDocument();
    expect(screen.getByText(/Receipt 7F3A-91C2/)).toBeInTheDocument();
    expect(screen.getByText(/Guidance is advisory/)).toBeInTheDocument();
  });

  it("checks in today and then shows it as done", async () => {
    portal.checkIn.mockImplementation(async () => {
      portal.getActivePlan.mockResolvedValue(plan(true));
      return {};
    });
    wrap(<Portal />);
    fireEvent.click(await screen.findByRole("button", { name: "Mark today as done" }));
    await waitFor(() => expect(portal.checkIn).toHaveBeenCalledWith("plan1", "it1"));
    expect(await screen.findByText("Done for today")).toBeInTheDocument();
  });

  it("withdraws consent only after confirming", async () => {
    portal.withdrawConsent.mockResolvedValue({});
    wrap(<Portal />);
    fireEvent.click(await screen.findByRole("button", { name: "Withdraw" }));
    expect(portal.withdrawConsent).not.toHaveBeenCalled();
    const dialog = await screen.findByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Withdraw" }));
    await waitFor(() => expect(portal.withdrawConsent).toHaveBeenCalledWith("c1", "reminders"));
  });

  it("requests a data export and offers the download when ready", async () => {
    portal.requestExport.mockResolvedValue({ id: "q1", kind: "client_export", status: "done", download_url: "http://x/export.zip" });
    wrap(<Portal />);
    fireEvent.click(await screen.findByRole("button", { name: "Request my data export" }));
    await waitFor(() => expect(portal.requestExport).toHaveBeenCalledWith("c1"));
    expect(await screen.findByRole("link", { name: "Download my data" })).toHaveAttribute("href", "http://x/export.zip");
  });
});
