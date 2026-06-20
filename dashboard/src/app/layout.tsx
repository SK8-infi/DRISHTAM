import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Layout/Sidebar";
import QueryProvider from "@/components/Layout/QueryProvider";
import TutorialManager from "@/components/Tutorial/TutorialManager";

export const metadata: Metadata = {
  title: "DRISHTAM — Predictive Enforcement Intelligence",
  description: "AI-powered enforcement optimization for Bengaluru's parking violations. Predicts where, when, and how to deploy officers for maximum traffic impact reduction.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <QueryProvider>
          <TutorialManager />
          <div className="app-layout">
            <Sidebar />
            <main className="main-content">{children}</main>
          </div>
        </QueryProvider>
      </body>
    </html>
  );
}
