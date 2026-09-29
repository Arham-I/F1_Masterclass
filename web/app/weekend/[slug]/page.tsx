import type { Metadata } from "next";
import Link from "next/link";
import Replay from "@/components/Replay";
import { getWeekend, weekendSlugs } from "@/lib/data";

export const dynamicParams = false;

export function generateStaticParams() {
  return weekendSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: PageProps<"/weekend/[slug]">): Promise<Metadata> {
  const w = getWeekend((await params).slug);
  return { title: `${w.name} ${w.year}`, description: `Replay the ${w.year} ${w.name} session by session with a live race prediction.` };
}

export default async function WeekendPage({ params }: PageProps<"/weekend/[slug]">) {
  const { slug } = await params;
  const w = getWeekend(slug);
  const date = new Date(`${w.date}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
  return (
    <div>
      <nav aria-label="Breadcrumb" className="mb-4 text-sm text-ink-3">
        <Link href="/" className="hover:text-ink">{w.year} calendar</Link>
      </nav>
      <header className="mb-6">
        <h1 className="wide text-4xl sm:text-5xl">{w.name}</h1>
        <p className="mt-2 text-ink-2">Round {w.round} in {w.location}, {date}</p>
        {(w.live || w.format === "sprint") && (
          <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold">
            {w.live && <span className="inline-flex items-center gap-1.5 rounded-sm bg-accent px-2 py-1 text-white"><span className="live-dot h-1.5 w-1.5 rounded-full bg-white" />Live weekend</span>}
            {w.format === "sprint" && <span className="rounded-sm bg-warn/15 px-2 py-1 text-warn">Sprint weekend</span>}
          </div>
        )}
      </header>
      <Replay weekend={w} slug={slug} />
    </div>
  );
}
