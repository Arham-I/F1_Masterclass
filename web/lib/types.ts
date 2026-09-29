// Shapes of the JSON written by scripts/export_site.py (f1cc/site_export.py).

export type Driver = { name: string; number: string | null; team: string; color: string };
export type Drivers = Record<string, Driver>;

export type SessionTime = { name: string; start_utc: string | null };

export type PredRow = {
  driver: string;
  pos: number;          // predicted finishing position
  sigma: number;        // spread of the simulated shuffle, in places (typical miss = sigma / 1.25)
  p_win: number;
  p_podium: number;
  p_points: number;
  p_dnf: number;
  lo: number;           // 80% likely range
  hi: number;
  dist: number[];       // chance of each finishing position (retirements count as the last places)
};

export type Step = {
  session: string;
  short: string;
  kind: "practice" | "sprint_quali" | "sprint" | "quali";
  stage: number;
  start_utc: string | null;
  timesheet: { driver: string; pos: number; best: number | null; gap: number | null; laps: number; status: string | null }[];
  longrun: { driver: string; n: number; median: number; q1: number; q3: number }[];
  stints: { driver: string; compound: string; start: number; end: number }[];
  // "official" = the real grid (from the race, or hand-entered after penalties are published);
  // "provisional" = qualifying order standing in during a live weekend; null = none shown.
  grid_state: "official" | "provisional" | null;
  grid: { driver: string; grid: number | null; penalty: string | null }[];
  prediction: { auto: string; by: Record<string, PredRow[]> };
  commentary: string[];
};

export type Weekend = {
  year: number;
  round: number;
  name: string;
  location: string;
  date: string;
  live: boolean;
  format: "sprint" | "conventional";
  race_start_utc: string | null;
  drivers: Drivers;
  steps: Step[];
};

export type RoundSummary = {
  round: number;
  name: string;
  location: string;
  country: string;
  format: string;
  sessions: SessionTime[];
  status: "finished" | "live" | "upcoming";
  winner?: string;
  favourite?: { driver: string; p_win: number };
};

export type Season = { year: number; rounds: RoundSummary[]; drivers: Drivers };

export type Score = { spearman: number; winner_hit: number; podium_hits: number; mae: number };

export type RaceResult = {
  year: number;
  round: number;
  result: { driver: string; pos: number; grid: number | null; status: string; finished: boolean }[];
  scores: Record<string, Record<string, Score>>;   // stage -> predictor -> score
  auto: Record<string, string>;
  commentary: string[];
};

export type Accuracy = {
  year: number;
  holdout_from: number;
  frozen_tag: string;
  baseline: string;
  auto: string;
  summary: (Score & { stage: number; predictor: string; races: number })[];
  per_round: (Score & { round: number; stage: number; predictor: string })[];
};
