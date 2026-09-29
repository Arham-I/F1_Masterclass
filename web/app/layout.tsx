import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { Barlow_Condensed, Inter } from "next/font/google";
import "./globals.css";
import RaceBanner from "@/components/RaceBanner";
import { getSeason } from "@/lib/data";

// Fonts are downloaded at build time and served from this site (no third-party requests).
const display = Barlow_Condensed({
  variable: "--font-display-face",
  subsets: ["latin"],
  weight: ["700", "800"],
  style: ["normal", "italic"],
});
const body = Inter({ variable: "--font-body", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "Race Weekend Companion", template: "%s · Race Weekend Companion" },
  description:
    "Relive every 2026 Formula 1 weekend session by session: timesheets, race pace, tyres and a race prediction that sharpens after every session.",
};

export const viewport: Viewport = { themeColor: "#09090c", colorScheme: "dark" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  const season = getSeason();
  return (
    <html lang="en" className={`${display.variable} ${body.variable} antialiased`}>
      <body className="min-h-dvh flex flex-col font-sans">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:bg-surface-2 focus:px-3 focus:py-2">
          Skip to content
        </a>
        <header className="relative z-40 border-b border-line bg-bg/85 backdrop-blur">
          <RaceBanner rounds={season.rounds} year={season.year} />
          <nav className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3" aria-label="Main">
            <Link href="/" className="flex items-center gap-2.5 shrink-0" aria-label="Race Weekend Companion home">
              <span aria-hidden className="checker h-5 w-5 rounded-[3px] opacity-90" />
              <span className="display text-lg leading-none sm:text-xl">
                <span className="hidden sm:inline">Race Weekend </span><span className="text-accent">Companion</span>
              </span>
            </Link>
            <div className="ml-auto flex items-center gap-0.5 text-sm font-medium text-ink-2 sm:gap-1">
              <Link className="rounded-md px-2 py-1.5 hover:bg-surface-2 hover:text-ink sm:px-2.5" href="/">Season</Link>
              <Link className="rounded-md px-2 py-1.5 hover:bg-surface-2 hover:text-ink sm:px-2.5" href="/accuracy/">Accuracy</Link>
              <Link className="rounded-md px-2 py-1.5 hover:bg-surface-2 hover:text-ink sm:px-2.5" href="/guide/">Guide</Link>
            </div>
          </nav>
        </header>
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 pb-16 pt-6">{children}</main>
        <footer className="border-t border-line">
          <div className="mx-auto max-w-6xl px-4 py-6 text-xs leading-relaxed text-ink-3">
            <p>
              Timing data from the open-source FastF1 library. Predictions are made by this project&apos;s own
              model using only information available at the time. An unofficial fan project, not associated with
              Formula 1 or any team.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
