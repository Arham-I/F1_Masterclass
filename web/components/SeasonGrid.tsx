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

/** The season calendar as a list, like a championship calendar. Results are hidden by default so
 *  a replay isn't spoiled; the choice is remembered in this browser. */
export default function SeasonGrid({ rounds, drivers, year }: { rounds: RoundSummary[]; drivers: Drivers; year: number }) {
  const hydrated = useHydrated();
  const [choice, setChoice] = useState<boolean | null>(null);
  const show = choice ?? (hydrated && readStorage(KEY) === "1");
  const toggle = () => {
    writeStorage(KEY, show ? "0" : "1");
    setChoice(!show);
  };
  return (
    <section aria-labelledby="calendar-title">
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <h2 id="calendar-title" className="mr-auto h2">{year} calendar</h2>
        <button type="button" role="switch" aria-checked={show} onClick={toggle}
          className="inline-flex items-center gap-2 rounded px-2 py-1.5 text-sm text-ink-2 hover:bg-surface-2 hover:text-ink">
          <span className={`relative h-4 w-7 rounded-full transition-colors ${show ? "bg-ink" : "bg-surface-3"}`}>
            <span className={`absolute top-0.5 h-3 w-3 rounded-full transition-all ${show ? "left-3.5 bg-bg" : "left-0.5 bg-ink-2"}`} />
          </span>
          Show results
        </button>
      </div>
      <ol className="border-t border-line">
        {rounds.map((r) => {
          const playable = r.status !== "upcoming";
          const row = (
            <>
              <span className="wide num w-8 shrink-0 text-lg text-ink-2">{r.round}</span>
              <span className="w-16 shrink-0 text-sm text-ink-2">{raceDate(r)}</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold">
                  {r.name}
                  {r.format === "sprint" && <span className="ml-2 rounded-sm bg-warn/15 px-1.5 py-0.5 align-middle text-[11px] font-semibold text-warn">Sprint</span>}
                </span>
                <span className="block truncate text-sm text-ink-2">{r.location}</span>
              </span>
              <span className="hidden w-64 shrink-0 text-sm md:block">
                {r.status === "finished" && (show ? (
                  <>
                    <span className="block">{drivers[r.winner!]?.name ?? r.winner} won</span>
                    {r.favourite && (
                      <span className={`block text-xs ${r.favourite.driver === r.winner ? "text-good" : "text-ink-2"}`}>
                        {r.favourite.driver === r.winner ? "As predicted" : `We tipped ${r.favourite.driver}`}, {pct(r.favourite.p_win, 1)} after qualifying
                      </span>
                    )}
                  </>
                ) : null)}
                {r.status === "live" && <span className="inline-flex items-center gap-1.5 font-semibold text-accent-hot"><span className="live-dot h-2 w-2 rounded-full bg-accent" />Live weekend</span>}
              </span>
              <span className={`w-20 shrink-0 text-right text-sm font-semibold ${playable ? "text-ink group-hover:underline" : "text-ink-3"}`}>
                {r.status === "live" ? "Follow" : playable ? "Replay" : "Upcoming"}
              </span>
            </>
          );
          return (
            <li key={r.round} className="border-b border-line">
              {playable ? (
                <Link href={`/weekend/${slug(year, r.round)}/`}
                  className={`group flex items-center gap-3 py-3 pl-5 pr-1 hover:bg-surface ${r.status === "finished" ? "checker-notch" : ""}`}>{row}</Link>
              ) : (
                <div className="flex items-center gap-3 py-3 pl-5 pr-1 text-ink-3">{row}</div>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
