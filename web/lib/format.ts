export const pct = (p: number | null | undefined, dp = 2) =>
  p == null ? "–" : `${(p * 100).toFixed(dp)}%`;

export const lapTime = (s: number | null | undefined) => {
  if (s == null) return "–";
  const m = Math.floor(s / 60);
  return `${m}:${(s - m * 60).toFixed(3).padStart(6, "0")}`;
};

export const gap = (s: number | null | undefined) => (s == null ? "–" : s === 0 ? "Fastest" : `+${s.toFixed(3)}s`);

export const slug = (year: number, round: number) => `${year}-${String(round).padStart(2, "0")}`;

export const ordinal = (n: number) => `P${n}`;

// Short, jargon-free names for the predictors (the pipeline's own names are kept as keys).
export const MODEL_INFO: Record<string, { label: string; blurb: string }> = {
  "Auto (best record this season)": {
    label: "Auto (recommended)",
    blurb: "At every stage of the weekend, uses whichever model below has done best so far this season.",
  },
  "Baseline (grid, else practice pace)": {
    label: "Simple rule",
    blurb: "Finishing order = qualifying order (before qualifying: the practice timesheet). The benchmark to beat.",
  },
  "Grid + recovery": {
    label: "Qualifying + comeback",
    blurb: "Qualifying order, but fast cars that qualified out of position are expected to move forward - more so at tracks where overtaking is easy.",
  },
  "Ridge (all seasons)": {
    label: "Stats model (2022-26)",
    blurb: "A statistical model trained on every race since 2022, weighing practice pace, qualifying, team and driver form.",
  },
  "Ridge (2026 only)": {
    label: "Stats model (2026)",
    blurb: "The same statistical model, trained only on this season's races.",
  },
};

export const modelLabel = (name: string) => MODEL_INFO[name]?.label ?? name;

export const COMPOUNDS: Record<string, { color: string; label: string; letter: string }> = {
  SOFT: { color: "#E8383D", label: "Soft", letter: "S" },
  MEDIUM: { color: "#FFD12E", label: "Medium", letter: "M" },
  HARD: { color: "#EDEDED", label: "Hard", letter: "H" },
  INTERMEDIATE: { color: "#43B02A", label: "Intermediate", letter: "I" },
  WET: { color: "#3B8ED0", label: "Wet", letter: "W" },
  UNKNOWN: { color: "#6F6F7A", label: "Unknown", letter: "?" },
};

export const SESSION_BLURB: Record<string, string> = {
  practice: "Practice: teams test set-ups and tyres. Lap times are a clue, not a verdict - fuel loads and programmes differ.",
  sprint_quali: "Sprint Qualifying: a short qualifying session that sets the grid for Saturday's Sprint race.",
  sprint: "The Sprint: a short race (about a third of the distance) with its own points. A strong hint of race pace.",
  quali: "Qualifying: sets the starting grid. The single strongest clue to the race result.",
};
