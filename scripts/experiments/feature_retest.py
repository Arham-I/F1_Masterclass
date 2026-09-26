"""Retest candidate features in ridge (all-seasons and same-season ridge), expanding window.

Writes one parquet per (variant, ridge kind) to --out; then run evaluate_retest.py on --out.
Usage (from the repo root; ~5-10 min per run, run several in parallel with xargs -P 4):
    python scripts/experiments/feature_retest.py control all --out experiments_out
    python scripts/experiments/feature_retest.py +gain_form season --out experiments_out
Variants: see VARIANTS below. The decision rule (second-half rule) is in docs/evaluation.md.
"control" is the plain ridge on FEATURES - *without* the after-Qualifying extras in
f1cc/predict/model.py (AFTER_Q) - so each candidate is judged on its own.
"""
import argparse, sys, warnings; warnings.filterwarnings("ignore")
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from f1cc import store
from f1cc.predict import FeatureBuilder, RidgePredictor, BaselinePredictor
from f1cc.predict import base as B
from f1cc.predict.base import FEATURES, fill_for_model, rps, finished
from f1cc.predict.model import MIN_ROWS
from f1cc.replay import Cutoff, apply_cutoff
F = store.read("features")

# --- driver-at-this-track history, from EARLIER seasons at the same location only ----------
CIRCUIT_ALIAS = {"Monte Carlo": "Monaco", "Miami Gardens": "Miami"}     # same circuit, renamed in the feed
circuit = lambda loc: CIRCUIT_ALIAS.get(loc, loc)
q = F[F.session == "Qualifying"][["year", "round", "location", "driver", "team", "position", "gap_to_best_s", "best_lap_s"]]
q = q.assign(qg=q.gap_to_best_s / (q.best_lap_s - q.gap_to_best_s) * 100)
tm = q.groupby(["year", "round", "team"]).qg.transform("sum") - q.qg
cnt = q.groupby(["year", "round", "team"]).qg.transform("count")
q["tmq"] = np.where(cnt == 2, q.qg - tm, np.nan)                         # + = slower than teammate
race = F[F.session == "Race"][["year", "round", "driver", "position"]].rename(columns={"position": "fin"})
hist = q.merge(race, on=["year", "round", "driver"])
hist["qr"] = hist.groupby(["year", "round"]).position.rank(); hist["fr"] = hist.groupby(["year", "round"]).fin.rank()
hist["gain"] = hist.qr - hist.fr
hist["circuit"] = hist.location.map(circuit)                                            # + = gained places vs quali
TRACK_SHRINK = 2.0
def track_hist(year, location, drivers):
    h = hist[(hist.year < year) & (hist.circuit == circuit(location))]
    g = h.groupby("driver").agg(gs=("gain", "sum"), gn=("gain", "count"), ts=("tmq", "sum"), tn=("tmq", "count"))
    g = g.reindex(drivers)
    return ((g.gs / (g.gn + TRACK_SHRINK)).fillna(0).to_numpy(), (g.ts / (g.tn + TRACK_SHRINK)).fillna(0).to_numpy())

# --- in-season race-gain form: places gained vs qualifying among finishers, earlier races only ---
_st = F[F.session == "Race"][["year", "round", "driver", "position", "status"]]
_q = F[F.session == "Qualifying"][["year", "round", "driver", "position"]].rename(columns={"position": "q"})
GAIN = _st.merge(_q, on=["year", "round", "driver"]).dropna(subset=["q"])
GAIN = GAIN[finished(GAIN.status.fillna(""))].copy()
GAIN["gain"] = GAIN.groupby(["year", "round"]).q.rank() - GAIN.groupby(["year", "round"]).position.rank()
GAIN_SHRINK = 3.0

