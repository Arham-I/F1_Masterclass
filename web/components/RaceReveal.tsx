"use client";

import { useEffect, useState } from "react";
import DriverTag from "@/components/DriverTag";
import InfoTip from "@/components/InfoTip";
import { modelLabel, pct } from "@/lib/format";
import type { Drivers, PredRow, RaceResult, Weekend } from "@/lib/types";

/** The real race result next to what was predicted. Loaded only when the viewer asks for it:
 *  the replay page itself never contains the result. */
export default function RaceReveal({ weekend, slug, model, rowsFor }: {
  weekend: Weekend; slug: string; model: string; rowsFor: (stage: number, model: string) => { rows: PredRow[]; used: string };
}) {
  const [race, setRace] = useState<RaceResult | null>(null);
  const [error, setError] = useState(false);
  const [stage, setStage] = useState(weekend.steps.length);
  useEffect(() => {
    let alive = true;
    fetch(`/data/race/${slug}.json`)
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then((d: RaceResult) => { if (alive) setRace(d); })
      .catch(() => alive && setError(true));
    return () => { alive = false; };
  }, [slug]);

  if (error) return <p className="panel p-5 text-sm text-ink-2">The race result didn&apos;t load. Check your connection and select Lights out again.</p>;
  if (!race) return <div className="panel h-64 animate-pulse" aria-busy="true" aria-label="Loading race result" />;

  const drivers: Drivers = weekend.drivers;
  const { rows, used } = rowsFor(stage, model);
  const pred = new Map(rows.map((r) => [r.driver, r]));
  const result = race.result.filter((r) => pred.has(r.driver));
  const score = race.scores[String(stage)]?.[used];
  const winner = result[0];
  const n = result.length;
  const x = (p: number) => ((p - 0.5) / n) * 100;

  return (
    <section className="space-y-6" aria-labelledby="race-title">
      <div>
        <h2 id="race-title" className="wide text-4xl sm:text-5xl">{drivers[winner.driver]?.name ?? winner.driver} wins</h2>
        <ul className="mt-4 max-w-3xl space-y-1.5 text-[16px] leading-relaxed text-ink-2">
          {race.commentary.map((c) => <li key={c}>{c}</li>)}
        </ul>
        <p className="mt-2 text-xs text-ink-3">These notes compare the result with the Auto prediction made after qualifying.</p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-ink-2">Compare with the prediction made after</span>
        <div className="flex flex-wrap gap-1" role="radiogroup" aria-label="Prediction made after">
          {weekend.steps.map((s) => (
            <button key={s.stage} type="button" role="radio" aria-checked={stage === s.stage} onClick={() => setStage(s.stage)}
              className={`rounded px-3 py-1 text-sm ${stage === s.stage ? "bg-ink font-semibold text-bg" : "bg-surface-2 text-ink-2 hover:text-ink"}`}>
              {s.short}
            </button>
          ))}
        </div>
      </div>

      {score && (
        <dl className="grid grid-cols-2 divide-line border-y border-line md:grid-cols-4 md:divide-x">
          <Stat k="Winner" v={winner.driver} sub={`${score.winner_hit === 1 ? "Predicted. " : ""}We gave ${pct(pred.get(winner.driver)?.p_win)}`} good={score.winner_hit === 1}
            tip="Did our predicted winner (P1) actually win?" />
          <Stat k="Podium called" v={`${score.podium_hits} of 3`} good={score.podium_hits >= 2} tip="How many of the real top 3 were in our predicted top 3." />
          <Stat k="Typical miss" v={`${score.mae.toFixed(1)} places`} tip="Average distance between each driver's predicted and actual finishing position." />
          <Stat k="Order score" v={score.spearman.toFixed(2)} sub="1 = perfect order" tip="How closely the whole predicted order matched the real one (rank correlation): 1 is perfect, 0 is no better than random." />
        </dl>
      )}
      <p className="text-xs text-ink-3">Model used: {modelLabel(used)}</p>

      <div className="panel p-4 sm:p-5">
        <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-2">
          <h3 className="wide mr-auto text-xl text-ink">Predicted against actual</h3>
          <span className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded-full border-2 border-ink-2" />predicted</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded-full bg-ink-2" />actual</span>
        </div>
        <ul aria-label="Race result compared with the prediction">
          {result.map((r) => {
            const p = pred.get(r.driver)!;
            const c = drivers[r.driver]?.color ?? "#888";
            const delta = p.pos - r.pos;
            const [a, b] = [Math.min(p.pos, r.pos), Math.max(p.pos, r.pos)];
            return (
              <li key={r.driver} className="grid h-9 grid-cols-[2rem_4.8rem_1fr_3.5rem] items-center gap-2 border-b border-line/50 text-sm sm:grid-cols-[2rem_11rem_1fr_6rem]">
                <span className="wide num text-right text-base">{r.finished ? r.pos : "DNF"}</span>
                <DriverTag code={r.driver} d={drivers[r.driver]} showName />
                <span className="relative h-full" aria-label={`predicted P${p.pos}, finished ${r.finished ? `P${r.pos}` : "did not finish"}`}>
                  <span className="absolute top-1/2 h-0.5 -translate-y-1/2 bg-line" style={{ left: `${x(a + 0.5)}%`, width: `${x(b + 0.5) - x(a + 0.5)}%` }} />
                  <span className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 bg-bg" style={{ left: `${x(p.pos + 0.5)}%`, borderColor: c }} />
                  <span className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full" style={{ left: `${x(r.pos + 0.5)}%`, background: r.finished ? c : "var(--ink-3)" }} />
                </span>
                <span className={`num text-right text-[13px] ${!r.finished ? "text-ink-3" : delta > 0 ? "text-good" : delta < 0 ? "text-ink-2" : "text-ink-3"}`}>
                  {!r.finished ? r.status : delta === 0 ? "spot on" : `${delta > 0 ? "▲" : "▼"}${Math.abs(delta)} vs P${p.pos}`}
                </span>
              </li>
            );
          })}
        </ul>
        <p className="mt-3 text-xs text-ink-3">Green ▲ means the driver finished higher than predicted. Retired cars are listed in their classified position.</p>
      </div>
    </section>
  );
}

function Stat({ k, v, sub, tip, good }: { k: string; v: string; sub?: string; tip: string; good?: boolean }) {
  return (
    <div className="px-1 py-4 md:px-5">
      <dt className="text-sm text-ink-2">{k}<InfoTip label={k}>{tip}</InfoTip></dt>
      <dd className={`wide num mt-1 text-2xl ${good === true ? "text-good" : ""}`}>{v}</dd>
      {sub && <dd className="text-xs text-ink-2">{sub}</dd>}
    </div>
  );
}
