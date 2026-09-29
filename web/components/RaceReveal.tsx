"use client";

import { useEffect, useState } from "react";
import DriverTag from "@/components/DriverTag";
import InfoTip from "@/components/InfoTip";
import { MODEL_INFO, modelLabel, pct } from "@/lib/format";
import type { PredRow, RaceResult, Weekend } from "@/lib/types";

// Up to three models at once. Colours validated as a set on the panel surface (dataviz
// validator, all pairs: CVD ΔE ≥ 9.4, normal ΔE ≥ 20.9) and paired with a shape, so a model is
// never identified by colour alone. A model keeps its slot while it stays selected.
const SLOTS = [
  { color: "#3987e5", shape: "circle" },
  { color: "#d95926", shape: "square" },
  { color: "#199e70", shape: "diamond" },
] as const;
const MAX = SLOTS.length;
type Pick = { model: string; slot: number };

function Marker({ slot, size = 14 }: { slot: number; size?: number }) {
  const { color, shape } = SLOTS[slot];
  const s = size, c = s / 2, r = s / 2 - 2;
  return (
    <svg width={s} height={s} viewBox={`0 0 ${s} ${s}`} aria-hidden className="shrink-0">
      {shape === "circle" && <circle cx={c} cy={c} r={r} fill="var(--bg)" stroke={color} strokeWidth="2" />}
      {shape === "square" && <rect x={2} y={2} width={s - 4} height={s - 4} fill="var(--bg)" stroke={color} strokeWidth="2" />}
      {shape === "diamond" && <path d={`M${c} 1.5 L${s - 1.5} ${c} L${c} ${s - 1.5} L1.5 ${c} Z`} fill="var(--bg)" stroke={color} strokeWidth="2" />}
    </svg>
  );
}

/** The real race result next to the predictions. Loaded only when the viewer asks for it: the
 *  replay page itself never contains the result. */
