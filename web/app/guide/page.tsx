import type { Metadata } from "next";
import Link from "next/link";
import { COMPOUNDS } from "@/lib/format";

export const metadata: Metadata = { title: "Guide", description: "What the numbers and charts mean, in plain words." };

const SESSIONS = [
  ["Practice 1, 2 & 3 (FP1-FP3)", "An hour each for teams to test set-ups and tyres. Useful clues, but fuel loads and programmes vary, so the fastest lap doesn't always mean the fastest car."],
  ["Sprint Qualifying", "On Sprint weekends only: a short qualifying session that sets the grid for the Sprint."],
  ["Sprint", "A short Saturday race, about a third of a Grand Prix, with its own points. A good preview of race pace."],
  ["Qualifying", "Three knockout rounds that set the starting grid. The single strongest clue to Sunday's result: most races are won from the front two rows."],
  ["Race", "The Grand Prix itself. In a replay the result stays hidden until you select Lights out."],
];

const NUMBERS = [
  ["Predicted finish", "Our best guess at each driver's finishing position."],
  ["Win / Podium / Points chance", "We simulate the race 20,000 times, adding realistic randomness: driver errors, strategy swings, retirements. The chance is the share of those races in which the driver won, finished top 3, or finished top 10 (the points places)."],
  ["Retirement chance", "Chance of not reaching the finish, based on how often this team's cars have retired, blended with the long-term average."],
  ["Likely finish range", "The race is simulated 20,000 times. The range covers the positions the driver finished in 8 out of 10 of those races: 1 in 10 went better, 1 in 10 worse. A narrow range means a confident prediction."],
  ["Typical miss (± places)", "How many places a car that finishes usually ends up either side of its predicted position: this model's average miss at the same point of the previous 40 race weekends (across seasons, not only this one). It is an average, not a limit: plenty of cars land further out, and a few are spot on. It is smaller for the front-runners and larger down the order, and it usually shrinks as the weekend goes on; before qualifying the model has to guess the grid too. The simulated races use it to set how much the order can shuffle. The Accuracy page also reports a typical miss over all cars, which is larger because a retirement counts as a big miss."],
  ["Order score", "How closely a predicted order matches the real one, from 0 (no better than random) to 1 (perfect). Also known as Spearman rank correlation."],
];

const CHARTS = [
  ["Timesheet", "Each driver's fastest lap as a gap to the quickest. In qualifying it is the official order."],
  ["Race pace", "Practice only. Teams run 5 or more laps back to back on one set of tyres with race fuel, known as a race simulation. Each dot is a driver's median lap on those runs, compared with the median car of the field on the same tyre compound. Left of the line means quicker than that car over a long run, often a better race clue than one fast lap."],
  ["Tyres", "Every run each driver did, coloured by tyre. Teams use practice to learn how long each compound lasts."],
  ["Who can win", "How the top contenders' chances moved after each session: who is gaining and who is fading."],
  ["Predicted against actual", "After the race: a filled dot for where the driver finished and an outlined marker for each model's prediction. You can compare up to three models at once."],
  ["Timing colours", "As on the TV timing screens, purple marks the fastest of the session and green marks a gain."],
];

export default function GuidePage() {
  return (
    <div className="space-y-12">
      <header>
        <h1 className="wide text-4xl sm:text-5xl">What everything means</h1>
        <p className="mt-4 max-w-2xl text-[16px] leading-relaxed text-ink-2">
          Plain explanations of the sessions, numbers and charts on this site, and of how the prediction is made.
        </p>
      </header>

      <section aria-labelledby="how">
        <h2 id="how" className="h2">How to use the replay</h2>
        <ol className="mt-4 grid gap-6 border-t border-line pt-4 sm:grid-cols-3">
          {[
            ["1", "Pick a weekend", "Choose any race from the season calendar on the home page."],
            ["2", "Play or step through", "Press Play for an automatic run-through, or select each session. The arrow keys work too. Each session lights one of the start lights."],
            ["3", "Lights out", "After qualifying, select Lights out to reveal the real result and see how the prediction held up."],
          ].map(([n, t, d]) => (
            <li key={n}>
              <span className="wide num text-3xl text-ink-3">{n}</span>
              <p className="mt-1 font-semibold">{t}</p>
              <p className="mt-1 text-sm text-ink-2">{d}</p>
            </li>
          ))}
        </ol>
      </section>

      <Terms id="sessions" title="The sessions" rows={SESSIONS} />
      <Terms id="numbers" title="The numbers" rows={NUMBERS} />
      <Terms id="charts" title="The charts" rows={CHARTS} />

      <section aria-labelledby="tyres">
        <h2 id="tyres" className="h2">Tyre colours</h2>
        <ul className="mt-4 grid gap-3 sm:grid-cols-5">
          {(["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"] as const).map((c) => (
            <li key={c} className="flex items-center gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-4 border-bg text-sm font-bold text-black outline outline-2" style={{ background: COMPOUNDS[c].color, outlineColor: COMPOUNDS[c].color }}>{COMPOUNDS[c].letter}</span>
              <span>
                <span className="block font-semibold">{COMPOUNDS[c].label}</span>
                <span className="text-xs text-ink-3">{{ SOFT: "fastest, wears quickly", MEDIUM: "the all-rounder", HARD: "slowest, lasts longest", INTERMEDIATE: "damp track", WET: "heavy rain" }[c]}</span>
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="model" className="grid gap-6 lg:grid-cols-2">
        <div>
          <h2 id="model" className="h2">How the prediction works</h2>
          <ol className="mt-4 space-y-3 text-[15px] leading-relaxed text-ink-2">
            <li><b className="text-ink">1. Rank the field.</b> Start from the best evidence so far: qualifying order if it has happened, otherwise practice and Sprint pace, team and driver form.</li>
            <li><b className="text-ink">2. Allow for comebacks.</b> A fast car that qualified out of position tends to move forward, more so at tracks where overtaking is easy.</li>
            <li><b className="text-ink">3. Race it 20,000 times.</b> Each simulated race adds random swings and retirements, sized by how wrong past predictions have been at this stage.</li>
            <li><b className="text-ink">4. Count the outcomes.</b> Win, podium and points chances are simply how often each happened in those races.</li>
          </ol>
        </div>
        <div>
          <h2 className="h2">Which model?</h2>
          <p className="mt-3 text-[15px] leading-relaxed text-ink-2">
            Several models compete, from a simple &ldquo;qualifying order&rdquo; rule to statistical models trained on every
            race since 2022. <b className="text-ink">Auto</b> (the default) uses whichever has the best record so far this
            season at that point in the weekend. You can switch models above the prediction table.
          </p>
          <Link href="/accuracy/" className="mt-4 inline-block font-semibold text-ink underline decoration-line underline-offset-4 hover:decoration-ink">See how accurate each model is</Link>
        </div>
      </section>
    </div>
  );
}

function Terms({ id, title, rows }: { id: string; title: string; rows: string[][] }) {
  return (
    <section aria-labelledby={id}>
      <h2 id={id} className="h2">{title}</h2>
      <dl className="mt-4 divide-y divide-line border-y border-line">
        {rows.map(([k, v]) => (
          <div key={k} className="grid gap-1 py-4 sm:grid-cols-[14rem_1fr] sm:gap-6">
            <dt className="font-semibold">{k}</dt>
            <dd className="text-[15px] leading-relaxed text-ink-2">{v}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
