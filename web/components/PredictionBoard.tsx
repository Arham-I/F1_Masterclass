"use client";

import { useState } from "react";
import DriverTag from "@/components/DriverTag";
import DriverDialog from "@/components/DriverDialog";
import Glide from "@/components/Glide";
import InfoTip from "@/components/InfoTip";
import { pct } from "@/lib/format";
import type { Drivers, PredRow, Step } from "@/lib/types";

const ROW = 44;

function Change({ now, before }: { now: number; before?: number }) {
  if (before == null) return <span className="w-7" />;
  const d = before - now;
  if (d === 0) return <span className="w-7 text-center text-[11px] text-ink-3" aria-label="no change">–</span>;
  return (
    <span className={`num w-7 text-center text-[11px] font-semibold ${d > 0 ? "text-good" : "text-ink-3"}`}
      aria-label={d > 0 ? `up ${d}` : `down ${-d}`}>
      {d > 0 ? "▲" : "▼"}{Math.abs(d)}
    </span>
  );
}

/** Likely finishing range (80% of simulated races) with the predicted place as a dot. */
function Range({ r, n, color }: { r: PredRow; n: number; color: string }) {
  const x = (p: number) => ((p - 0.5) / n) * 100;
  return (
    <span className="relative block h-full" aria-label={`likely P${r.lo} to P${r.hi}`}>
      <span className="absolute inset-x-0 top-1/2 h-px bg-line" aria-hidden />
      <span className="grow absolute top-1/2 h-2 -translate-y-1/2 rounded-full opacity-40"
        style={{ left: `${x(r.lo)}%`, width: `${x(r.hi + 1) - x(r.lo)}%`, background: color }} />
      <span className="grow absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-bg"
        style={{ left: `${x(r.pos + 0.5)}%`, background: color }} />
    </span>
  );
}

function Bar({ p, color }: { p: number; color: string }) {
  return (
    <span className="flex items-center justify-end gap-2">
      <span className="num text-[13px]">{pct(p)}</span>
      <span className="hidden h-1.5 w-10 overflow-hidden rounded-sm bg-surface-3 lg:block" aria-hidden>
        <span className="grow block h-full" style={{ width: `${p * 100}%`, background: color }} />
      </span>
    </span>
  );
}

