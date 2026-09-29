import DriverTag from "@/components/DriverTag";
import Glide from "@/components/Glide";
import { gap, lapTime } from "@/lib/format";
import type { Drivers, Step } from "@/lib/types";

/** Session classification. Practice/Sprint Qualifying: fastest lap order. Qualifying / Sprint:
 *  the official order. Bars show the gap to the fastest lap. */
export default function Timesheet({ step, drivers }: { step: Step; drivers: Drivers }) {
  const rows = step.timesheet;
  const isRace = step.kind === "sprint";
  const max = Math.max(...rows.map((r) => r.gap ?? 0), 0.001);
  return (
    <Glide
      label={`${step.session} classification`}
      items={rows}
      keyOf={(r) => r.driver}
      rowHeight={30}
      render={(r) => {
        const out = isRace && r.status && !/Finished|Lap/.test(r.status);
        return (
          <div className="grid h-full grid-cols-[2.2rem_4.8rem_1fr_5.5rem] items-center gap-2 text-sm sm:grid-cols-[2.2rem_11rem_1fr_6rem]">
            <span className="num text-right text-ink-3">{r.pos}</span>
            <DriverTag code={r.driver} d={drivers[r.driver]} showName />
            <span className="relative h-3.5 overflow-hidden rounded-sm bg-surface-3/60">
              {!isRace && r.gap != null && (
                <span
                  className="grow absolute inset-y-0 left-0 rounded-sm opacity-90"
                  style={{ width: `${Math.max(1.5, (r.gap / max) * 100)}%`, background: r.gap === 0 ? "var(--purple)" : drivers[r.driver]?.color ?? "#888" }}
                />
              )}
            </span>
            <span className="num text-right text-[13px] text-ink-2">
              {isRace ? (out ? <span className="text-warn">{r.status}</span> : r.pos === 1 ? "Winner" : "") :
                r.gap === 0 ? <b className="text-purple">{lapTime(r.best)}</b> : gap(r.gap)}
            </span>
          </div>
        );
      }}
    />
  );
}
