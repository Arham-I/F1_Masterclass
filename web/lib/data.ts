// Build-time data access. Runs only while `next build` renders the pages (server components),
// so the files are read from disk once and baked into static HTML.
import "server-only";
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import type { Accuracy, Season, Weekend } from "./types";

const DATA = path.join(process.cwd(), "data");

function read<T>(file: string): T {
  return JSON.parse(readFileSync(path.join(DATA, file), "utf8")) as T;
}

function check(ok: unknown, what: string): asserts ok {
  // Fail the build loudly rather than publish a page with missing or malformed numbers.
  if (!ok) throw new Error(`data check failed: ${what} (re-run scripts/export_site.py)`);
}

export function getSeason(): Season {
  const s = read<Season>("season.json");
  check(Array.isArray(s.rounds) && s.rounds.length > 0, "season.json has no rounds");
  return s;
}

export function getAccuracy(): Accuracy {
  const a = read<Accuracy>("accuracy.json");
  check(a.summary.length > 0, "accuracy.json has no summary");
  return a;
}

export function weekendSlugs(): string[] {
  return readdirSync(path.join(DATA, "weekends"))
    .filter((f) => /^\d{4}-\d{2}\.json$/.test(f))
    .map((f) => f.replace(".json", ""))
    .sort();
}

export function getWeekend(slug: string): Weekend {
  check(/^\d{4}-\d{2}$/.test(slug), `bad weekend id ${slug}`);
  const w = read<Weekend>(path.join("weekends", `${slug}.json`));
  check(w.steps.length > 0, `${slug} has no sessions`);
  for (const s of w.steps) {
    const rows = s.prediction.by[s.prediction.auto];
    check(rows && rows.length > 0, `${slug} ${s.session}: no prediction for ${s.prediction.auto}`);
    const total = rows.reduce((t, r) => t + r.p_win, 0);
    check(Math.abs(total - 1) < 0.02, `${slug} ${s.session}: win chances sum to ${total}`);
  }
  return w;
}
