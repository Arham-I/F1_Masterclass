"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import InfoTip from "@/components/InfoTip";
import PredictionBoard from "@/components/PredictionBoard";
import Gantry, { LIGHTS_HOLD_MS, LIGHT_STEP_MS } from "@/components/Gantry";
import RaceReveal from "@/components/RaceReveal";
import LongRuns from "@/components/charts/LongRuns";
import Stints from "@/components/charts/Stints";
import Timesheet from "@/components/charts/Timesheet";
import WeekendTrend from "@/components/charts/WeekendTrend";
import { useHydrated, useSearch } from "@/lib/client";
import { MODEL_INFO, SESSION_BLURB, modelLabel } from "@/lib/format";
import type { PredRow, Weekend } from "@/lib/types";

const AUTO = "auto";
const AUTOPLAY_MS = 6000;
type Tab = "timesheet" | "longrun" | "tyres";

function fromLink(search: string, last: number, canReveal: boolean, live: boolean) {
  const q = new URLSearchParams(search).get("step");
  if (q === "race" && canReveal) return { i: last, race: true };
  if (q && /^\d+$/.test(q)) return { i: Math.min(Math.max(Number(q), 0), last + 1) - 1, race: false };
  return { i: live ? last : -1, race: false };
}

export default function Replay({ weekend, slug }: { weekend: Weekend; slug: string }) {
  const steps = weekend.steps;
  const last = steps.length - 1;
  const canReveal = !weekend.live;
  const hydrated = useHydrated();
  const search = useSearch();
  // i = -1: before the weekend; 0..last: after that session; race = result revealed.
  // Until the viewer moves, the position comes from the link (?step=3 or ?step=race).
  const [picked, setPicked] = useState<{ i: number; race: boolean } | null>(null);
  const { i, race } = picked ?? fromLink(search, last, canReveal, weekend.live);
  const [playing, setPlaying] = useState(false);
  const [model, setModel] = useState(AUTO);
  const [tab, setTab] = useState<Tab>("timesheet");

  // Keep the address bar in step with the replay so any moment can be shared or bookmarked.
  useEffect(() => {
    if (!hydrated) return;
    const url = new URL(window.location.href);
    if (race) url.searchParams.set("step", "race");
    else if (i >= 0) url.searchParams.set("step", String(i + 1));
    else url.searchParams.delete("step");
    window.history.replaceState(null, "", url);
  }, [i, race, hydrated]);

  const go = useCallback((to: number) => {
    setPicked({ i: Math.min(Math.max(to, -1), last), race: false });
  }, [last]);
  const reveal = () => { setPlaying(false); setPicked({ i: last, race: true }); };

  // Autoplay: one session every few seconds, stopping before the race so the result stays a choice.
  useEffect(() => {
    if (!playing || i >= last) return;
    const t = setTimeout(() => {
      go(i + 1);
      if (i + 1 >= last) setPlaying(false);
    }, i < 0 ? 900 : AUTOPLAY_MS);
    return () => clearTimeout(t);
  }, [playing, i, last, go]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof Element && e.target.closest("input, select, textarea, dialog")) return;
      if (e.key === "ArrowRight") { setPlaying(false); go(i + 1); }
      else if (e.key === "ArrowLeft") { setPlaying(false); go(i - 1); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [i, go]);

  const rowsFor = useCallback((stage: number, m: string): { rows: PredRow[]; used: string } => {
    const p = steps[stage - 1].prediction;
    const used = m === AUTO ? p.auto : m;
    return { rows: p.by[used] ?? p.by[p.auto], used: p.by[used] ? used : p.auto };
  }, [steps]);

  const models = useMemo(() => Object.keys(steps[0].prediction.by), [steps]);
  const step = i >= 0 ? steps[i] : null;
  const now = step ? rowsFor(step.stage, model) : null;
  const prev = i > 0 ? rowsFor(steps[i - 1].stage, model).rows : undefined;
  // Race pace comes from practice long runs; qualifying and Sprint sessions never have them.
  const isPractice = step?.kind === "practice";
  const view: Tab = tab === "longrun" && !isPractice ? "timesheet" : tab;
  const lightsMs = (steps.length + 1) * LIGHT_STEP_MS + LIGHTS_HOLD_MS;

  return (
    <div className="space-y-6">
      <div className="sticky top-0 z-30 -mx-4 border-b border-line bg-bg/95 px-4 py-2.5 backdrop-blur">
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => { if (i >= last) go(-1); setPlaying((p) => !p); }}
            className="cut-sm flex h-11 shrink-0 items-center gap-2 rounded-md bg-accent px-3.5 font-semibold text-white hover:bg-accent-hot sm:px-4"
            aria-label={playing ? "Pause replay" : i >= last ? "Replay from the start" : "Play the weekend"}>
            <span aria-hidden className="text-sm">{playing ? "❚❚" : i >= last ? "↺" : "▶"}</span>
            <span className="hidden text-sm sm:inline">{playing ? "Pause" : i >= last ? "Start again" : i < 0 ? "Play weekend" : "Play"}</span>
          </button>
          <Gantry steps={steps} i={i} race={race} live={weekend.live} playing={playing} autoplayMs={AUTOPLAY_MS}
            onGo={(k) => { setPlaying(false); go(k); }} onReveal={reveal} />
          <div className="hidden shrink-0 flex-col gap-1 sm:flex">
            <button type="button" onClick={() => { setPlaying(false); go(i - 1); }} disabled={i < 0 && !race}
              className="h-5 w-8 rounded bg-surface-2 text-[10px] text-ink-2 hover:text-ink disabled:opacity-30" aria-label="Previous session">◀</button>
            <button type="button" onClick={() => { setPlaying(false); go(i + 1); }} disabled={i >= last}
              className="h-5 w-8 rounded bg-surface-2 text-[10px] text-ink-2 hover:text-ink disabled:opacity-30" aria-label="Next session">▶</button>
          </div>
        </div>
      </div>

      {race ? (
        <div className="after-lights" style={{ ["--delay" as string]: `${lightsMs}ms` }}>
          <RaceReveal weekend={weekend} slug={slug} rowsFor={rowsFor} />
        </div>
      ) : !step ? (
        <Intro weekend={weekend} onStart={() => go(0)} onPlay={() => setPlaying(true)} />
      ) : (
        <div className="space-y-10">
          <section className="grid gap-x-10 gap-y-8 lg:grid-cols-[1.1fr_1fr]" aria-label={`After ${step.session}`}>
            <RaceControl steps={steps.slice(0, i + 1)} />
            <div className="border-t border-line pt-4">
              <h2 className="h3">Who can win
                <InfoTip label="Who can win">The four drivers most likely to win right now, and how their chances moved after each session. Hover over or tap a session for exact numbers. Underneath: the typical miss in places at each point, meaning how many places a finishing car usually ends up from its predicted position. It is this model&apos;s average miss at the same point of the previous 40 race weekends. It usually shrinks as the weekend reveals more, but can rise when Auto switches to a different model.</InfoTip>
              </h2>
              <div className="mt-3">
                <WeekendTrend steps={steps} upto={i} rowsAt={(k) => rowsFor(steps[k].stage, model).rows} drivers={weekend.drivers} />
              </div>
            </div>
          </section>

          <section className="panel cut cut-edge p-4 sm:p-5" aria-labelledby="pred-title">
            <div className="mb-4 flex flex-wrap items-end gap-3">
              <div className="mr-auto">
                <h2 id="pred-title" className="h2">Predicted finishing order</h2>
                <p className="mt-1 text-sm text-ink-2">
                  {weekend.live ? <span className="text-warn">Live forecast: the race hasn&apos;t been run yet. </span> : null}
                  Made after {step.session}, using only what was known then. Select a driver for the full picture.
                </p>
              </div>
              <label className="text-sm text-ink-2">
                <span className="mb-1 flex items-center">Model
                  <InfoTip label="Which model?" align="right">
                    {model === AUTO ? MODEL_INFO["Auto (best record this season)"].blurb : MODEL_INFO[model]?.blurb}
                    {model === AUTO && <> Right now: <b className="text-ink">{modelLabel(now!.used)}</b>.</>}
                  </InfoTip>
                </span>
                <select value={model} onChange={(e) => setModel(e.target.value)}
                  className="rounded border border-line bg-surface-2 px-2.5 py-1.5 text-sm text-ink">
                  <option value={AUTO}>Auto (recommended)</option>
                  {models.map((m) => <option key={m} value={m}>{modelLabel(m)}</option>)}
                </select>
              </label>
            </div>
            <PredictionBoard rows={now!.rows} prev={prev} step={step} drivers={weekend.drivers} />
          </section>

          <section className="border-t border-line pt-5" aria-labelledby="session-title">
            <div className="mb-3 flex flex-wrap items-end gap-3">
              <h2 id="session-title" className="mr-auto h2">{step.session}</h2>
              <div className="flex gap-1 rounded-md bg-surface-2 p-1" role="tablist" aria-label="Session charts">
                {([["timesheet", step.kind === "sprint" ? "Result" : "Timesheet"], ...(isPractice ? [["longrun", "Race pace"]] : []), ["tyres", "Tyres"]] as [Tab, string][]).map(([t, label]) => (
                  <button key={t} type="button" role="tab" aria-selected={view === t}
                    onClick={() => setTab(t)}
                    className={`rounded px-3 py-1.5 text-sm ${view === t ? "bg-ink font-semibold text-bg" : "text-ink-2 hover:text-ink disabled:opacity-35"}`}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <p className="mb-4 max-w-3xl text-sm text-ink-2">
              {view === "timesheet" && (step.kind === "sprint" ? "The official Sprint result." :
                step.kind === "quali" ? "The official qualifying order. Bars show each driver's gap to pole; the fastest lap is in purple, as on the timing screens." :
                "Each driver's fastest lap as a gap to the quickest (in purple). Practice times are a clue only: teams run different fuel loads and tyres.")}
              {view === "longrun" && "Race simulations: runs of 5 or more clean laps back to back on one set of tyres. Each dot is the driver's median long-run lap, compared with the median car of the field on the same tyre compound (the line at 0). −0.50s means half a second a lap quicker than that car. The bar covers the middle half of the driver's long-run laps. Only practice has these runs."}
              {view === "tyres" && "Every run each driver did, coloured by tyre. Softs are fastest but wear quickest; hards are slowest but last longest."}
            </p>
            {view === "timesheet" && <Timesheet step={step} drivers={weekend.drivers} />}
            {view === "longrun" && <LongRuns step={step} drivers={weekend.drivers} />}
            {view === "tyres" && <Stints step={step} drivers={weekend.drivers} />}
            <p className="mt-4 text-xs text-ink-3">{SESSION_BLURB[step.kind]}</p>
          </section>

          {i === last && !weekend.live && (
            <div className="flex flex-wrap items-center gap-4 border-y border-line py-5">
              <div className="mr-auto">
                <p className="h3">Every session before the race is in.</p>
                <p className="text-sm text-ink-2">See how the prediction held up against the real result.</p>
              </div>
              <button type="button" onClick={reveal}
                className="cut-sm rounded-md bg-accent px-5 py-2.5 font-semibold text-white hover:bg-accent-hot">Lights out: show the race</button>
            </div>
          )}
        </div>
      )}
      <p className="text-xs text-ink-3">Use the ← and → keys to step through the weekend.</p>
    </div>
  );
}

/** Commentary in the style of race-control messages: the latest session in full, earlier ones
 *  behind a disclosure so the column keeps a steady height. */
function RaceControl({ steps }: { steps: Weekend["steps"] }) {
  const latest = steps[steps.length - 1];
  const earlier = steps.slice(0, -1).reverse();
  const block = (s: Weekend["steps"][number], current: boolean) => (
    <div key={s.session}>
      <p className="mb-1.5 text-xs">
        <span className={`rounded-sm px-1.5 py-0.5 font-semibold ${current ? "bg-ink text-bg" : "bg-surface-3 text-ink"}`}>{s.short}</span>
      </p>
      <ul className={`space-y-1.5 leading-snug ${current ? "text-[16px]" : "text-[15px] text-ink-2"}`}>
        {s.commentary.map((c) => <li key={c}>{c}</li>)}
      </ul>
    </div>
  );
  return (
    <div className="border-t border-line pt-4">
      <h2 className="h3">Race control</h2>
      <p className="text-sm text-ink-2">What {latest.session} told us.</p>
      <div className="mt-3">{block(latest, true)}</div>
      {earlier.length > 0 && (
        <details className="group mt-4">
          <summary className="cursor-pointer select-none text-sm text-ink-2 hover:text-ink">
            <span className="group-open:hidden">Show</span><span className="hidden group-open:inline">Hide</span> earlier sessions ({earlier.length})
          </summary>
          <div className="mt-3 space-y-4">{earlier.map((s) => block(s, false))}</div>
        </details>
      )}
    </div>
  );
}

function Intro({ weekend, onStart, onPlay }: { weekend: Weekend; onStart: () => void; onPlay: () => void }) {
  // Local times only in the browser: the page is pre-built, so it can't know the viewer's time zone.
  const hydrated = useHydrated();
  const fmt = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  const times: Record<string, string> = hydrated
    ? Object.fromEntries(weekend.steps.filter((s) => s.start_utc).map((s) => [s.session, fmt.format(new Date(s.start_utc!))]))
    : {};
  return (
    <section className="grid gap-8 md:grid-cols-[1.2fr_1fr]" aria-label="How the replay works">
      <div>
        <h2 className="h2">{weekend.live ? "Follow the weekend so far" : "Relive it one session at a time"}</h2>
        <p className="mt-3 max-w-prose text-[16px] leading-relaxed text-ink-2">
          Each session lights one of the start lights. After each one you&apos;ll see what happened, how the race
          prediction moved and how sure it is. Later sessions stay hidden until you reach them, and the race result
          only appears when you choose lights out.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button type="button" onClick={onPlay} className="cut-sm rounded-md bg-accent px-5 py-2.5 font-semibold text-white hover:bg-accent-hot">Play the weekend</button>
          <button type="button" onClick={onStart} className="rounded-md border border-line px-5 py-2.5 font-semibold text-ink hover:bg-surface-2">Step through it myself</button>
        </div>
      </div>
      <div>
        <h3 className="text-sm font-semibold text-ink-2">Sessions{hydrated ? " (your local time)" : ""}</h3>
        <ol className="mt-2 divide-y divide-line border-y border-line">
          {weekend.steps.map((s) => (
            <li key={s.session} className="flex items-center justify-between py-2 text-sm">
              <span>{s.session}</span>
              <span className="text-ink-2">{times[s.session] ?? ""}</span>
            </li>
          ))}
          <li className="flex items-center justify-between py-2 text-sm">
            <span className="font-semibold">Race</span>
            <span className="text-ink-2">{weekend.live ? "Not run yet" : "Revealed at the end"}</span>
          </li>
        </ol>
      </div>
    </section>
  );
}
