"use client";

import { useEffect, useRef } from "react";
import { pct } from "@/lib/format";
import type { Driver, PredRow } from "@/lib/types";

/** Per-driver detail: the chance of every finishing position from the 20,000 simulated races. */
export default function DriverDialog({ row, driver, session, onClose }: {
  row: PredRow | null; driver?: Driver; session: string; onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (row && !dlg.open) dlg.showModal();
    if (!row && dlg.open) dlg.close();
  }, [row]);
  const max = row ? Math.max(...row.dist) : 1;
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      className="m-auto w-[min(92vw,560px)] rounded-2xl border border-line bg-surface p-0 text-ink backdrop:bg-black/70 backdrop:backdrop-blur-sm"
      aria-labelledby="driver-dialog-title"
    >
      {row && (
        <div className="p-5">
          <div className="flex items-start gap-3">
            <span className="mt-1 h-10 w-1.5 rounded-full" style={{ background: driver?.color }} aria-hidden />
            <div className="min-w-0">
              <p className="eyebrow">{driver?.team} · prediction after {session}</p>
              <h2 id="driver-dialog-title" className="display text-3xl">{driver?.name ?? row.driver}</h2>
            </div>
            <button type="button" onClick={onClose} className="ml-auto rounded-md px-2 py-1 text-ink-2 hover:bg-surface-2 hover:text-ink" aria-label="Close">✕</button>
          </div>
          <dl className="mt-4 grid grid-cols-4 gap-2 text-center">
            {[["Predicted", `P${row.pos}`], ["Win", pct(row.p_win)], ["Podium", pct(row.p_podium)], ["Retire", pct(row.p_dnf)]].map(([k, v]) => (
              <div key={k} className="rounded-lg bg-surface-2 px-2 py-2">
                <dt className="eyebrow !text-[10px]">{k}</dt>
                <dd className="num mt-0.5 font-semibold">{v}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-5 text-sm text-ink-2">Chance of finishing in each position</p>
          <div className="mt-2 flex h-36 items-end gap-[3px]" role="img"
            aria-label={`Most likely finishing positions: ${row.dist.map((p, i) => [p, i + 1] as const).sort((a, b) => b[0] - a[0]).slice(0, 3).map(([p, i]) => `P${i} ${pct(p, 1)}`).join(", ")}`}>
            {row.dist.map((p, i) => (
              <div key={i} className="group relative flex h-full flex-1 flex-col justify-end">
                <div className="rounded-t-[3px]" style={{ height: `${(p / max) * 100}%`, background: driver?.color, opacity: i + 1 >= row.lo && i + 1 <= row.hi ? 1 : 0.35 }} />
                <span className="pointer-events-none absolute -top-6 left-1/2 hidden -translate-x-1/2 whitespace-nowrap rounded bg-surface-3 px-1.5 py-0.5 text-[11px] group-hover:block">
                  P{i + 1}: {pct(p)}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-1 flex gap-[3px] text-center text-[9px] text-ink-3">
            {row.dist.map((_, i) => <span key={i} className="flex-1">{(i + 1) % 5 === 0 || i === 0 ? i + 1 : ""}</span>)}
          </div>
          <p className="mt-4 text-xs leading-relaxed text-ink-3">
            Bright bars are the likely range (8 in 10 simulated races). Races where the car retires are counted in
            the last places, so the right-hand bars include retirements.
          </p>
        </div>
      )}
    </dialog>
  );
}
