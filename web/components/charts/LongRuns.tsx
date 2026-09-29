import DriverTag from "@/components/DriverTag";
import Glide from "@/components/Glide";
import type { Drivers, Step } from "@/lib/types";

/** Race-simulation pace from practice long runs: lap time vs the typical car on the same tyre.
 *  Dot = typical lap, bar = middle half of the laps. Left of the line = faster than average. */
export default function LongRuns({ step, drivers }: { step: Step; drivers: Drivers }) {
  const rows = step.longrun;
  if (!rows.length)
    return <p className="py-6 text-sm text-ink-3">No long runs in this session (a long run needs 5+ clean laps on one set of tyres).</p>;
  const lo = Math.min(...rows.map((r) => r.q1)), hi = Math.max(...rows.map((r) => r.q3));
  const pad = (hi - lo) * 0.08 || 0.5;
  const x = (v: number) => ((v - (lo - pad)) / (hi - lo + 2 * pad)) * 100;
  return (
    <div>
      <div className="mb-1 grid grid-cols-[4.8rem_1fr_4.5rem] gap-2 text-[11px] text-ink-3 sm:grid-cols-[11rem_1fr_5rem]">
        <span />
        <span className="flex justify-between"><span>Faster</span><span>Slower</span></span>
        <span className="text-right">per lap</span>
      </div>
      <Glide
        label="Long-run pace"
        items={rows}
        keyOf={(r) => r.driver}
        rowHeight={28}
        render={(r, k) => (
          <div className="grid h-full grid-cols-[4.8rem_1fr_4.5rem] items-center gap-2 text-sm sm:grid-cols-[11rem_1fr_5rem]">
            <DriverTag code={r.driver} d={drivers[r.driver]} showName />
            <span className="relative h-full">
              <span className="absolute inset-y-1 w-px bg-ink-3/50" style={{ left: `${x(0)}%` }} aria-hidden />
              <span className="absolute top-1/2 h-2 -translate-y-1/2 rounded-full opacity-45"
                style={{ left: `${x(r.q1)}%`, width: `${Math.max(0.8, x(r.q3) - x(r.q1))}%`, background: drivers[r.driver]?.color }} />
              <span className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-bg"
                style={{ left: `${x(r.median)}%`, background: drivers[r.driver]?.color }} />
            </span>
            <span className={`num text-right text-[13px] ${k === 0 ? "font-semibold text-purple" : r.median < 0 ? "text-ink" : "text-ink-2"}`}>
              {r.median > 0 ? "+" : ""}{r.median.toFixed(2)}s
            </span>
          </div>
        )}
      />
    </div>
  );
}
