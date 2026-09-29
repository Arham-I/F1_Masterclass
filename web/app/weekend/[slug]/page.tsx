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
        <Link href="/" className="hover:text-ink">Season {w.year}</Link> <span aria-hidden>/</span> Round {w.round}
      </nav>
      <header className="relative mb-6 overflow-hidden">
        <p className="eyebrow">Round {w.round} · {w.location} · {date}</p>
        <h1 className="display mt-2 text-5xl sm:text-6xl">{w.name.replace(" Grand Prix", "")} <span className="text-accent">Grand Prix</span></h1>
        <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold uppercase tracking-wider">
          {w.live && <span className="inline-flex items-center gap-1.5 rounded-full bg-accent px-2.5 py-1 text-white"><span className="live-dot h-1.5 w-1.5 rounded-full bg-white" />Live weekend</span>}
          {w.format === "sprint" && <span className="rounded-full bg-warn/15 px-2.5 py-1 text-warn">Sprint weekend</span>}
          <span className="rounded-full bg-surface-2 px-2.5 py-1 text-ink-2">{w.steps.length} sessions to replay</span>
        </div>
      </header>
      <Replay weekend={w} slug={slug} />
    </div>
  );
}
