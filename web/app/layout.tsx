import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { Archivo } from "next/font/google";
import "./globals.css";
import RaceBanner from "@/components/RaceBanner";
import { getSeason } from "@/lib/data";

// One family, two widths (see DESIGN.md). Downloaded at build time and served from this site.
const archivo = Archivo({ variable: "--font-archivo", subsets: ["latin"], axes: ["wdth"] });

export const metadata: Metadata = {
  title: { default: "Race Weekend Companion", template: "%s | Race Weekend Companion" },
  description:
    "Relive every 2026 Formula 1 weekend session by session: timesheets, race pace, tyres and a race prediction that sharpens after every session.",
};

export const viewport: Viewport = { themeColor: "#1a1b1e", colorScheme: "dark" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  const season = getSeason();
  return (
    <html lang="en" className={`${archivo.variable} antialiased`}>
      <body className="flex min-h-dvh flex-col font-sans">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:bg-surface-2 focus:px-3 focus:py-2">
          Skip to content
        </a>
        <header className="border-b border-line">
          <RaceBanner rounds={season.rounds} year={season.year} />
          <nav className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3" aria-label="Main">
            <Link href="/" className="flex shrink-0 items-center gap-2.5" aria-label="Race Weekend Companion, home">
              <span aria-hidden className="flex gap-[3px]">
                {[0, 1, 2].map((k) => <span key={k} className="lamp on !h-2.5 !w-2.5" />)}
              </span>
              <span className="wide text-[15px] sm:text-base">
                <span className="hidden sm:inline">Race Weekend </span>Companion
              </span>
            </Link>
            <div className="ml-auto flex items-center gap-0.5 text-sm text-ink-2 sm:gap-1">
              <Link className="rounded px-2 py-1.5 hover:bg-surface-2 hover:text-ink sm:px-2.5" href="/">Season</Link>
              <Link className="rounded px-2 py-1.5 hover:bg-surface-2 hover:text-ink sm:px-2.5" href="/accuracy/">Accuracy</Link>
              <Link className="rounded px-2 py-1.5 hover:bg-surface-2 hover:text-ink sm:px-2.5" href="/guide/">Guide</Link>
            </div>
          </nav>
        </header>
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 pb-16 pt-6">{children}</main>
        <footer className="border-t border-line">
          <div className="mx-auto max-w-6xl px-4 py-6 text-xs leading-relaxed text-ink-3">
            <p className="max-w-3xl">
              Timing data from the open-source FastF1 library. Predictions come from this project&apos;s own model,
              using only information available at the time. An unofficial fan project, not associated with Formula 1
              or any team.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