export default function PredictionBoard({ rows, prev, step, drivers }: {
  rows: PredRow[]; prev?: PredRow[]; step: Step; drivers: Drivers;
}) {
  const [open, setOpen] = useState<PredRow | null>(null);
  const before = new Map(prev?.map((r) => [r.driver, r.pos]));
  const sessionPos = new Map(step.timesheet.map((t) => [t.driver, t.pos]));
  const grid = new Map(step.grid.map((g) => [g.driver, g]));
  const showGrid = step.grid.length > 0;
  const provisional = step.grid_state === "provisional";
  const n = rows.length;
  const cols = "grid-cols-[2rem_1.75rem_minmax(4.5rem,1fr)_4.2rem_4.2rem] md:grid-cols-[2rem_1.75rem_minmax(9rem,1.1fr)_minmax(7rem,1fr)_5.2rem_5.2rem_4.4rem_4.4rem_3.2rem]"
    + (showGrid ? " lg:grid-cols-[2rem_1.75rem_minmax(9rem,1.1fr)_minmax(7rem,1fr)_6.5rem_6.5rem_4.6rem_4.6rem_3.2rem_3.2rem]" : " lg:grid-cols-[2rem_1.75rem_minmax(9rem,1.1fr)_minmax(7rem,1fr)_6.5rem_6.5rem_4.6rem_4.6rem_3.2rem]");
  return (
    <div>
      <div className={`grid ${cols} items-end gap-2 border-b border-line pb-2 text-xs font-semibold text-ink-2`}>
        <span className="text-right">Pos.</span>
        <span />
        <span>Driver</span>
        <span className="hidden md:block">Likely finish
          <InfoTip label="Likely finish">The race is simulated 20,000 times. The bar spans the positions this driver finished in 8 out of 10 of those races (1 in 10 went better, 1 in 10 worse). The dot is the predicted position. A short bar means a confident prediction.</InfoTip>
        </span>
        <span className="text-right">Win<InfoTip label="Win chance" align="right">Share of 20,000 simulated races this driver won. The simulation adds realistic randomness: mistakes, strategy, and retirements.</InfoTip></span>
        <span className="text-right">Podium<InfoTip label="Podium chance" align="right">Chance of finishing in the top 3.</InfoTip></span>
        <span className="hidden text-right md:block">Points<InfoTip label="Points chance" align="right">Chance of finishing in the top 10, which scores championship points.</InfoTip></span>
        <span className="hidden text-right md:block">Retire<InfoTip label="Retirement chance" align="right">Chance of not finishing (crash or failure), based on how often this team&apos;s cars have retired.</InfoTip></span>
        <span className="hidden text-right md:block">{step.short}<InfoTip label={`${step.short} position`} align="right">Where the driver placed in {step.session}, for comparison with the prediction.</InfoTip></span>
        {showGrid && (
          <span className="hidden text-right lg:block">
            {provisional ? "Grid*" : "Grid"}
            <InfoTip label="Starting grid" align="right">
              {provisional
                ? "Qualifying order, shown while the official grid is pending: penalties are published as stewards' documents after qualifying and are not in the timing data. It is replaced by the real grid once the race has run."
                : "Official starting position after penalties."}
              {" The prediction starts from qualifying order either way: drivers with grid penalties usually recover much of the lost ground."}
            </InfoTip>
          </span>
        )}
      </div>
      <Glide
        label="Predicted race result"
        items={rows}
        keyOf={(r) => r.driver}
        rowHeight={ROW}
        render={(r) => {
          const d = drivers[r.driver];
          const color = d?.color ?? "#888";
          const g = grid.get(r.driver);
          return (
            <button
              type="button"
              onClick={() => setOpen(r)}
              className={`grid h-full w-full ${cols} items-center gap-2 border-b border-line/60 text-left text-sm transition-colors hover:bg-surface-2`}
              aria-label={`${d?.name ?? r.driver}: predicted P${r.pos}, ${pct(r.p_win)} to win. Show details`}
            >
              <span className={`wide num text-right text-base ${r.pos <= 3 ? "text-ink" : "text-ink-2"}`}>{r.pos}</span>
              <Change now={r.pos} before={before.get(r.driver)} />
              <span className="min-w-0">
                <DriverTag code={r.driver} d={d} showName />
              </span>
              <span className="hidden h-full md:block"><Range r={r} n={n} color={color} /></span>
              <Bar p={r.p_win} color={color} />
              <Bar p={r.p_podium} color={color} />
              <span className="num hidden text-right text-[13px] text-ink-2 md:block">{pct(r.p_points)}</span>
              <span className="num hidden text-right text-[13px] text-ink-2 md:block">{pct(r.p_dnf)}</span>
              <span className="num hidden text-right text-[13px] text-ink-2 md:block">{sessionPos.has(r.driver) ? `P${sessionPos.get(r.driver)}` : "–"}</span>
              {showGrid && (
                <span className={`num hidden text-right text-[13px] lg:block ${g?.penalty ? "text-warn" : "text-ink-2"}`} title={g?.penalty ?? undefined}>
                  {g?.grid ? `P${g.grid}` : g ? "Pit" : "–"}{g?.penalty ? "*" : ""}
                </span>
              )}
            </button>
          );
        }}
      />
      {showGrid && provisional && (
        <p className="mt-2 text-xs text-ink-3">
          * Official grid pending. This is the qualifying order; any grid penalties are applied after
          qualifying and will show here once the race has run.
        </p>
      )}
      {showGrid && !provisional && step.grid.some((g) => g.penalty) && (
        <p className="mt-2 text-xs text-ink-3">
          Grid penalty: {step.grid.filter((g) => g.penalty).map((g) => `${g.driver} ${g.penalty}`).join("; ")}
        </p>
      )}
      <DriverDialog row={open} driver={open ? drivers[open.driver] : undefined} onClose={() => setOpen(null)} session={step.session} />
    </div>
  );
}
