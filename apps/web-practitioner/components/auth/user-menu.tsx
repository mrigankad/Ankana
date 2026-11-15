"use client";

import { useRouter } from "next/navigation";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { authApi } from "@/lib/auth/api";
import { getFreshToken, selectPractice, signOut } from "@/lib/auth/session";
import { LanguageMenuItems } from "@/components/language-switcher";
import { useT } from "@/lib/i18n/provider";
import { useAuth } from "./auth-provider";

const ROLE_LABEL: Record<string, string> = {
  owner: "Owner",
  astrologer: "Astrologer",
  assistant: "Assistant",
  client: "Client",
};

function initials(name: string | null, email: string | null) {
  const src = (name || email || "?").trim();
  const parts = src.split(/[\s@.]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "?") + (parts[1]?.[0] ?? "")).toUpperCase();
}

/** Sidebar footer when built-in auth is on: who you are, practice switcher, sign out. */
export function UserMenu() {
  const { session } = useAuth();
  const router = useRouter();
  const t = useT();
  const current = session.memberships.find((m) => m.practice_id === session.practiceId) ?? session.memberships[0];
  if (!session.user) return null;

  async function switchTo(practiceId: string) {
    selectPractice(practiceId);
    const token = await getFreshToken();
    if (token) void authApi.switchPractice(token, practiceId).catch(() => undefined);
    router.refresh();
    window.location.reload();
  }

  async function logout() {
    await signOut();
    router.replace("/sign-in");
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="flex w-full items-center gap-[10px] rounded-[6px] px-[6px] py-1 text-left hover:bg-white/70"
        aria-label={t("Account menu")}
      >
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-ink text-[12px] font-bold leading-4 text-white">
          {initials(session.user.name, session.user.email)}
        </span>
        <span className="flex min-w-0 flex-col">
          <span className="truncate text-[14px] font-bold leading-[18px] text-black">{session.user.name || session.user.email}</span>
          <span className="truncate text-[12px] leading-4 text-soft">{current?.practice_name ?? ""}</span>
        </span>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="top" align="start" className="w-[248px]">
        <DropdownMenuLabel className="text-[12px] text-soft">{session.user.email}</DropdownMenuLabel>
        {session.memberships.length > 1 ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuLabel className="text-[12px] text-soft">{t("Switch practice")}</DropdownMenuLabel>
            {session.memberships.map((m) => (
              <DropdownMenuItem key={m.practice_id} onSelect={() => void switchTo(m.practice_id)}>
                <span className="grow truncate">{m.practice_name}</span>
                <span className="text-[12px] text-soft">
                  {m.practice_id === current?.practice_id ? t("Current") : (ROLE_LABEL[m.role] ?? m.role)}
                </span>
              </DropdownMenuItem>
            ))}
          </>
        ) : null}
        <DropdownMenuSeparator />
        <LanguageMenuItems />
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => void logout()}>{t("Sign out")}</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