export default function RaceReveal({ weekend, slug, rowsFor }: {
  weekend: Weekend; slug: string; rowsFor: (stage: number, model: string) => { rows: PredRow[]; used: string };
}) {
  const [race, setRace] = useState<RaceResult | null>(null);
  const [error, setError] = useState(false);
  const [stage, setStage] = useState(weekend.steps.length);
  const [picked, setPicked] = useState<Pick[] | null>(null);
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

  const drivers = weekend.drivers;
  const models = Object.keys(weekend.steps[0].prediction.by);
  const autoPick = race.auto[String(stage)] ?? weekend.steps[stage - 1].prediction.auto;
  const chosen: Pick[] = picked ?? [{ model: autoPick, slot: 0 }];
  const toggle = (m: string) => {
    const has = chosen.find((p) => p.model === m);
    if (has) { if (chosen.length > 1) setPicked(chosen.filter((p) => p.model !== m)); return; }
    if (chosen.length >= MAX) return;
    const free = [0, 1, 2].find((k) => !chosen.some((p) => p.slot === k))!;
    setPicked([...chosen, { model: m, slot: free }]);
  };
  const preds = chosen.map((p) => ({ ...p, rows: new Map(rowsFor(stage, p.model).rows.map((r) => [r.driver, r])) }));
  const result = race.result.filter((r) => preds[0].rows.has(r.driver));
  const winner = result[0];
  const n = result.length;
  const x = (pos: number) => ((pos - 0.5) / n) * 100;
  const ticks = [1, 5, 10, 15, 20].filter((t) => t <= n).concat(n % 5 >= 3 ? [n] : []);
  const cols = "grid-cols-[2.2rem_4.4rem_1fr_auto] sm:grid-cols-[2.6rem_11rem_1fr_9.5rem]";
  // Position axis, repeated under the chart so it stays in view on a long list.
  const axis = (where: "top" | "bottom") => (
    <div className={`grid ${cols} gap-2 text-xs text-ink-2 ${where === "top" ? "items-end border-b border-line pb-1.5" : "items-start pt-1.5"}`} aria-hidden={where === "bottom"}>
      <span className="text-right">{where === "top" ? "Result" : ""}</span>
      <span>{where === "top" ? "Driver" : ""}</span>
      <span className="relative h-8">
        <span className={`absolute left-0 ${where === "top" ? "top-0" : "bottom-0"}`}>Finishing position</span>
        {ticks.map((t) => <span key={t} className={`num absolute -translate-x-1/2 ${where === "top" ? "bottom-0" : "top-0"}`} style={{ left: `${x(t)}%` }}>P{t}</span>)}
      </span>
      <span className="text-right">{where === "top" ? "Predicted" : ""}</span>
    </div>
  );

  return (
    <section className="space-y-8" aria-labelledby="race-title">
      <div>
        <h2 id="race-title" className="wide text-4xl sm:text-5xl">{drivers[winner.driver]?.name ?? winner.driver} wins</h2>
        <ul className="mt-4 max-w-3xl space-y-1.5 text-[16px] leading-relaxed text-ink-2">
          {race.commentary.map((c) => <li key={c}>{c}</li>)}
        </ul>
        <p className="mt-2 text-xs text-ink-3">These notes compare the result with the prediction Auto made after qualifying.</p>
      </div>

      <div className="space-y-3 border-t border-line pt-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="w-52 text-sm text-ink-2">Prediction made after</span>
          <div className="flex flex-wrap gap-1" role="radiogroup" aria-label="Prediction made after">
            {weekend.steps.map((s) => (
              <button key={s.stage} type="button" role="radio" aria-checked={stage === s.stage} onClick={() => setStage(s.stage)}
                className={`rounded px-3 py-1 text-sm ${stage === s.stage ? "bg-ink font-semibold text-bg" : "bg-surface-2 text-ink-2 hover:text-ink"}`}>
                {s.short}
              </button>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="flex w-52 items-center text-sm text-ink-2">Compare models (up to {MAX})
            <InfoTip label="Comparing models">Pick up to three models to draw on the chart and score in the table. &ldquo;Auto&apos;s pick&rdquo; marks the model the Auto setting used at this point of the weekend; Auto itself isn&apos;t a separate model.</InfoTip>
          </span>
          <div className="flex flex-wrap gap-1">
            {models.map((m) => {
              const p = chosen.find((q) => q.model === m);
              const full = !p && chosen.length >= MAX;
              return (
                <button key={m} type="button" aria-pressed={!!p} onClick={() => toggle(m)} disabled={full}
                  title={full ? `Compare up to ${MAX} models: remove one first` : MODEL_INFO[m]?.blurb}
                  className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-sm ${p ? "bg-surface-3 text-ink ring-1 ring-ink-3" : "bg-surface-2 text-ink-2 hover:text-ink disabled:opacity-40"}`}>
                  {p ? <Marker slot={p.slot} size={12} /> : <span className="h-3 w-3 rounded-sm border border-ink-3" aria-hidden />}
                  {modelLabel(m)}
                  {m === autoPick && <span className="rounded-sm bg-ink/10 px-1 text-[11px] text-ink-2">Auto&apos;s pick</span>}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="scroll-x">
        <table className="w-full min-w-[560px] text-[15px]">
          <thead className="border-b border-line text-left text-sm text-ink-2">
            <tr>
              <th scope="col" className="py-2 pr-3 font-normal">Model</th>
              <th scope="col" className="py-2 pr-3 font-normal">Winner picked<InfoTip label="Winner picked">Whether the driver this model predicted to finish first actually won, and the win chance it had given the real winner.</InfoTip></th>
              <th scope="col" className="py-2 pr-3 text-right font-normal">Podium named<InfoTip label="Podium named" align="right">How many of the real top three were in this model&apos;s predicted top three.</InfoTip></th>
              <th scope="col" className="py-2 pr-3 text-right font-normal">Typical miss<InfoTip label="Typical miss" align="right">The average number of places between each driver&apos;s predicted and actual finishing position, counting retired cars in the position they were classified. Lower is better.</InfoTip></th>
              <th scope="col" className="py-2 text-right font-normal">Order score<InfoTip label="Order score" align="right">How closely the whole predicted order matched the real finishing order: 1 is perfect, 0 is no better than a random order.</InfoTip></th>
            </tr>
          </thead>
          <tbody>
            {preds.map((p) => {
              const sc = race.scores[String(stage)]?.[p.model];
              return (
                <tr key={p.model} className="border-b border-line">
                  <th scope="row" className="py-2.5 pr-3 text-left font-semibold"><span className="inline-flex items-center gap-2"><Marker slot={p.slot} />{modelLabel(p.model)}</span></th>
                  <td className="py-2.5 pr-3">{sc ? <>{sc.winner_hit === 1 ? <span className="text-good">✓ Yes</span> : <span className="text-ink-2">✗ No</span>} <span className="text-sm text-ink-3">gave {winner.driver} {pct(p.rows.get(winner.driver)?.p_win)}</span></> : "–"}</td>
                  <td className="num py-2.5 pr-3 text-right">{sc ? `${sc.podium_hits} of 3` : "–"}</td>
                  <td className="num py-2.5 pr-3 text-right">{sc ? `${sc.mae.toFixed(1)} places` : "–"}</td>
                  <td className="num py-2.5 text-right">{sc ? sc.spearman.toFixed(2) : "–"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="panel cut cut-edge p-4 sm:p-5">
        <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-ink-2">
          <h3 className="h3 mr-auto text-ink">Predicted against actual</h3>
          <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-ink" aria-hidden />Where they finished</span>
          {preds.map((p) => <span key={p.model} className="inline-flex items-center gap-1.5"><Marker slot={p.slot} size={12} />{modelLabel(p.model)} predicted</span>)}
        </div>
        {axis("top")}
        <ul aria-label="Race result compared with the predictions">
          {result.map((r) => {
            const ps = preds.map((p) => ({ ...p, pos: p.rows.get(r.driver)!.pos }));
            const all = [r.pos, ...ps.map((p) => p.pos)];
            const [a, b] = [Math.min(...all), Math.max(...all)];
            return (
              <li key={r.driver} className={`grid ${cols} h-9 items-center gap-2 border-b border-line/50 text-sm hover:bg-surface-2`}>
                <span className="wide num text-right text-base">{r.finished ? r.pos : <span className="text-[13px] text-ink-2">DNF</span>}</span>
                <DriverTag code={r.driver} d={drivers[r.driver]} showName />
                <span className="relative h-full" role="img"
                  aria-label={`${r.finished ? `finished P${r.pos}` : `did not finish (${r.status})`}; ${ps.map((p) => `${modelLabel(p.model)} predicted P${p.pos}`).join("; ")}`}>
                  {ticks.map((t) => <span key={t} className="absolute inset-y-1 w-px bg-line/60" style={{ left: `${x(t)}%` }} aria-hidden />)}
                  <span className="absolute top-1/2 h-0.5 -translate-y-1/2 bg-ink-3/70" style={{ left: `${x(a)}%`, width: `${x(b) - x(a)}%` }} aria-hidden />
                  {ps.map((p) => (
                    <span key={p.model} className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2" style={{ left: `${x(p.pos)}%` }}><Marker slot={p.slot} /></span>
                  ))}
                  <span className={`absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ${r.finished ? "bg-ink" : "bg-ink-3"}`} style={{ left: `${x(r.pos)}%` }} aria-hidden />
                </span>
                <span className="flex items-center justify-end gap-2 text-[13px]">
                  {ps.map((p) => (
                    <span key={p.model} className="num inline-flex items-center gap-1">
                      <Marker slot={p.slot} size={10} />
                      <span className={p.pos === r.pos ? "font-semibold text-good" : "text-ink-2"}>P{p.pos}</span>
                    </span>
                  ))}
                </span>
              </li>
            );
          })}
        </ul>
        {axis("bottom")}
        <p className="mt-3 text-xs text-ink-3">
          The filled dot is where the driver finished; each outlined marker is where a model predicted them. Green means
          exactly right. Cars that retired are shown in the position they were classified.
        </p>
      </div>
    </section>
  );
}
