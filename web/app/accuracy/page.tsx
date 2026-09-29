import type { Metadata } from "next";
import Link from "next/link";
import InfoTip from "@/components/InfoTip";
import { getAccuracy, getSeason } from "@/lib/data";
import { MODEL_INFO, modelLabel, slug } from "@/lib/format";

export const metadata: Metadata = { title: "Accuracy", description: "How well the race predictions have matched real results this season." };

const STAGES = ["After 1st session", "After 2nd session", "After 3rd session", "After qualifying"];

export default function AccuracyPage() {
  const acc = getAccuracy();
  const season = getSeason();
  const names = new Map(season.rounds.map((r) => [r.round, r]));
  const get = (stage: number, p: string) => acc.summary.find((s) => s.stage === stage && s.predictor === p)!;
  const auto = get(4, acc.auto), base = get(4, acc.baseline);
  const predictors = [acc.auto, ...Object.keys(MODEL_INFO).filter((p) => p !== acc.auto && acc.summary.some((s) => s.predictor === p))];
  const rounds = acc.per_round.filter((r) => r.stage === 4 && r.predictor === acc.auto).sort((a, b) => a.round - b.round);
  // Zoomed scale for the stage comparison (labelled on the page as starting at LO).
  const LO = 0.55, HI = 0.8;
  const TICKS = [0.55, 0.6, 0.65, 0.7, 0.75, 0.8];
  const sx = (v: number) => ((v - LO) / (HI - LO)) * 100;

  return (
    <div className="space-y-10">
      <header>
        <h1 className="wide text-4xl sm:text-5xl">How accurate is it?</h1>
        <p className="mt-4 max-w-2xl text-[16px] leading-relaxed text-ink-2">
          Every prediction on this site was made using only what was known at that moment, then checked against the
          real race. Below is the full record, next to the simplest possible guess: <b className="text-ink">the cars
          finish in qualifying order</b>. In Formula 1 that is a hard benchmark to beat.
        </p>
      </header>

      <section aria-labelledby="afterq">
        <h2 id="afterq" className="h2">After qualifying, {auto.races} races</h2>
        <div className="scroll-x mt-3">
          <table className="w-full min-w-[520px] text-[15px]">
            <thead className="border-b border-line text-left text-sm text-ink-2">
              <tr>
                <th scope="col" className="py-2 pr-4 font-normal">Measure</th>
                <th scope="col" className="py-2 pr-4 text-right font-semibold text-ink">Our prediction</th>
                <th scope="col" className="py-2 text-right font-normal">Qualifying order</th>
              </tr>
            </thead>
            <tbody>
              {[
                { k: "Winner picked", a: `${Math.round(auto.winner_hit * auto.races)} of ${auto.races}`, b: `${Math.round(base.winner_hit * base.races)} of ${base.races}`, tip: "How often our predicted winner actually won." },
                { k: "Podium finishers named", a: `${auto.podium_hits.toFixed(2)} of 3`, b: `${base.podium_hits.toFixed(2)} of 3`, tip: "On average, how many of the real top three were in our predicted top three." },
                { k: "Typical miss", a: `${auto.mae.toFixed(2)} places`, b: `${base.mae.toFixed(2)} places`, tip: "Average gap between each driver's predicted and actual finishing place. Lower is better." },
                { k: "Order score", a: auto.spearman.toFixed(3), b: base.spearman.toFixed(3), tip: "How closely the whole predicted order matched the real one (Spearman rank correlation). 1 is perfect, 0 is no better than random." },
              ].map((c) => (
                <tr key={c.k} className="border-b border-line">
                  <th scope="row" className="py-3 pr-4 text-left font-normal text-ink-2">{c.k}<InfoTip label={c.k}>{c.tip}</InfoTip></th>
                  <td className="wide num py-3 pr-4 text-right text-xl">{c.a}</td>
                  <td className="num py-3 text-right text-ink-2">{c.b}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="border-t border-line pt-5" aria-labelledby="through">
        <h2 id="through" className="h2">Each session adds a little</h2>
        <p className="mt-1 max-w-2xl text-sm text-ink-2">
          Order score of the prediction made after each session, averaged over the season. The scale starts at {LO} so
          the differences are visible: they are small, and the two approaches stay close all weekend.
        </p>
        <div className="mt-5 max-w-3xl">
          <div className="grid grid-cols-[8.5rem_1fr_7rem] gap-3 text-xs text-ink-3">
            <span />
            <span className="relative h-4">
              {TICKS.map((t) => <span key={t} className="num absolute -translate-x-1/2" style={{ left: `${sx(t)}%` }}>{t.toFixed(2)}</span>)}
            </span>
            <span />
          </div>
          <ol>
            {STAGES.map((label, k) => {
              const ours = get(k + 1, acc.auto).spearman, rule = get(k + 1, acc.baseline).spearman;
              return (
                <li key={label} className="grid grid-cols-[8.5rem_1fr_7rem] items-center gap-3 border-b border-line py-3 text-sm">
                  <span className="text-ink-2">{label}</span>
                  <span className="relative h-4" aria-label={`ours ${ours.toFixed(3)}, qualifying-order rule ${rule.toFixed(3)}`}>
                    {TICKS.map((t) => <span key={t} className="absolute inset-y-0 w-px bg-line" style={{ left: `${sx(t)}%` }} aria-hidden />)}
                    <span className="absolute top-1/2 h-0.5 -translate-y-1/2 bg-ink-3" style={{ left: `${sx(Math.min(ours, rule))}%`, width: `${Math.abs(sx(ours) - sx(rule))}%` }} aria-hidden />
                    <span className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ink-2 bg-bg" style={{ left: `${sx(rule)}%` }} aria-hidden />
                    <span className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-ink" style={{ left: `${sx(ours)}%` }} aria-hidden />
                  </span>
                  <span className="num text-right"><b>{ours.toFixed(3)}</b> <span className="text-ink-3">/ {rule.toFixed(3)}</span></span>
                </li>
              );
            })}
          </ol>
          <div className="mt-3 flex gap-5 text-xs text-ink-2">
            <span className="inline-flex items-center gap-2"><span className="h-3 w-3 rounded-full bg-ink" />Our prediction (Auto)</span>
            <span className="inline-flex items-center gap-2"><span className="h-3 w-3 rounded-full border-2 border-ink-2" />Qualifying-order rule (practice order before qualifying)</span>
          </div>
        </div>
      </section>

      <section aria-labelledby="byrace">
        <h2 id="byrace" className="h2">Race by race</h2>
        <p className="mt-1 text-sm text-ink-2">Our prediction after qualifying, checked against each result.</p>
        <div className="scroll-x mt-3 rounded-md border border-line">
          <table className="w-full min-w-[560px] text-sm">
            <thead className="bg-surface text-left text-sm text-ink-2">
              <tr>
                <th scope="col" className="px-3 py-2 font-normal">Round</th>
                <th scope="col" className="px-3 py-2 font-normal">Winner picked</th>
                <th scope="col" className="px-3 py-2 text-right font-normal">Podium</th>
                <th scope="col" className="px-3 py-2 text-right font-normal">Typical miss</th>
                <th scope="col" className="px-3 py-2 text-right font-normal">Order score</th>
              </tr>
            </thead>
            <tbody>
              {rounds.map((r) => {
                const meta = names.get(r.round);
                return (
                  <tr key={r.round} className="border-t border-line/70">
                    <td className="px-3 py-2">
                      <Link href={`/weekend/${slug(acc.year, r.round)}/?step=race`} className="hover:underline">
                        <span className="num text-ink-3">R{r.round}</span> {meta?.name.replace(" Grand Prix", " GP")}
                      </Link>
                      {r.round >= acc.holdout_from && <span className="ml-2 rounded-sm bg-good/15 px-1.5 py-0.5 text-[11px] font-semibold text-good">Unseen test</span>}
                    </td>
                    <td className={`px-3 py-2 ${r.winner_hit ? "text-good" : "text-ink-3"}`}>{r.winner_hit ? "✓ Yes" : "✗ No"}</td>
                    <td className="num px-3 py-2 text-right">{Math.round(r.podium_hits)} / 3</td>
                    <td className="num px-3 py-2 text-right">{r.mae.toFixed(1)}</td>
                    <td className="num px-3 py-2 text-right">{r.spearman.toFixed(2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="models" className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <div className="min-w-0">
          <h2 id="models" className="h2">The models compared</h2>
          <p className="mt-1 text-sm text-ink-2">After qualifying, averaged over the season. &ldquo;Auto&rdquo; switches to whichever model has the best record so far.</p>
          <div className="scroll-x mt-3 rounded-md border border-line">
            <table className="w-full min-w-[520px] text-sm">
              <thead className="bg-surface text-left text-sm text-ink-2">
                <tr>
                  <th scope="col" className="px-3 py-2 font-normal">Model</th>
                  <th scope="col" className="px-3 py-2 text-right font-normal">Winners</th>
                  <th scope="col" className="px-3 py-2 text-right font-normal">Podium</th>
                  <th scope="col" className="px-3 py-2 text-right font-normal">Miss</th>
                  <th scope="col" className="px-3 py-2 text-right font-normal">Order</th>
                </tr>
              </thead>
              <tbody>
                {predictors.map((p) => {
                  const s = get(4, p);
                  return (
                    <tr key={p} className="border-t border-line/70">
                      <th scope="row" className="px-3 py-2 text-left font-medium">{modelLabel(p)}
                        <span className="block text-xs font-normal text-ink-3">{MODEL_INFO[p]?.blurb}</span>
                      </th>
                      <td className="num px-3 py-2 text-right">{Math.round(s.winner_hit * s.races)}/{s.races}</td>
                      <td className="num px-3 py-2 text-right">{s.podium_hits.toFixed(2)}</td>
                      <td className="num px-3 py-2 text-right">{s.mae.toFixed(2)}</td>
                      <td className="num px-3 py-2 text-right">{s.spearman.toFixed(3)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
        <aside className="panel h-fit p-5">
          <h2 className="h3">Playing fair</h2>
          <ul className="mt-3 space-y-3 text-sm leading-relaxed text-ink-2">
            <li><b className="text-ink">No peeking.</b> Each prediction uses only the sessions before it and the results of earlier races.</li>
            <li><b className="text-ink">Frozen model.</b> The model was locked after round {acc.holdout_from - 1}. From round {acc.holdout_from} on, every race is a genuine test it has never seen - marked <span className="text-good">Unseen test</span> above.</li>
            <li><b className="text-ink">Still learning, by fixed rules.</b> After each race the new result is added to the training data automatically; the recipe itself doesn&apos;t change.</li>
            <li><b className="text-ink">Small numbers.</b> With {auto.races} races so far, one or two surprises can move these figures noticeably.</li>
          </ul>
        </aside>
      </section>
    </div>
  );
}
