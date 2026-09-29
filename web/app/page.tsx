import Link from "next/link";
import SeasonGrid from "@/components/SeasonGrid";
import { getAccuracy, getSeason } from "@/lib/data";
import { slug } from "@/lib/format";

export default function Home() {
  const season = getSeason();
  const acc = getAccuracy();
  const done = season.rounds.filter((r) => r.status !== "upcoming");
  const latest = [...done].reverse().find((r) => r.status === "live") ?? done[done.length - 1];
  const afterQ = acc.summary.find((s) => s.stage === 4 && s.predictor === acc.auto)!;
  const base = acc.summary.find((s) => s.stage === 4 && s.predictor === acc.baseline)!;
  const wins = Math.round(afterQ.winner_hit * afterQ.races);
  return (
    <div className="space-y-12">
      <section className="relative overflow-hidden rounded-2xl border border-line bg-surface p-6 sm:p-10">
        <div aria-hidden className="stripe absolute -right-10 top-0 h-full w-40 -skew-x-12 opacity-20" />
        <div aria-hidden className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-accent/25 blur-3xl" />
        <p className="eyebrow relative">Formula 1 · {season.year} season</p>
        <h1 className="display relative mt-3 max-w-3xl text-5xl sm:text-7xl">
          Every session.<br /><span className="text-accent">Every twist.</span><br />One prediction.
        </h1>
        <p className="relative mt-5 max-w-xl text-[17px] leading-relaxed text-ink-2">
          Replay each {season.year} race weekend from first practice to qualifying and watch the race prediction
          sharpen after every session - then reveal how it really ended.
        </p>
        <div className="relative mt-7 flex flex-wrap gap-3">
          {latest && (
            <Link href={`/weekend/${slug(season.year, latest.round)}/`}
              className="rounded-full bg-accent px-6 py-3 font-semibold text-white shadow-[0_0_30px_rgba(225,6,0,0.4)] hover:bg-accent-hot">
              ▶ {latest.status === "live" ? "Follow" : "Replay"} the {latest.name.replace(" Grand Prix", " GP")}
            </Link>
          )}
          <Link href="/guide/" className="rounded-full bg-surface-3 px-6 py-3 font-semibold text-ink hover:bg-line">How it works</Link>
        </div>
      </section>

      <section aria-labelledby="record-title" className="grid gap-3 sm:grid-cols-3">
        <h2 id="record-title" className="sr-only">Prediction record this season</h2>
        <Link href="/accuracy/" className="card group p-5 hover:border-ink-3">
          <p className="eyebrow">Winner picked</p>
          <p className="display mt-2 text-5xl">{wins}<span className="text-2xl text-ink-3"> / {afterQ.races}</span></p>
          <p className="mt-1 text-sm text-ink-2">races, predicting after qualifying</p>
        </Link>
        <Link href="/accuracy/" className="card group p-5 hover:border-ink-3">
          <p className="eyebrow">Podium finishers called</p>
          <p className="display mt-2 text-5xl">{afterQ.podium_hits.toFixed(1)}<span className="text-2xl text-ink-3"> / 3</span></p>
          <p className="mt-1 text-sm text-ink-2">on average per race</p>
        </Link>
        <Link href="/accuracy/" className="card group p-5 hover:border-ink-3">
          <p className="eyebrow">Typical miss</p>
          <p className="display mt-2 text-5xl">{afterQ.mae.toFixed(1)}<span className="text-2xl text-ink-3"> places</span></p>
          <p className="mt-1 text-sm text-ink-2">
            per driver · simple &ldquo;qualifying order&rdquo; rule: {base.mae.toFixed(1)} <span className="text-accent-hot group-hover:underline">details →</span>
          </p>
        </Link>
      </section>

      <SeasonGrid rounds={season.rounds} drivers={season.drivers} year={season.year} />
    </div>
  );
}
