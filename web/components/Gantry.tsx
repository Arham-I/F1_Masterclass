"use client";

import type { Step } from "@/lib/types";

export const LIGHT_STEP_MS = 420;       // gap between lights coming on, as at a real start
export const LIGHTS_HOLD_MS = 700;      // pause with all lights on before they go out

/** Replay timeline drawn as the start-light gantry: one column of lights per session, lit once the
 *  session is revealed. The last column is the race - revealing it runs the start sequence (lights
 *  on one by one, then all out). */
export default function Gantry({ steps, i, race, live, playing, autoplayMs, onGo, onReveal }: {
  steps: Step[]; i: number; race: boolean; live: boolean; playing: boolean; autoplayMs: number;
  onGo: (k: number) => void; onReveal: () => void;
}) {
  const last = steps.length - 1;
  const cols = steps.length + 1;
  const total = cols * LIGHT_STEP_MS + LIGHTS_HOLD_MS;
  const lamps = (k: number) => {
    const lit = !race && k <= i;
    const seq = race ? { "--delay": `${k * LIGHT_STEP_MS}ms`, "--hold": `${total - k * LIGHT_STEP_MS}ms` } as React.CSSProperties : undefined;
    return (
      <span className="flex justify-center gap-1" aria-hidden>
        <span className={`lamp ${race ? "sequence" : lit ? "on" : ""}`} style={seq} />
        <span className={`lamp ${race ? "sequence" : lit ? "on" : ""}`} style={seq} />
      </span>
    );
  };
  return (
    <ol className="cut flex min-w-0 flex-1 gap-1 bg-[var(--housing)] p-1.5" aria-label="Weekend sessions">
      {steps.map((s, k) => {
        const current = k === i && !race;
        return (
          <li key={s.session} className="min-w-0 flex-1">
            <button type="button" onClick={() => onGo(k)} aria-current={current ? "step" : undefined}
              className={`relative flex w-full flex-col items-center gap-1.5 overflow-hidden rounded px-1 pb-1.5 pt-2 text-[12px] sm:text-[13px] ${
                current ? "bg-surface-2 font-semibold text-ink" : k <= i || race ? "text-ink-2 hover:bg-surface" : "text-ink-3 hover:bg-surface hover:text-ink-2"}`}>
              {lamps(k)}
              <span className="truncate"><span className="sm:hidden">{s.short === "Sprint Quali" ? "SQ" : s.short}</span><span className="hidden sm:inline">{s.short}</span></span>
              {current && <span className="absolute inset-x-2 bottom-0 h-0.5 bg-ink" aria-hidden />}
              {playing && k === i + 1 && (
                <span key={i} className="autoplay-fill absolute inset-x-0 bottom-0 h-0.5 bg-accent" aria-hidden
                  style={{ ["--autoplay-ms" as string]: `${i < 0 ? 900 : autoplayMs}ms` }} />
              )}
            </button>
          </li>
        );
      })}
      <li className="min-w-0 flex-1">
        {live ? (
          <span className="flex w-full flex-col items-center gap-1.5 rounded px-1 pb-1.5 pt-2 text-[12px] text-ink-3 sm:text-[13px]">
            {lamps(steps.length)}
            <span className="truncate">Not run yet</span>
          </span>
        ) : (
          <button type="button" onClick={onReveal} disabled={i < last && !race} aria-current={race ? "step" : undefined}
            title={i < last && !race ? "Finish the replay to reveal the race" : "Reveal the race result"}
            aria-label={race ? "Race result" : "Lights out: reveal the race result"}
            className={`relative flex w-full flex-col items-center gap-1.5 rounded px-1 pb-1.5 pt-2 text-[12px] sm:text-[13px] ${
              race ? "bg-surface-2 font-semibold text-ink" : i >= last ? "font-semibold text-ink ring-1 ring-accent hover:bg-surface" : "text-ink-3 opacity-60"}`}>
            {lamps(steps.length)}
            <span className="truncate"><span className="sm:hidden">Race</span><span className="hidden sm:inline">{race ? "Race" : "Lights out"}</span></span>
            {race && <span className="absolute inset-x-2 bottom-0 h-0.5 bg-ink" aria-hidden />}
          </button>
        )}
      </li>
    </ol>
  );
}
