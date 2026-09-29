"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { RoundSummary } from "@/lib/types";
import { slug } from "@/lib/format";

const HOUR = 3_600_000;
const DURATION: Record<string, number> = { Race: 2 * HOUR, Sprint: 1 * HOUR };
const SHORT: Record<string, string> = {
  "Practice 1": "FP1", "Practice 2": "FP2", "Practice 3": "FP3",
  "Sprint Qualifying": "Sprint Qualifying", Sprint: "Sprint", Qualifying: "Qualifying", Race: "Race",
};

type Slot = { round: RoundSummary; session: string; start: number };

export function countdown(ms: number): string {
  const m = Math.max(0, Math.round(ms / 60_000));
  const d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60), mm = m % 60;
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${String(mm).padStart(2, "0")}m`;
  return `${mm}m`;
}

/** Site-wide strip: live session, "race starts soon" countdown, or the next race. Computed in the
 *  browser from the published calendar, so it stays current without rebuilding the site. */
export default function RaceBanner({ rounds, year }: { rounds: RoundSummary[]; year: number }) {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    const tick = () => setNow(Date.now());
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, []);

  const slots: Slot[] = rounds.flatMap((round) =>
    round.sessions.filter((s) => s.start_utc).map((s) => ({ round, session: s.name, start: Date.parse(s.start_utc!) })),
  );
  if (now == null) return <div className="h-9 border-b border-line bg-surface" aria-hidden />;

  const live = slots.find((s) => s.start <= now && now < s.start + (DURATION[s.session] ?? HOUR));
  const next = slots.filter((s) => s.start > now).sort((a, b) => a.start - b.start)[0];
  const target = live ?? next;
  if (!target) return <div className="h-9 border-b border-line bg-surface" aria-hidden />;

  const r = target.round;
  const where = `${r.name} · ${r.location}`;
  const href = r.status !== "upcoming" ? `/weekend/${slug(year, r.round)}/` : null;
  let tone = "bg-surface text-ink-2";
  let text: React.ReactNode;
  if (live) {
    tone = "bg-accent text-white";
    text = (<><span className="live-dot mr-2 inline-block h-2 w-2 rounded-full bg-white align-middle" />
      <b className="font-semibold">LIVE NOW</b> · {SHORT[live.session]} · {where}</>);
  } else if (next.session === "Race" && next.start - now < 24 * HOUR) {
    tone = "bg-gradient-to-r from-accent to-[#8a0400] text-white";
    text = (<><b className="font-semibold">Race starts soon</b> · lights out in{" "}
      <b className="num font-semibold">{countdown(next.start - now)}</b> · {where}</>);
  } else if (next.start - now < 4 * 24 * HOUR) {
    tone = "bg-surface-2 text-ink";
    text = (<><b className="font-semibold text-accent-hot">Race weekend</b> · {SHORT[next.session]} in{" "}
      <b className="num font-semibold">{countdown(next.start - now)}</b> · {where}</>);
  } else {
    const date = new Date(next.start).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
    text = (<>Next up: <b className="font-semibold text-ink">{r.name}</b> · {r.location} · {SHORT[next.session]}{" "}
      {date} <span className="text-ink-3">(in {countdown(next.start - now)})</span></>);
  }
  const inner = <span className="truncate">{text}</span>;
  return (
    <div className={`h-9 border-b border-line text-[13px] ${tone}`} role="status" aria-live="polite">
      <div className="mx-auto flex h-full max-w-6xl items-center px-4">
        {href ? <Link href={href} className="flex min-w-0 items-center hover:underline">{inner}</Link> : inner}
      </div>
    </div>
  );
}
