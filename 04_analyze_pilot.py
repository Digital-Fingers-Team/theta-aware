"""Analyze a pilot/confirm JSON.
eps(theta): incoherent error per RZZ from mirror decay.  delta(theta): coherent over-rotation from phase amplification.
CIs by parametric (binomial) bootstrap.  Constant-eps test per pair: chi^2 against the weighted mean (Holm-corrected).
"""
import json, sys
import numpy as np
from scipy import stats

B = 300
rng = np.random.default_rng(1)
d = json.load(open(sys.argv[1]))
pairs, meta, counts, shots = d["pairs"], d["meta"], d["counts"], d["shots"]

def bit(key, i):
    return key[::-1][i]

def frac(c, pred):
    tot = sum(c.values())
    return sum(v for k, v in c.items() if pred(k)) / tot

def wrap(x):
    return (x + np.pi) % (2 * np.pi) - np.pi

def idx(**kw):
    return next(k for k, m in enumerate(meta) if all(m.get(a) == b for a, b in kw.items()))

def eps_fit(depths, surv):
    s = np.clip(surv, 1e-3, 1)
    slope = np.polyfit(2 * np.asarray(depths), np.log(s), 1)[0]
    return 15 / 16 * (1 - np.exp(slope))

def delta_fit(theta, Ns, x0, y0, x1, y1):
    """Sequential unwrap over doubling N: phi_N = 2N(theta+delta) mod 2pi."""
    est = 0.0
    for n, a, b, c, e in zip(Ns, x0, y0, x1, y1):
        meas = wrap(np.arctan2(b, a) - np.arctan2(e, c))       # 2N(theta+delta) mod 2pi
        pred = 2 * n * (theta + est)
        est = (pred + wrap(meas - pred)) / (2 * n) - theta
    return est

mir_angles = sorted({m["theta"] for m in meta if m["kind"] == "mirror"})
depths = sorted({m["depth"] for m in meta if m["kind"] == "mirror"})
ph_angles = sorted({m["theta"] for m in meta if m["kind"] == "phase"})
Ns = sorted({m["n"] for m in meta if m["kind"] == "phase"})

print(f"Job {d['job_id']} on {d['backend']} | {len(meta)} circuits x {shots} shots | QPU s: {d.get('usage_seconds')}")
if d.get("usage_seconds"):
    print(f"Seconds per circuit: {d['usage_seconds'] / len(meta):.3f}")

results, pvals = {}, []
for i, pr in enumerate(pairs):
    pr = tuple(pr)
    rows = []
    for a in mir_angles:
        s = np.array([frac(counts[idx(kind="mirror", theta=a, depth=dd)],
                           lambda k: bit(k, 2 * i) == "0" and bit(k, 2 * i + 1) == "0") for dd in depths])
        e = eps_fit(depths, s)
        boot = [eps_fit(depths, rng.binomial(shots, s) / shots) for _ in range(B)]
        rows.append((a, e, np.std(boot), np.percentile(boot, 2.5), np.percentile(boot, 97.5)))
    e, se = np.array([r[1] for r in rows]), np.maximum(np.array([r[2] for r in rows]), 1e-6)
    w = 1 / se ** 2
    mean = (w @ e) / w.sum()
    chi2 = float(((e - mean) ** 2 * w).sum())
    p = float(stats.chi2.sf(chi2, len(e) - 1))
    pvals.append(p)
    drow = []
    for a in ph_angles:
        z = {}
        for ctrl in (0, 1):
            for bas in ("X", "Y"):
                z[(ctrl, bas)] = np.array([frac(counts[idx(kind="phase", theta=a, n=n, control=ctrl, basis=bas)],
                                                lambda k: bit(k, 2 * i + 1) == "0") for n in Ns])
        ev = lambda q: 2 * q - 1
        dl = delta_fit(a, Ns, ev(z[0, "X"]), ev(z[0, "Y"]), ev(z[1, "X"]), ev(z[1, "Y"]))
        boot = [delta_fit(a, Ns, *[ev(rng.binomial(shots, z[k]) / shots) for k in
                                   [(0, "X"), (0, "Y"), (1, "X"), (1, "Y")]]) for _ in range(B)]
        drow.append((a, dl, np.percentile(boot, 2.5), np.percentile(boot, 97.5)))
    results[pr] = (rows, mean, chi2, p, drow)

# Holm correction across pairs
order = np.argsort(pvals); m = len(pvals); holm = np.empty(m); run = 0
for r, k in enumerate(order):
    run = max(run, min(1, (m - r) * pvals[k])); holm[k] = run

rep = d["reported_rzz_error"]
for i, pr in enumerate(pairs):
    pr = tuple(pr)
    rows, mean, chi2, p, drow = results[pr]
    print(f"\n=== pair {pr} | IBM-reported {rep.get(str(pr), float('nan')):.5f} | "
          f"constant-eps test: chi2={chi2:.1f}, p={p:.2e}, Holm p={holm[i]:.2e} "
          f"{'REJECT constant' if holm[i] < 0.01 else 'not rejected'}")
    print("  theta    eps        95% CI                 delta(rad)  95% CI")
    dmap = {round(a, 6): (dl, lo, hi) for a, dl, lo, hi in drow}
    for a, e, se, lo, hi in rows:
        dl = dmap.get(round(a, 6))
        ds = f"{dl[0]:+.4f}  [{dl[1]:+.4f}, {dl[2]:+.4f}]" if dl else ""
        print(f"  {a:.3f}   {e:.5f}   [{lo:.5f}, {hi:.5f}]   {ds}")

rej = int((holm < 0.01).sum())
print(f"\nH1 preview: constant-error model rejected (Holm p<0.01) in {rej}/{m} pairs = {100 * rej / m:.0f}%")

if len(sys.argv) > 2:   # save a calibration table for the compiler / compensation test
    cal = {"source_job": d["job_id"], "backend": d["backend"], "pairs": {}}
    for pr in pairs:
        rows, mean, chi2, p, drow = results[tuple(pr)]
        cal["pairs"][str(tuple(pr))] = {
            "theta": [r[0] for r in drow], "delta": [r[1] for r in drow],
            "delta_ci": [[r[2], r[3]] for r in drow],
            "eps_theta": [r[0] for r in rows], "eps": [r[1] for r in rows]}
    json.dump(cal, open(sys.argv[2], "w"), indent=1)
    print("Saved calibration to", sys.argv[2])
