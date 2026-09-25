"""Apply the second-half rule to feature_retest.py output: keep a feature if it improves the second
half of the season in >=3 of the seasons tested and on average, without significantly hurting the
whole season.  Usage: python scripts/experiments/evaluate_retest.py experiments_out"""
import glob, sys, numpy as np, pandas as pd
from scipy.stats import linregress
S=sys.argv[1]; R=pd.concat([pd.read_parquet(p) for p in glob.glob(f"{S}/*.parquet")])
R["phase"]=np.where(R.stage==4,"after Q","before Q")
per=R.groupby(["kind","variant","phase","year","round"])[["spearman","win_ll","rps"]].mean().reset_index()
n_rounds=per.groupby("year")["round"].transform("max"); per["late"]=per["round"]>n_rounds/2
per["frac"]=per["round"]/n_rounds
rng=np.random.default_rng(0); out=[]
for (kind,phase),g in per.groupby(["kind","phase"]):
    ctrl=g[g.variant=="control"].set_index(["year","round"])
    for v in [x for x in g.variant.unique() if x!="control"]:
        c=g[g.variant==v].set_index(["year","round"])
        d=(c.spearman-ctrl.spearman).dropna().rename("d").reset_index()
        d["late"]=d["round"]>d.groupby("year")["round"].transform("max")/2
        d["frac"]=d["round"]/d.groupby("year")["round"].transform("max")
        late_by_year=d[d.late].groupby("year").d.mean()
        bo=rng.choice(d.d.to_numpy(),(4000,len(d))).mean(1); lo,hi=np.percentile(bo,[2.5,97.5])
        slope=linregress(d.frac,d.d)
        passes=(int((late_by_year>0).sum())>=max(3,len(late_by_year)-1)) and d[d.late].d.mean()>0 and not hi<0
        out.append({"kind":kind,"phase":phase,"variant":v,"full":d.d.mean(),"full_lo":lo,"full_hi":hi,
                    "early":d[~d.late].d.mean(),"late":d[d.late].d.mean(),
                    **{f"late{y}":late_by_year.get(y,np.nan) for y in (2023,2024,2025,2026)},
                    "late>0 seasons":int((late_by_year>0).sum()),"slope":slope.slope,"slope_p":slope.pvalue,
                    "dRPS":(c.rps-ctrl.rps).mean(),"dwinLL":(c.win_ll-ctrl.win_ll).mean(),"PASS":passes})
T=pd.DataFrame(out); pd.set_option("display.width",260); pd.set_option("display.max_columns",30)
for (kind,phase),g in T.groupby(["kind","phase"]):
    print(f"\n### ridge {kind} | {phase}   (Spearman change vs control; late = 2nd half of each season)")
    print(g.drop(columns=["kind","phase"]).round(4).to_string(index=False))
T.to_parquet(f"{S}/verdict.parquet")
