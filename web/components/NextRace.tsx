"use client";

import Link from "next/link";
import { countdown, useNow } from "@/components/RaceBanner";
import { slug } from "@/lib/format";
import type { RoundSummary } from "@/lib/types";

const HOUR = 3_600_000;

/** The next (or current) race weekend: one start light per session, lit once the session is over. */
export default function NextRace({ rounds, year }: { rounds: RoundSummary[]; year: number }) {
  const now = useNow();
  if (now == null) return <div className="panel h-56" aria-hidden />;
  const t = now;
  const round = rounds.find((r) => r.sessions.some((s) => s.name === "Race" && s.start_utc && Date.parse(s.start_utc) + 2 * HOUR > t));
  if (!round) return null;
  const sessions = round.sessions.filter((s) => s.start_utc).map((s) => ({ ...s, start: Date.parse(s.start_utc!) }));
  const next = sessions.find((s) => s.start > t);
  const fmt = new Intl.DateTimeFormat(undefined, { weekday: "short", hour: "2-digit", minute: "2-digit" });
  return (
    <div className="panel p-5">
      <h2 className="text-sm text-ink-2">{round.status === "live" ? "This weekend" : "Next race"}</h2>
      <p className="wide mt-1 text-2xl">{round.name}</p>
      <p className="text-sm text-ink-2">{round.location}, round {round.round}</p>
      <ol className="mt-4 flex gap-1 rounded-md bg-[#101113] p-1.5" aria-label="Sessions this weekend">
        {sessions.map((s) => {
          const done = s.start + (s.name === "Race" ? 2 : 1) * HOUR <= t;
          return (
            <li key={s.name} className="flex flex-1 flex-col items-center gap-1.5 py-1.5 text-center">
              <span className="flex gap-1" aria-hidden><span className={`lamp ${done ? "on" : ""}`} /><span className={`lamp ${done ? "on" : ""}`} /></span>
              <span className="text-[11px] leading-tight text-ink-2">
                {s.name.replace("Practice ", "FP").replace("Sprint Qualifying", "SQ").replace("Qualifying", "Quali")}
                <span className="block text-ink-3">{fmt.format(new Date(s.start))}</span>
              </span>
              <span className="sr-only">{done ? "finished" : "to come"}</span>
            </li>
          );
        })}
      </ol>
      <p className="mt-3 text-sm">
        {next ? <>{next.name} starts in <b className="num">{countdown(next.start - t)}</b> (times in your time zone).</> : "Race under way."}
      </p>
      {round.status === "live" && (
        <Link href={`/weekend/${slug(year, round.round)}/`} className="mt-3 inline-block text-sm font-semibold text-accent-hot hover:underline">Follow the live forecast</Link>
      )}
    </div>
  );
}