class XB(FeatureBuilder):
    def __init__(self, f, extra=(), lr_fp2=False, pace_w=False, hl=None, after_q_only=False):
        super().__init__(f); self.extra, self.lr_fp2, self.pace_w, self.hl = set(extra), lr_fp2, pace_w, hl
        self.after_q_only = after_q_only
    def _build(self, year, rnd, k):
        out = super()._build(year, rnd, k)
        if out.empty: return out
        w = self.weekend(year, rnd); vis = apply_cutoff(self.features, Cutoff(w, k))
        out = out.set_index("driver"); pr = vis[vis.session.str.startswith("Practice")].copy()
        quali = vis[vis.session == "Qualifying"]
        if self.after_q_only and quali.empty:
            return out.reset_index()
        if "tm_delta" in self.extra:
            qq = quali.assign(qg=quali.gap_to_best_s / (quali.best_lap_s - quali.gap_to_best_s) * 100)
            t = qq.groupby("team").qg.transform("sum") - qq.qg; c = qq.groupby("team").qg.transform("count")
            out["tm_delta"] = pd.Series(np.where(c == 2, qq.qg - t, np.nan), index=qq.driver)
        if "new_soft" in self.extra:
            ns = vis.groupby("driver").new_soft_sets.sum(); out["new_soft"] = ns - ns.median()
        if "penalty" in self.extra and len(quali):
            grid = self.features[(self.features.year == year) & (self.features["round"] == rnd) & (self.features.session == "Race")].set_index("driver").grid
            out["penalty"] = grid.replace(0, 21) - quali.set_index("driver").position    # published grid, known before the start
        if "gain_form" in self.extra:
            h = GAIN[(GAIN.year == year) & (GAIN["round"] < rnd)].groupby("driver").gain.agg(["sum", "count"])
            h = h.reindex(out.index)
            out["gain_form"] = (h["sum"] / (h["count"] + GAIN_SHRINK)).fillna(0.0)
        if "track" in self.extra:
            loc = w.location; g, t = track_hist(year, loc, out.index)
            out["track_gain"], out["track_tm"] = g, t
        if self.pace_w and len(pr):
            pr["w"] = pr.session.str[-1].astype(int); pr["gap_pct"] = pr.gap_to_best_s / (pr.best_lap_s - pr.gap_to_best_s)
            for src, dst in (("pace_rank", "prac_rank"), ("gap_pct", "prac_gap_pct")):
                ok = pr.dropna(subset=[src]); out[dst] = ok.assign(v=ok[src] * ok.w).groupby("driver").v.sum() / ok.groupby("driver").w.sum()
        if self.lr_fp2 and len(pr):
            lr = pr.pivot_table(index="driver", columns="session", values="longrun_rank"); pick = pd.Series(np.nan, index=lr.index)
            for sess in ("Practice 2", "Practice 1", "Practice 3"):
                if sess in lr: pick = pick.combine_first(lr[sess])
            out["lr_rank"] = pick
        if self.hl:
            h = self._races[(self._races.year == year) & (self._races["round"] < rnd)].copy()
            if len(h):
                order = sorted(h["round"].unique()); age = {r: len(order) - i for i, r in enumerate(order)}
                h["w"] = 0.5 ** (h["round"].map(age) / self.hl)
                for key, col, m in (("team", "team_form", B.TEAM_SHRINK), ("driver", "driver_form", B.DRIVER_SHRINK)):
                    g = h.assign(wp=h.position * h.w).groupby(key)[["wp", "w"]].sum()
                    ids = out["team"] if key == "team" else pd.Series(out.index, index=out.index)
                    out[col] = [(g.loc[i, "wp"] + B.PRIOR_POS * m) / (g.loc[i, "w"] + m) if i in g.index else B.PRIOR_POS for i in ids]
        return out.reset_index()

EXTRA_COLS = {"gain_form": ["gain_form"], "tm_delta": ["tm_delta"], "new_soft": ["new_soft"], "penalty": ["penalty"], "track": ["track_gain", "track_tm"]}

