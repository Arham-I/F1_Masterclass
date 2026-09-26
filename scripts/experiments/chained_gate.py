"""Gate for the chained model: Model A = ridge trained on earlier weekends to predict the
QUALIFYING order from what is visible before Qualifying. Compare its order, for both the
qualifying and the race result, with the current pre-Qualifying predictors.
Usage: python scripts/experiments/chained_gate.py   (~15 s; see docs/experiments.md)"""
import sys, warnings; warnings.filterwarnings("ignore")
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from f1cc import store
from f1cc.predict import FeatureBuilder, BaselinePredictor, RidgePredictor
from f1cc.predict.base import FEATURES, fill_for_model
F = store.read("features"); b = FeatureBuilder(F)
QPOS = F[F.session == "Qualifying"].set_index(["year", "round", "driver"]).position
def quali(y, r): return QPOS.xs((y, r), level=(0, 1)) if (y, r) in set(QPOS.index.droplevel(2)) else pd.Series(dtype=float)
class ModelA:
    """Ridge on the same pre-Q features, target = qualifying position (same season or all seasons)."""
    def __init__(self, same_year): self.same_year = same_year; self.rows = {}
    def _rows(self, y, r, k):
        if (y, r, k) not in self.rows:
            m = b.matrix(y, r, k)
            if m["q_pos"].notna().any() or len(m) < 10: self.rows[(y, r, k)] = None   # Q already visible: not a pre-Q stage
            else:
                t = m.driver.map(quali(y, r)); ok = t.notna().to_numpy()
                self.rows[(y, r, k)] = (fill_for_model(m)[ok], t[ok].to_numpy()) if ok.sum() >= 10 else None
        return self.rows[(y, r, k)]
    def score(self, y, r, k):
        m = b.matrix(y, r, k)
        rows = [self._rows(yy, rr, k) for (yy, rr) in b.weekends_before(y, r) if not (self.same_year and yy != y)]
        rows = [x for x in rows if x is not None]
        if sum(len(t) for _, t in rows) < 40: return BaselinePredictor.score(m)
        X = pd.concat([x for x, _ in rows]); t = np.concatenate([t for _, t in rows])
        cols = [c for c in FEATURES if X[c].notna().all() and X[c].std() > 0]
        mu, sd = X[cols].mean(), X[cols].std(); Z = ((X[cols] - mu) / sd).to_numpy()
        w = np.linalg.solve(Z.T @ Z + 10 * np.eye(len(cols)), Z.T @ (t - t.mean()))
        return t.mean() + ((fill_for_model(m)[cols] - mu) / sd).to_numpy() @ w
P = {"baseline (practice / sprint-quali order)": BaselinePredictor(F, b), "ridge all (direct, race target)": RidgePredictor(F, b),
     "ridge season (direct, race target)": RidgePredictor(F, b, same_year_only=True)}
A = {"Model A all (quali target)": ModelA(False), "Model A season (quali target)": ModelA(True)}
rows = []
for y in (2023, 2024, 2025, 2026):
    for r in sorted(F[(F.year == y) & (F.session == "Race")]["round"].unique()):
        r = int(r); w = b.weekend(y, r); res = b.result(y, r).set_index("driver").position; qq = quali(y, r)
        for k in range(1, len(w.replayable) + 1):
            m = b.matrix(y, r, k)
            if m["q_pos"].notna().any(): break                                  # only stages before Qualifying
            for name, s in [(n, p.point(y, r, k)) for n, p in P.items()] + [(n, a.score(y, r, k)) for n, a in A.items()]:
                s = pd.Series(s, index=m.driver)
                rq, rr = s.reindex(qq.index).dropna(), s.reindex(res.index).dropna()
                rows.append({"year": y, "round": r, "stage": k, "model": name,
                             "vs_quali": spearmanr(rq, qq.reindex(rq.index))[0], "vs_race": spearmanr(rr, res.reindex(rr.index))[0]})
R = pd.DataFrame(rows); pd.set_option("display.width", 200); None
per = R.groupby(["model", "year"])[["vs_quali", "vs_race"]].mean().unstack().round(3)
print(per.to_string()); print(R.groupby("model")[["vs_quali", "vs_race"]].mean().round(4).to_string())
base = R[R.model.str.startswith("baseline")].set_index(["year", "round", "stage"])
rng = np.random.default_rng(0)
for n in R.model.unique():
    if n.startswith("baseline"): continue
    g = R[R.model == n].set_index(["year", "round", "stage"])
    for tgt in ("vs_quali", "vs_race"):
        d = (g[tgt] - base[tgt]).groupby(level=[0, 1]).mean().to_numpy(); bo = rng.choice(d, (3000, len(d))).mean(1)
        print(f"{n:32s} {tgt}: {d.mean():+.4f} [{np.percentile(bo,2.5):+.4f},{np.percentile(bo,97.5):+.4f}]")
