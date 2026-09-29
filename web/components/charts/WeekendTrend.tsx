"use client";

import { useState } from "react";
import { pct } from "@/lib/format";
import type { Drivers, PredRow, Step } from "@/lib/types";

const W = 520, H = 220, L = 38, R = 70, T = 14, B = 34;

/** Win chances of today's top contenders after every revealed session, plus how sure the
 *  prediction is (typical error in places). Sessions not yet revealed are drawn as empty slots,
 *  so the chart never shows the future. */
export default function WeekendTrend({ steps, upto, rowsAt, drivers }: {
  steps: Step[]; upto: number; rowsAt: (i: number) => PredRow[]; drivers: Drivers;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const shown = steps.slice(0, upto + 1).map((_, i) => rowsAt(i));
  const top = [...shown[upto]].sort((a, b) => b.p_win - a.p_win).slice(0, 4).map((r) => r.driver);
  const series = top.map((d) => ({ d, pts: shown.map((rows) => rows.find((r) => r.driver === d)?.p_win ?? 0) }));
  const ymax = Math.max(0.2, ...series.flatMap((s) => s.pts)) * 1.1;
  const x = (i: number) => L + (steps.length === 1 ? 0.5 : i / (steps.length - 1)) * (W - L - R);
  const y = (p: number) => T + (1 - p / ymax) * (H - T - B);
  const ticks = [0, ymax / 2, ymax].map((v) => Math.round(v * 20) / 20);
  const sigma = shown.map((rows) => rows.reduce((t, r) => t + r.sigma, 0) / rows.length);

  // Nudge end labels apart so they never overlap.
  const labels = series.map((s) => ({ d: s.d, y: y(s.pts[upto]) })).sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i++) labels[i].y = Math.max(labels[i].y, labels[i - 1].y + 13);
  const overflow = labels.length ? labels[labels.length - 1].y - (H - B) : 0;   // keep clear of the axis labels
  if (overflow > 0) for (const l of labels) l.y -= overflow;

  return (
    <div>
      <div className="relative" onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
        aria-label={`Win chance after each session. Now: ${series.map((s) => `${s.d} ${pct(s.pts[upto], 1)}`).join(", ")}`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeDasharray={t === 0 ? undefined : "2 4"} />
            <text x={L - 6} y={y(t) + 4} textAnchor="end" fontSize="10" fill="var(--ink-3)">{Math.round(t * 100)}%</text>
          </g>
        ))}
        {steps.map((s, i) => (
          <text key={s.session} x={x(i)} y={H - 10} textAnchor="middle" fontSize="12"
            fill={i <= upto ? "var(--ink-2)" : "var(--ink-3)"} opacity={i <= upto ? 1 : 0.5}>
            {s.short}
          </text>
        ))}
        {series.map((s) => {
          const c = drivers[s.d]?.color ?? "#888";
          return (
            <g key={s.d}>
              {s.pts.length > 1 && (
                <polyline points={s.pts.map((p, i) => `${x(i)},${y(p)}`).join(" ")} fill="none" stroke={c} strokeWidth="2.5"
                  strokeLinejoin="round" strokeLinecap="round" />
              )}
              {s.pts.map((p, i) => <circle key={i} cx={x(i)} cy={y(p)} r={i === upto ? 4.5 : 3} fill={c} stroke="var(--bg)" strokeWidth="1.5" />)}
            </g>
          );
        })}
        {labels.map((l) => {
          const s = series.find((q) => q.d === l.d)!;
          return (
            <text key={l.d} x={x(upto) + 10} y={l.y + 4} fontSize="12" fontWeight="700" fill={drivers[l.d]?.color ?? "#888"}>
              {l.d} {pct(s.pts[upto], 0)}
            </text>
          );
        })}
        {hover != null && <line x1={x(hover)} x2={x(hover)} y1={T} y2={H - B} stroke="var(--ink-2)" strokeWidth="1" aria-hidden />}
        {shown.map((_, i) => {
          const half = steps.length > 1 ? (W - L - R) / (steps.length - 1) / 2 : 40;
          return (
            <rect key={i} x={x(i) - half} y={T} width={half * 2} height={H - T - B} fill="transparent" tabIndex={0}
              aria-label={`After ${steps[i].short}: ${series.map((q) => `${q.d} ${pct(q.pts[i], 1)}`).join(", ")}`}
              onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)} onBlur={() => setHover(null)} className="outline-none" />
          );
        })}
      </svg>
      {hover != null && (
        <div className="pointer-events-none absolute top-2 z-10 w-44 rounded border border-line bg-surface-3 p-2.5 text-xs shadow-lg"
          style={{ left: `${Math.min((x(hover) / W) * 100, 62)}%`, transform: "translateX(8px)" }}>
          <p className="mb-1.5 text-ink-2">Chance to win after {steps[hover].short}</p>
          {[...series].sort((a, b) => b.pts[hover] - a.pts[hover]).map((q) => (
            <p key={q.d} className="flex items-center gap-2">
              <span className="h-0.5 w-3" style={{ background: drivers[q.d]?.color }} aria-hidden />
              <b className="num text-ink">{pct(q.pts[hover], 1)}</b>
              <span className="text-ink-2">{q.d}</span>
            </p>
          ))}
          <p className="mt-1.5 text-ink-2">Typical error <b className="num text-ink">±{sigma[hover].toFixed(1)}</b> places</p>
        </div>
      )}
      </div>
      <div className="mt-3 border-t border-line pt-3">
        <p className="text-xs text-ink-3">Typical error of the prediction (places, for cars that finish)</p>
        <ol className="mt-2 grid gap-1.5" style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }}>
          {steps.map((s, i) => (
            <li key={s.session} className={`rounded-md px-1 py-1.5 text-center ${i === upto ? "bg-surface-3 ring-1 ring-ink" : "bg-surface-2"}`}>
              <span className="block text-[11px] text-ink-2">{s.short}</span>
              <span className={`num block text-sm font-semibold ${i <= upto ? "" : "text-ink-3"}`}>{i <= upto ? `±${sigma[i].toFixed(1)}` : "?"}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
