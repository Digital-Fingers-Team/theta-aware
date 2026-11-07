"""How much the H1 count depends on the bootstrap's random numbers, and on how many pairs are bad. No QPU."""
import json
from pathlib import Path
import numpy as np
from scipy import stats

HERE = Path(__file__).parent
SWEEPS = {"E2": "confirm_db7sns0r1c5c738l7vm0.json", "E7": "sweepK_db7td8or1c5c738l94d0.json", "E8": "sweepM2_db7td8or1c5c738l94dg.json"}

def holm(p):
    p = np.asarray(p); order = np.argsort(p); out = np.empty(len(p)); run = 0
    for r, k in enumerate(order):
        run = max(run, min(1, (len(p) - r) * p[k])); out[k] = run
    return out

def eps_fit(depths, surv):
    slope = np.polyfit(2 * np.asarray(depths), np.log(np.clip(surv, 1e-3, 1)), 1)[0]
    return 15 / 16 * (1 - np.exp(slope))

def eps_many(depths, surv):
    """eps_fit for a whole array of resamples at once."""
    x = 2 * np.asarray(depths, float); y = np.log(np.clip(surv, 1e-3, 1)); xb = x - x.mean()
    return 15 / 16 * (1 - np.exp(((y - y.mean(1, keepdims=True)) * xb).sum(1) / (xb ** 2).sum()))

out = {}
for name, f in SWEEPS.items():
    d = json.load(open(HERE / f)); meta, counts, shots = d["meta"], d["counts"], d["shots"]
    look = {(m["theta"], m["depth"]): k for k, m in enumerate(meta) if m["kind"] == "mirror"}
    angles = sorted({a for a, _ in look}); depths = sorted({b for _, b in look})
    surv = {}
    for i, pr in enumerate(d["pairs"]):
        surv[str(tuple(pr))] = np.array([[sum(v for key, v in counts[look[a, dd]].items() if key[::-1][2 * i] == "0" and key[::-1][2 * i + 1] == "0") / sum(counts[look[a, dd]].values()) for dd in depths] for a in angles])
    rows = {k: [] for k in surv}; totals = []
    for seed in range(40):
        rng = np.random.default_rng(seed); ps = {}
        for pr, s in surv.items():
            e = np.array([eps_fit(depths, x) for x in s])
            se = np.maximum([np.std(eps_many(depths, rng.binomial(shots, x, size=(300, len(depths))) / shots)) for x in s], 1e-6)
            w = 1 / se ** 2; mean = (w @ e) / w.sum(); ps[pr] = stats.chi2.sf(float(((e - mean) ** 2 * w).sum()), len(e) - 1)
        h = holm(list(ps.values())); totals.append(int((h < .01).sum()))
        for pr, x in zip(ps, h): rows[pr].append(float(x))
    out[name] = dict(rejected_min=min(totals), rejected_max=max(totals), rejected_median=float(np.median(totals)), reject_share={k: float(np.mean(np.array(v) < .01)) for k, v in rows.items()}, holm_median={k: float(np.median(v)) for k, v in rows.items()})

# Median gain >= 10% needs over half of circuits to touch a bad pair: the bad-pair share per edge this takes.
out["bad_share_needed"] = {str(e): 1 - .5 ** (1 / e) for e in (7, 15, 31)}
json.dump(out, open(HERE / "h1_sensitivity.json", "w"), indent=1)
print(json.dumps(out, indent=0))
