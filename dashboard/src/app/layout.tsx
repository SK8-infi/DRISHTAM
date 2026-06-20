import type { Metadata, Viewport } from "next";
import "./globals.css";
import Sidebar from "@/components/Layout/Sidebar";
import QueryProvider from "@/components/Layout/QueryProvider";
import TutorialManager from "@/components/Tutorial/TutorialManager";

export const metadata: Metadata = {
  title: "DRISHTAM — Predictive Enforcement Intelligence",
  description: "AI-powered enforcement optimization for Bengaluru's parking violations. Predicts where, when, and how to deploy officers for maximum traffic impact reduction.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <QueryProvider>
          <TutorialManager />
          {/* Skip navigation link for keyboard users */}
          <a href="#main-content" className="skip-nav-link">
            Skip to main content
          </a>
          <div className="app-layout">
            <Sidebar />
            <main id="main-content" className="main-content" role="main" aria-label="Dashboard content">
              {children}
            </main>
          </div>
        </QueryProvider>
      </body>
    </html>
  );
}
