import Link from "next/link";
import NextRace from "@/components/NextRace";
import SeasonGrid from "@/components/SeasonGrid";
import { getAccuracy, getSeason } from "@/lib/data";
import { slug } from "@/lib/format";

export default function Home() {
  const season = getSeason();
  const acc = getAccuracy();
  const done = season.rounds.filter((r) => r.status !== "upcoming");
  const latest = done.find((r) => r.status === "live") ?? done[done.length - 1];
  const afterQ = acc.summary.find((s) => s.stage === 4 && s.predictor === acc.auto)!;
  const base = acc.summary.find((s) => s.stage === 4 && s.predictor === acc.baseline)!;
  const wins = Math.round(afterQ.winner_hit * afterQ.races);
  return (
    <div className="space-y-12">
      <section className="grid items-start gap-8 lg:grid-cols-[1.5fr_1fr]">
        <div className="pt-2">
          <h1 className="wide max-w-2xl text-4xl sm:text-[3.0625rem]">Relive every {season.year} weekend, session by session.</h1>
          <p className="mt-5 max-w-xl text-[17px] leading-relaxed text-ink-2">
            Step from first practice to qualifying and watch the race prediction change after every session, using
            only what was known at that point. Then turn the lights out and see how it really finished.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            {latest && (
              <Link href={`/weekend/${slug(season.year, latest.round)}/`}
                className="rounded-md bg-accent px-5 py-3 font-semibold text-white hover:bg-accent-hot">
                {latest.status === "live" ? "Follow" : "Replay"} the {latest.name}
              </Link>
            )}
            <Link href="/guide/" className="rounded-md border border-line px-5 py-3 font-semibold text-ink hover:bg-surface-2">How it works</Link>
          </div>
        </div>
        <NextRace rounds={season.rounds} year={season.year} />
      </section>

      <p className="max-w-3xl text-[16px] leading-relaxed text-ink-2">
        So far this season, predicting after qualifying, our pick has won <b className="text-ink">{wins} of {afterQ.races}</b> races
        and we&apos;ve named <b className="text-ink">{afterQ.podium_hits.toFixed(1)} of the 3</b> podium finishers on average.
        A typical driver finishes <b className="text-ink">{afterQ.mae.toFixed(1)} places</b> from our prediction; simply
        assuming the qualifying order gives {base.mae.toFixed(1)}. <Link href="/accuracy/" className="font-semibold text-ink underline decoration-line underline-offset-4 hover:decoration-ink">See the full record</Link>
      </p>

      <SeasonGrid rounds={season.rounds} drivers={season.drivers} year={season.year} />
    </div>
  );
}
