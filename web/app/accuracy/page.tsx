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
  const W = 560, H = 220, L = 34, R = 12, T = 14, B = 34;
  const x = (k: number) => L + ((k - 0.5) / 4) * (W - L - R);
  const y = (v: number) => T + (1 - v) * (H - T - B);

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
        <h2 id="afterq" className="wide text-2xl">After qualifying, {auto.races} races</h2>
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

      <section className="panel p-5" aria-labelledby="through">
        <h2 id="through" className="wide text-2xl">Sharper as the weekend goes on</h2>
        <p className="mt-1 text-sm text-ink-2">Order score (higher is better) of the prediction made after each session, averaged over the season.</p>
        <svg viewBox={`0 0 ${W} ${H}`} className="mt-4 w-full max-w-3xl" role="img"
          aria-label={`Order score by stage: ${STAGES.map((s, k) => `${s} ${get(k + 1, acc.auto).spearman.toFixed(2)}`).join(", ")}`}>
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <g key={t}>
              <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeDasharray={t ? "2 4" : undefined} />
              <text x={L - 6} y={y(t) + 4} textAnchor="end" fontSize="10" fill="var(--ink-3)">{t}</text>
            </g>
          ))}
          {STAGES.map((s, k) => (
            <text key={s} x={x(k + 1)} y={H - 12} textAnchor="middle" fontSize="11" fill="var(--ink-2)">{s.replace("After ", "")}</text>
          ))}
          {[acc.baseline, acc.auto].map((p) => {
            const pts = [1, 2, 3, 4].map((k) => get(k, p).spearman);
            const c = p === acc.auto ? "var(--ink)" : "var(--ink-3)";
            return (
              <g key={p}>
                <polyline points={pts.map((v, k) => `${x(k + 1)},${y(v)}`).join(" ")} fill="none" stroke={c} strokeWidth="3" strokeDasharray={p === acc.auto ? undefined : "6 5"} />
                {pts.map((v, k) => (
                  <g key={k}>
                    <circle cx={x(k + 1)} cy={y(v)} r="4.5" fill={c} />
                    <text x={x(k + 1)} y={y(v) + (p === acc.auto ? -10 : 18)} textAnchor="middle" fontSize="11" fontWeight="700" fill={p === acc.auto ? "var(--ink)" : "var(--ink-3)"}>{v.toFixed(2)}</text>
                  </g>
                ))}
              </g>
            );
          })}
        </svg>
        <div className="mt-2 flex gap-5 text-xs text-ink-2">
          <span className="inline-flex items-center gap-2"><span className="h-0.5 w-6 bg-ink" />Our prediction (Auto)</span>
          <span className="inline-flex items-center gap-2"><span className="h-0.5 w-6 border-t-2 border-dashed border-ink-3" />Simple rule</span>
        </div>
      </section>

      <section aria-labelledby="byrace">
        <h2 id="byrace" className="wide text-2xl">Race by race</h2>
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
        <div>
          <h2 id="models" className="wide text-2xl">The models compared</h2>
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
          <h2 className="wide text-lg">Playing fair</h2>
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
