import type { ReactNode } from "react";
import localFont from "next/font/local";

import "./globals.css";

import { AppShell } from "@/components/app-shell";
import { AuthProvider } from "@/components/auth/auth-provider";
import { ToastProvider } from "@/components/ui/toast";
import { TooltipProvider } from "@/components/ui/tooltip";
import { LanguageProvider } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

// Fonts are bundled (SIL OFL, see app/fonts) so Ankana builds and runs fully offline.
const urbanist = localFont({
  src: "./fonts/Urbanist-VF.ttf",
  weight: "100 900",
  variable: "--font-urbanist",
  display: "swap",
});

// Devanagari script only (Hindi and Sanskrit labels); never used for Latin text.
const notoDeva = localFont({
  src: "./fonts/NotoSerifDevanagari-VF.ttf",
  weight: "100 900",
  variable: "--font-deva",
  display: "swap",
});

export const metadata = {
  title: "Ankana",
  description:
    "The Jyotish practice workspace: deterministic charts, explainable readings.",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={cn(urbanist.variable, notoDeva.variable, "font-sans")}>
      <body className="min-h-screen antialiased">
        <TooltipProvider delayDuration={200}>
          <AuthProvider>
            <LanguageProvider>
              <ToastProvider>
                <AppShell>{children}</AppShell>
              </ToastProvider>
            </LanguageProvider>
          </AuthProvider>
        </TooltipProvider>
      </body>
    </html>
  );
}
