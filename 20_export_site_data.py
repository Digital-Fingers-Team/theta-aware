import json, sys
src = open("17_paper_analysis.py").read().split("\n")
code = "\n".join(src[:146])
import matplotlib; matplotlib.use("Agg")
import matplotlib.figure
matplotlib.figure.Figure.savefig = lambda *a, **k: None
g = {"__file__": "/home/opc/theta-aware/17_paper_analysis.py", "__name__": "x"}
exec(compile(code, "17", "exec"), g)
S, ROUND = g["S"], g["ROUND"]
out = {"sweeps": {}, "rounds": {}}
for k, v in S.items():
    out["sweeps"][k] = dict(backend=v["backend"], depths=v["depths"], pairs={p: {kk: q[kk] for kk in ("theta","eps","lo","hi","reported","holm","phase_theta","delta")} for p, q in v["pairs"].items()})
for k, v in ROUND.items():
    cal = {p: {kk: c[kk] for kk in c if kk in ("th","alpha","beta","eff")} for p, c in v["cal"].items()}
    out["rounds"][k] = dict(backend=v["backend"], cal=cal, cases=v["cases"])
print(list(next(iter(ROUND["E4"]["cal"].values())).keys()))
json.dump(out, open("site/data/site_data.json","w"), default=float)
print("ok")
