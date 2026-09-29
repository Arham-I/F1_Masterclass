"use client";

import Link from "next/link";
import { useState } from "react";
import { readStorage, useHydrated, writeStorage } from "@/lib/client";
import { pct, slug } from "@/lib/format";
import type { Drivers, RoundSummary } from "@/lib/types";

const KEY = "rwc-show-results";

const raceDate = (r: RoundSummary) => {
  const s = r.sessions.find((x) => x.name === "Race")?.start_utc;
  return s ? new Date(s).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" }) : "";
};

/** Season calendar. Results are hidden by default (spoiler-free), the choice is remembered. */
export default function SeasonGrid({ rounds, drivers, year }: { rounds: RoundSummary[]; drivers: Drivers; year: number }) {
  const hydrated = useHydrated();
  const [choice, setChoice] = useState<boolean | null>(null);
  const show = choice ?? (hydrated && readStorage(KEY) === "1");     // hidden until the browser says otherwise
  const toggle = () => {
    writeStorage(KEY, show ? "0" : "1");
    setChoice(!show);
  };
  return (
    <section aria-labelledby="calendar-title">
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="mr-auto">
          <p className="eyebrow">{year} calendar</p>
          <h2 id="calendar-title" className="display mt-1 text-4xl">Pick a weekend</h2>
        </div>
        <button type="button" role="switch" aria-checked={show} onClick={toggle}
          className="inline-flex items-center gap-2 rounded-full bg-surface-2 px-3 py-1.5 text-sm text-ink-2 hover:text-ink">
          <span className={`relative h-4 w-7 rounded-full transition-colors ${show ? "bg-accent" : "bg-surface-3"}`}>
            <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-white transition-all ${show ? "left-3.5" : "left-0.5"}`} />
          </span>
          Show results
        </button>
      </div>
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {rounds.map((r) => {
          const playable = r.status !== "upcoming";
          const body = (
            <>
              <div className="flex items-center justify-between">
                <span className="eyebrow">Round {r.round} · {raceDate(r)}</span>
                {r.status === "live" && <span className="inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-[10px] font-bold uppercase text-white"><span className="live-dot h-1.5 w-1.5 rounded-full bg-white" />Live</span>}
                {r.format === "sprint" && r.status !== "live" && <span className="rounded-full bg-warn/15 px-2 py-0.5 text-[10px] font-bold uppercase text-warn">Sprint</span>}
              </div>
              <p className="display mt-2 text-2xl">{r.name.replace(" Grand Prix", " GP")}</p>
              <p className="text-sm text-ink-3">{r.location}</p>
              <div className="mt-3 min-h-[2.5rem] text-sm">
                {r.status === "finished" && (show ? (
                  <p className="text-ink-2">
                    Winner <b className="text-ink">{drivers[r.winner!]?.name ?? r.winner}</b>
                    {r.favourite && (
                      <span className={`mt-0.5 block text-xs ${r.favourite.driver === r.winner ? "text-good" : "text-ink-3"}`}>
                        {r.favourite.driver === r.winner ? "✓ Predicted" : `We tipped ${r.favourite.driver}`} ({pct(r.favourite.p_win, 1)} after qualifying)
                      </span>
                    )}
                  </p>
                ) : <p className="text-ink-3">Result hidden · <span className="text-ink-2">replay it first</span></p>)}
                {r.status === "live" && <p className="text-ink-2">Sessions so far are in - follow the live forecast.</p>}
                {r.status === "upcoming" && <p className="text-ink-3">Not raced yet</p>}
              </div>
              {playable && <span className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-accent-hot group-hover:gap-2 transition-all">{r.status === "live" ? "Follow live" : "Replay weekend"} →</span>}
            </>
          );
          return (
            <li key={r.round}>
              {playable ? (
                <Link href={`/weekend/${slug(year, r.round)}/`} className="card group block h-full p-4 transition-colors hover:border-ink-3">{body}</Link>
              ) : (
                <div className="card h-full p-4 opacity-55">{body}</div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
