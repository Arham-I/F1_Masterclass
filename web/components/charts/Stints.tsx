import DriverTag from "@/components/DriverTag";
import { COMPOUNDS } from "@/lib/format";
import type { Drivers, Step } from "@/lib/types";

/** Every run each driver did, coloured by tyre, along the session's laps. */
export default function Stints({ step, drivers }: { step: Step; drivers: Drivers }) {
  const byDriver = new Map<string, Step["stints"]>();
  for (const s of step.stints) byDriver.set(s.driver, [...(byDriver.get(s.driver) ?? []), s]);
  const order = step.timesheet.map((t) => t.driver).filter((d) => byDriver.has(d));
  const maxLap = Math.max(...step.stints.map((s) => s.end), 1);
  const used = Object.keys(COMPOUNDS).filter((c) => step.stints.some((s) => s.compound === c));
  if (!order.length) return <p className="py-6 text-sm text-ink-3">No tyre data for this session.</p>;
  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-3 text-xs text-ink-2">
        {used.map((c) => (
          <span key={c} className="inline-flex items-center gap-1.5">
            <span className="inline-flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold text-black" style={{ background: COMPOUNDS[c].color }}>
              {COMPOUNDS[c].letter}
            </span>
            {COMPOUNDS[c].label}
          </span>
        ))}
        <span className="ml-auto text-ink-3">lap 1 → {maxLap}</span>
      </div>
      <ul className="space-y-1" aria-label="Tyre stints per driver">
        {order.map((d) => (
          <li key={d} className="grid grid-cols-[4.8rem_1fr] items-center gap-2 sm:grid-cols-[11rem_1fr]">
            <DriverTag code={d} d={drivers[d]} showName />
            <span className="relative h-4 rounded-sm bg-surface-3/50">
              {byDriver.get(d)!.map((s, i) => {
                const c = COMPOUNDS[s.compound] ?? COMPOUNDS.UNKNOWN;
                return (
                  <span key={i} title={`${c.label}: laps ${s.start}-${s.end}`}
                    className="absolute inset-y-0 flex items-center justify-center overflow-hidden rounded-[3px] border border-bg text-[9px] font-bold text-black"
                    style={{ left: `${((s.start - 1) / maxLap) * 100}%`, width: `${((s.end - s.start + 1) / maxLap) * 100}%`, background: c.color }}>
                    {s.end - s.start >= 3 ? c.letter : ""}
                  </span>
                );
              })}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