class XRidge(RidgePredictor):
    def __init__(self, f, b, same_year_only, cols, lam=None):
        super().__init__(f, b, same_year_only=same_year_only); self.cols, self.lam = cols, lam
    def _fill(self, m):
        x = fill_for_model(m)
        for c in self.cols: x[c] = m[c].astype(float).fillna(0.0).to_numpy() if c in m else 0.0
        return x
    def _training_rows(self, y, r, k):
        key = (y, r, k)
        if key not in self._rows:
            h = self.builder.matrix(y, r, k, with_target=True).dropna(subset=["actual"])
            self._rows[key] = (self._fill(h), h["actual"].to_numpy()) if len(h) >= 10 else None
        return self._rows[key]
    def _score(self, m, year, rnd, k):
        rows = [(yy, self._training_rows(yy, r, k)) for (yy, r) in self.builder.weekends_before(year, rnd)
                if not (self.same_year_only and yy != year)]
        rows = [(yy, x) for yy, x in rows if x is not None]
        if sum(len(x[1]) for _, x in rows) < MIN_ROWS: return BaselinePredictor.score(m)
        X = pd.concat([x[0] for _, x in rows], ignore_index=True); y = np.concatenate([x[1] for _, x in rows])
        W = np.concatenate([[1.0 if (self.lam is None or yy == year) else self.lam] * len(x[1]) for yy, x in rows])
        allc = FEATURES + self.cols
        cols = [c for c in allc if X[c].notna().all() and X[c].std() > 0]
        mu, sd = X[cols].mean(), X[cols].std(); Z = ((X[cols] - mu) / sd).to_numpy()
        ym = np.average(y, weights=W)
        coef = np.linalg.solve(Z.T @ (Z * W[:, None]) + self.alpha * np.eye(len(cols)), Z.T @ (W * (y - ym)))
        T = ((self._fill(m)[cols] - mu) / sd).to_numpy()
        return ym + T @ coef

VARIANTS = {"control": {}, "+tm_delta": dict(extra=["tm_delta"]), "+new_soft": dict(extra=["new_soft"]),
            "+penalty": dict(extra=["penalty"]), "+track": dict(extra=["track"]), "+lr_fp2": dict(lr_fp2=True),
            "+pace_w": dict(pace_w=True), "+form_hl3": dict(hl=3), "+old_x0.5": dict(lam=0.5),
            "+gain_form": dict(extra=["gain_form"]),
            "combo_all": dict(extra=["tm_delta", "new_soft"], after_q_only=True),
            "combo_season": dict(extra=["new_soft"], pace_w=True, after_q_only=True)}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("variant", choices=sorted(VARIANTS)); ap.add_argument("kind", choices=["all", "season"])
    ap.add_argument("--out", default="experiments_out"); ap.add_argument("--years", type=int, nargs="+", default=[2023, 2024, 2025, 2026])
    a = ap.parse_args(); name, kind = a.variant, a.kind; Path(a.out).mkdir(exist_ok=True)
    v = dict(VARIANTS[name]); lam = v.pop("lam", None)
    b = XB(F, **v); cols = sum((EXTRA_COLS[e] for e in v.get("extra", [])), [])
    P = XRidge(F, b, same_year_only=(kind == "season"), cols=cols, lam=lam); rows = []
    for y in a.years:
        for r in sorted(F[(F.year == y) & (F.session == "Race")]["round"].unique()):
            r = int(r); res = b.result(y, r).set_index("driver").position
            for k in (1, 2, 3, 4):
                pr = P.predict(Cutoff(b.weekend(y, r), k)); pr["act"] = pr.driver.map(res); pr = pr.dropna(subset=["act"])
                dist = np.stack(pr.p_pos.to_numpy()); wi = pr.act.idxmin()
                rows.append({"variant": name, "kind": kind, "year": y, "round": r, "stage": k,
                             "spearman": spearmanr(pr.expected_pos, pr.act)[0], "win_ll": -np.log(max(pr.loc[wi, "p_win"], 1e-4)),
                             "rps": rps(dist, pr.act.rank(method="first").to_numpy())})
    pd.DataFrame(rows).to_parquet(f"{a.out}/{name.replace('+','p').replace('.','')}_{kind}.parquet"); print("done", name, kind, flush=True)
