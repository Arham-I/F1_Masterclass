"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import InfoTip from "@/components/InfoTip";
import PredictionBoard from "@/components/PredictionBoard";
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
  const hasLong = !!step?.longrun.length;
  const view: Tab = tab === "longrun" && !hasLong ? "timesheet" : tab;

  return (
    <div className="space-y-6">
      {/* ---- timeline ---------------------------------------------------------------- */}
      <div className="sticky top-0 z-30 -mx-4 border-b border-line bg-bg/90 px-4 py-3 backdrop-blur">
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => { setPlaying(false); go(i - 1); }} disabled={i < 0 && !race}
            className="hidden h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-2 text-ink-2 hover:text-ink disabled:opacity-30 sm:flex"
            aria-label="Previous session">◀</button>
          <button type="button" onClick={() => { if (i >= last) go(-1); setPlaying((p) => !p); }}
            className="flex h-10 shrink-0 items-center gap-2 rounded-full bg-accent px-4 font-semibold text-white shadow-[0_0_24px_rgba(225,6,0,0.35)] hover:bg-accent-hot"
            aria-label={playing ? "Pause replay" : i >= last ? "Replay from the start" : "Play the weekend"}>
            <span aria-hidden>{playing ? "❚❚" : i >= last ? "↺" : "▶"}</span>
            <span className="hidden text-sm sm:inline">{playing ? "Pause" : i >= last ? "Restart" : i < 0 ? "Play weekend" : "Play"}</span>
          </button>
          <ol className="scroll-x flex min-w-0 flex-1 items-center gap-1" aria-label="Weekend sessions">
            {steps.map((s, k) => {
              const state = race || k < i ? "done" : k === i ? "now" : "next";
              return (
                <li key={s.session} className="min-w-[3.1rem] flex-1 sm:min-w-[4.2rem]">
                  <button type="button" onClick={() => { setPlaying(false); go(k); }} aria-current={k === i && !race ? "step" : undefined}
                    className={`relative w-full overflow-hidden rounded-md px-1 py-2 text-center text-[13px] font-semibold transition-colors sm:px-2 ${
                      state === "now" ? "bg-ink text-bg" : state === "done" ? "bg-surface-3 text-ink" : "bg-surface-2 text-ink-3 hover:text-ink-2"}`}>
                    {s.short}
                    {playing && k === i + 1 && <span key={i} className="autoplay-fill absolute inset-x-0 bottom-0 h-0.5 bg-accent" style={{ ["--autoplay-ms" as string]: `${i < 0 ? 900 : AUTOPLAY_MS}ms` }} />}
                  </button>
                </li>
              );
            })}
            <li className="min-w-[3.9rem] flex-1 sm:min-w-[4.6rem]">
              {canReveal ? (
                <button type="button" disabled={i < last && !race}
                  onClick={reveal}
                  aria-current={race ? "step" : undefined}
                  className={`relative w-full overflow-hidden rounded-md px-1 py-2 text-[13px] font-semibold sm:px-2 ${
                    race ? "bg-accent text-white" : i >= last ? "bg-accent/20 text-ink ring-1 ring-accent" : "bg-surface-2 text-ink-3 opacity-60"}`}
                  title={i < last ? "Finish the replay to reveal the race" : "Reveal the race result"}>
                  <span aria-hidden className="mr-1">🏁</span>Race
                </button>
              ) : (
                <span className="block w-full rounded-md border border-dashed border-line px-2 py-2 text-center text-[13px] text-ink-3">Race</span>
              )}
            </li>
          </ol>
          <button type="button" onClick={() => { setPlaying(false); go(i + 1); }} disabled={i >= last}
            className="hidden h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-2 text-ink-2 hover:text-ink disabled:opacity-30 sm:flex"
            aria-label="Next session">▶</button>
        </div>
      </div>

      {/* ---- body -------------------------------------------------------------------- */}
      {race ? (
        <RaceReveal weekend={weekend} slug={slug} model={model} rowsFor={rowsFor} />
      ) : !step ? (
        <Intro weekend={weekend} onStart={() => { go(0); }} onPlay={() => setPlaying(true)} />
      ) : (
        <div key={step.session} className="space-y-6">
          <section className="grid gap-4 lg:grid-cols-[1.05fr_1fr]" aria-label={`After ${step.session}`}>
            <div className="card rise relative overflow-hidden p-5">
              <div className="stripe absolute inset-y-0 left-0 w-1.5 opacity-80" aria-hidden />
              <p className="eyebrow">After {step.session}</p>
              <h2 className="display mt-1 text-3xl">What we learned</h2>
              <ul className="mt-3 space-y-2.5 text-[15px] leading-relaxed text-ink-2">
                {step.commentary.map((c, k) => (
                  <li key={c} className="rise flex gap-2.5" style={{ animationDelay: `${120 + k * 90}ms` }}>
                    <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rotate-45 bg-accent" />
                    <span>{c}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-4 text-xs text-ink-3">{SESSION_BLURB[step.kind]}</p>
            </div>
            <div className="card p-5">
              <p className="eyebrow">Through the weekend</p>
              <h2 className="display mt-1 text-3xl">Win chances
                <InfoTip label="Win chances">The four drivers most likely to win right now, and how their chances moved after each session. Below: how far off a typical prediction is - it shrinks as the weekend reveals more.</InfoTip>
              </h2>
              <div className="mt-3">
                <WeekendTrend steps={steps} upto={i} rowsAt={(k) => rowsFor(steps[k].stage, model).rows} drivers={weekend.drivers} />
              </div>
            </div>
          </section>

          <section className="card p-4 sm:p-5" aria-labelledby="pred-title">
            <div className="mb-4 flex flex-wrap items-end gap-3">
              <div className="mr-auto">
                <p className="eyebrow">Race prediction · made after {step.session}</p>
                <h2 id="pred-title" className="display mt-1 text-3xl">Predicted finishing order</h2>
                {weekend.live && <p className="mt-1 text-sm text-warn">Live forecast - the race has not been run yet.</p>}
              </div>
              <label className="text-xs text-ink-3">
                <span className="mb-1 flex items-center">Model
                  <InfoTip label="Which model?" align="right">
                    {model === AUTO ? MODEL_INFO["Auto (best record this season)"].blurb : MODEL_INFO[model]?.blurb}
                    {model === AUTO && <> Right now: <b className="text-ink">{modelLabel(now!.used)}</b>.</>}
                  </InfoTip>
                </span>
                <select value={model} onChange={(e) => setModel(e.target.value)}
                  className="rounded-md border border-line bg-surface-2 px-2.5 py-1.5 text-sm text-ink">
                  <option value={AUTO}>Auto (recommended)</option>
                  {models.map((m) => <option key={m} value={m}>{modelLabel(m)}</option>)}
                </select>
              </label>
            </div>
            <Podium rows={now!.rows} weekend={weekend} />
            <p className="mb-2 mt-5 text-xs text-ink-3">Tap a driver for the full picture. Arrows show the change since the previous session.</p>
            <PredictionBoard rows={now!.rows} prev={prev} step={step} drivers={weekend.drivers} />
          </section>

          <section className="card p-4 sm:p-5" aria-labelledby="session-title">
            <div className="mb-4 flex flex-wrap items-end gap-3">
              <div className="mr-auto">
                <p className="eyebrow">{step.session}</p>
                <h2 id="session-title" className="display mt-1 text-3xl">Session data</h2>
              </div>
              <div className="flex gap-1 rounded-lg bg-surface-2 p-1" role="tablist" aria-label="Session charts">
                {([["timesheet", step.kind === "sprint" ? "Result" : "Timesheet"], ["longrun", "Race pace"], ["tyres", "Tyres"]] as [Tab, string][]).map(([t, label]) => (
                  <button key={t} type="button" role="tab" aria-selected={view === t} disabled={t === "longrun" && !hasLong}
                    onClick={() => setTab(t)}
                    className={`rounded-md px-3 py-1.5 text-sm font-medium ${view === t ? "bg-ink text-bg" : "text-ink-2 hover:text-ink disabled:opacity-35"}`}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <p className="mb-4 text-sm text-ink-3">
              {view === "timesheet" && (step.kind === "sprint" ? "Official Sprint result." :
                step.kind === "quali" ? "Official qualifying order. Bars show the gap to pole on each driver's best lap." :
                "Each driver's fastest lap, as a gap to the quickest. Practice times are a clue only: teams run different fuel loads and tyres.")}
              {view === "longrun" && "Race-simulation runs: laps done back-to-back on one set of tyres, compared with the typical car on the same tyre. The dot is the typical lap; the bar shows the middle half of the laps. Further left = faster race pace."}
              {view === "tyres" && "Every run each driver did, coloured by tyre compound (Soft is fastest but wears quickest, Hard is slowest but lasts longest)."}
            </p>
            {view === "timesheet" && <Timesheet step={step} drivers={weekend.drivers} />}
            {view === "longrun" && <LongRuns step={step} drivers={weekend.drivers} />}
            {view === "tyres" && <Stints step={step} drivers={weekend.drivers} />}
          </section>

          {i === last && canReveal && (
            <div className="card flex flex-wrap items-center gap-4 p-5">
              <div className="mr-auto">
                <p className="display text-2xl">That&apos;s every session before the race.</p>
                <p className="text-sm text-ink-2">Ready to see how the prediction held up?</p>
              </div>
              <button type="button" onClick={reveal}
                className="rounded-full bg-accent px-5 py-2.5 font-semibold text-white hover:bg-accent-hot">🏁 Reveal race result</button>
            </div>
          )}
        </div>
      )}
      <p className="text-center text-xs text-ink-3">Tip: use ← → keys to step through the weekend. Each prediction uses only the sessions before it.</p>
    </div>
  );
}

function Podium({ rows, weekend }: { rows: PredRow[]; weekend: Weekend }) {
  const top = rows.slice(0, 3);
  return (
    <ol className="grid grid-cols-3 gap-2 sm:gap-3" aria-label="Predicted podium">
      {top.map((r, k) => {
        const d = weekend.drivers[r.driver];
        return (
          <li key={r.driver} className="rise relative overflow-hidden rounded-xl border border-line bg-surface-2 p-3 sm:p-4" style={{ animationDelay: `${k * 80}ms` }}>
            <span aria-hidden className="absolute inset-x-0 top-0 h-1" style={{ background: d?.color }} />
            <span className="display absolute -right-1 -top-2 text-6xl text-white/5 sm:text-7xl" aria-hidden>{k + 1}</span>
            <p className="eyebrow">P{k + 1}</p>
            <p className="display mt-1 truncate text-2xl sm:text-3xl">{r.driver}</p>
            <p className="hidden truncate text-sm text-ink-2 sm:block">{d?.name}</p>
            <p className="num mt-2 text-sm"><b className="text-ink">{(r.p_win * 100).toFixed(2)}%</b> <span className="text-ink-3">win</span></p>
            <p className="num text-sm"><b className="text-ink">{(r.p_podium * 100).toFixed(2)}%</b> <span className="text-ink-3">podium</span></p>
          </li>
        );
      })}
    </ol>
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
    <section className="card rise grid gap-6 p-6 md:grid-cols-[1.2fr_1fr]" aria-label="How the replay works">
      <div>
        <p className="eyebrow">{weekend.live ? "Live weekend" : "Replay mode"}</p>
        <h2 className="display mt-1 text-4xl">{weekend.live ? "Follow the weekend so far" : "Relive the weekend, one session at a time"}</h2>
        <p className="mt-3 max-w-prose text-[15px] leading-relaxed text-ink-2">
          After each session you&apos;ll see what happened, how our race prediction changed, and how sure it is.
          Nothing from later sessions - and never the race result - is shown until you get there, exactly as it
          looked at the time.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <button type="button" onClick={onPlay} className="rounded-full bg-accent px-5 py-2.5 font-semibold text-white hover:bg-accent-hot">▶ Play weekend</button>
          <button type="button" onClick={onStart} className="rounded-full bg-surface-3 px-5 py-2.5 font-semibold text-ink hover:bg-line">Step through myself</button>
        </div>
      </div>
      <div>
        <p className="eyebrow mb-2">Sessions</p>
        <ol className="space-y-1.5">
          {weekend.steps.map((s) => (
            <li key={s.session} className="flex items-center justify-between rounded-lg bg-surface-2 px-3 py-2 text-sm">
              <span className="font-medium">{s.session}</span>
              <span className="num text-ink-3">{times[s.session] ?? ""}</span>
            </li>
          ))}
          <li className="flex items-center justify-between rounded-lg border border-accent/40 bg-accent/10 px-3 py-2 text-sm">
            <span className="font-semibold">🏁 Race</span>
            <span className="text-ink-3">{weekend.live ? "not run yet" : "revealed at the end"}</span>
          </li>
        </ol>
      </div>
    </section>
  );
}
