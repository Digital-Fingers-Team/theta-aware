"""Everything the paper states, recomputed from the raw job files. No QPU is used and no key is read.

Part 1: measured results (E2, E4, E6, E7, E8, E10).
Part 2: model checks against those measurements.
Part 3: projections for the full experiment. They are model outputs, not data.
Writes paper_results.json and figures/*.png.
"""
import json
from pathlib import Path
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
FIG = HERE / "figures"; FIG.mkdir(exist_ok=True)
rng = np.random.default_rng(20261107)
INK, GREY, BLUE, ORANGE, GREEN, RED = "#0b0b0b", "#8a8984", "#2a78d6", "#d9822b", "#2f9e6e", "#c8413b"
plt.rcParams.update({"font.size": 8.5, "axes.spines.top": False, "axes.spines.right": False, "font.family": "DejaVu Sans",
                     "axes.edgecolor": "#55544f", "axes.linewidth": 0.7, "legend.frameon": False, "figure.dpi": 200})
R = {}

SWEEPS = {"E2": "confirm_db7sns0r1c5c738l7vm0.json", "E7": "sweepK_db7td8or1c5c738l94d0.json", "E8": "sweepM2_db7td8or1c5c738l94dg.json"}
ROUNDS = {"E4": "round2_db7t6ier6oqs738898ig.json", "E6": "round2k_db7teq6il99s73forh20.json"}
wrap = lambda x: (x + np.pi) % (2 * np.pi) - np.pi
bit = lambda key, i: key[::-1][i]

def frac(c, pred):
    return sum(v for k, v in c.items() if pred(k)) / sum(c.values())

def eps_fit(depths, surv):
    slope = np.polyfit(2 * np.asarray(depths), np.log(np.clip(surv, 1e-3, 1)), 1)[0]
    return 15 / 16 * (1 - np.exp(slope))

def delta_fit(theta, Ns, x0, y0, x1, y1):
    est = 0.0
    for n, a, b, c, e in zip(Ns, x0, y0, x1, y1):
        meas = wrap(np.arctan2(b, a) - np.arctan2(e, c))
        pred = 2 * n * (theta + est)
        est = (pred + wrap(meas - pred)) / (2 * n) - theta
    return est

def holm(p):
    p = np.asarray(p); order = np.argsort(p); out = np.empty(len(p)); run = 0
    for r, k in enumerate(order):
        run = max(run, min(1, (len(p) - r) * p[k])); out[k] = run
    return out

def wilson(k, n, z=1.96):
    c = (k + z * z / 2) / (n + z * z); h = z * np.sqrt(k * (n - k) / n + z * z / 4) / (n + z * z)
    return c - h, c + h

def analyse_sweep(name):
    d = json.load(open(HERE / SWEEPS[name]))
    meta, counts, shots = d["meta"], d["counts"], d["shots"]
    lookup = {tuple(sorted(m.items())): k for k, m in enumerate(meta)}
    idx = lambda **kw: lookup[tuple(sorted(kw.items()))]
    mir = sorted({m["theta"] for m in meta if m["kind"] == "mirror"})
    depths = sorted({m["depth"] for m in meta if m["kind"] == "mirror"})
    pha = sorted({m["theta"] for m in meta if m["kind"] == "phase"})
    Ns = sorted({m["n"] for m in meta if m["kind"] == "phase"})
    out, pvals = {}, []
    for i, pr in enumerate(d["pairs"]):
        eps, ses, los, his, A = [], [], [], [], []
        for a in mir:
            s = np.array([frac(counts[idx(kind="mirror", theta=a, depth=dd)], lambda k: bit(k, 2 * i) == "0" and bit(k, 2 * i + 1) == "0") for dd in depths])
            boot = [eps_fit(depths, rng.binomial(shots, s) / shots) for _ in range(300)]
            eps.append(eps_fit(depths, s)); ses.append(np.std(boot)); los.append(np.percentile(boot, 2.5)); his.append(np.percentile(boot, 97.5))
        eps, ses = np.array(eps), np.maximum(np.array(ses), 1e-6)
        w = 1 / ses ** 2; mean = (w @ eps) / w.sum(); chi2 = float(((eps - mean) ** 2 * w).sum())
        p = float(stats.chi2.sf(chi2, len(eps) - 1)); pvals.append(p)
        dl = []
        for a in pha:
            z = {}
            for ctrl in (0, 1):
                for bas in ("X", "Y"):
                    z[ctrl, bas] = 2 * np.array([frac(counts[idx(kind="phase", theta=a, n=n, control=ctrl, basis=bas)], lambda k: bit(k, 2 * i + 1) == "0") for n in Ns]) - 1
            dl.append(delta_fit(a, Ns, z[0, "X"], z[0, "Y"], z[1, "X"], z[1, "Y"]))
        rep = d["reported_rzz_error"].get(str(tuple(pr)))
        out[str(tuple(pr))] = dict(theta=mir, eps=eps.tolist(), se=ses.tolist(), lo=los, hi=his, p=p, chi2=chi2, reported=rep, phase_theta=pha, delta=dl)
    for key, h in zip(out, holm(pvals)):
        out[key]["holm"] = float(h)
    return dict(backend=d["backend"], job=d["job_id"], depths=depths, Ns=Ns, shots=shots, usage=d.get("usage_seconds"), pairs=out)

S = {k: analyse_sweep(k) for k in SWEEPS}
R["h1_measured"] = {}
for k, v in S.items():
    rej = sum(p["holm"] < 0.01 for p in v["pairs"].values())
    R["h1_measured"][k] = dict(backend=v["backend"], rejected=rej, pairs=len(v["pairs"]), holm={a: b["holm"] for a, b in v["pairs"].items()})
kk = sum(x["rejected"] for x in R["h1_measured"].values()); nn = sum(x["pairs"] for x in R["h1_measured"].values())
R["h1_measured"]["pooled"] = dict(rejected=kk, pairs=nn, wilson=wilson(kk, nn))

# Figure 1: eps(theta) for three contrasting pairs, with IBM's single number.
fig, axes = plt.subplots(1, 3, figsize=(7.1, 2.25), sharey=True)
for ax, (exp, pr) in zip(axes, [("E2", "(10, 11)"), ("E2", "(14, 15)"), ("E7", "(16, 23)")]):
    p = S[exp]["pairs"][pr]; t = np.array(p["theta"]); e = np.array(p["eps"])
    ax.errorbar(t, e, yerr=[np.maximum(e - p["lo"], 0), np.maximum(np.array(p["hi"]) - e, 0)], fmt="o-", ms=3, lw=1, color=BLUE, capsize=1.5, elinewidth=.7)
    ax.axhline(p["reported"], color=RED, ls="--", lw=1); ax.set_yscale("log"); ax.set_xlabel("θ (rad)")
    ax.set_title(f"{pr}, {S[exp]['backend']}", fontsize=8.5, loc="left")
axes[0].set_ylabel("incoherent error ε(θ)"); axes[0].text(.75, S["E2"]["pairs"]["(10, 11)"]["reported"] * 1.25, "IBM-reported", color=RED, fontsize=7.5)
fig.tight_layout(); fig.savefig(FIG / "fig1_eps.png"); plt.close(fig)

# Rounds: gains and calibration.
def pid(cnt, i, ideal):
    t = sum(cnt.values()); return sum(v for k, v in cnt.items() if bit(k, 2 * i) + bit(k, 2 * i + 1) == ideal) / t
ROUND = {}
R["compensation"] = {}
for name, f in ROUNDS.items():
    d = json.load(open(HERE / f)); meta = d["test_meta"]; counts = d["test_counts"]
    cases = []
    for i, pr in enumerate(d["pairs"]):
        for j in sorted({m["j"] for m in meta}):
            for mult in (1, 2):
                ideal = "11" if mult == 1 else "00"
                row = dict(pair=str(tuple(pr)), j=j, mult=mult)
                for v in ("raw", "local", "local+delta"):
                    k = next(k for k, m in enumerate(meta) if m["j"] == j and m["mult"] == mult and m["variant"] == v)
                    row[v] = pid(counts[k], i, ideal)
                cases.append(row)
    ROUND[name] = dict(cases=cases, cal=d["calibration"], backend=d["backend"], pairs=[str(tuple(p)) for p in d["pairs"]])
    raw = np.array([c["raw"] for c in cases]); res = {}
    for v in ("local", "local+delta"):
        x = np.array([c[v] for c in cases]); rel = (x - raw) / np.maximum(raw, 1e-3)
        res[v] = dict(mean_gain=float((x - raw).mean()), median_gain=float(np.median(x - raw)), median_rel=float(np.median(rel)), p=float(stats.wilcoxon(x, raw, alternative="greater").pvalue), n=len(x), improved=int((x > raw).sum()))
    per = {}
    for pr in ROUND[name]["pairs"]:
        c = [q for q in cases if q["pair"] == pr]
        per[pr] = dict(mean_gain=float(np.mean([q["local"] - q["raw"] for q in c])), improved=sum(q["local"] > q["raw"] for q in c), n=len(c), raw_mean=float(np.mean([q["raw"] for q in c])))
    res["per_pair"] = per
    R["compensation"][name] = res

# Figure 2: local phases and delta, marrakesh.
fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.4))
cal = ROUND["E4"]["cal"]; ax = axes[0]
for pr, c in cal.items():
    bad = pr == "(10, 11)"
    ax.plot(c["th"], c["beta"], "o-", ms=2.5, lw=1.2 if bad else .7, color=RED if bad else GREY, alpha=1 if bad else .7, label="(10, 11)" if bad else None)
ax.set_xlabel("θ (rad)"); ax.set_ylabel("local phase β (rad per gate)"); ax.legend(loc="lower right"); ax.axhline(0, color=INK, lw=.4)
ax = axes[1]
for pr in S["E2"]["pairs"]:
    if pr == "(93, 94)": continue
    p = S["E2"]["pairs"][pr]; bad = pr == "(10, 11)"
    ax.plot(p["phase_theta"], p["delta"], "o-", ms=2.5, lw=1.2 if bad else .7, color=RED if bad else GREY, alpha=1 if bad else .7)
ax.set_xlabel("θ (rad)"); ax.set_ylabel("over-rotation δ (rad)"); ax.axhline(0, color=INK, lw=.4)
fig.tight_layout(); fig.savefig(FIG / "fig2_coherent.png"); plt.close(fig)

# Figure 3: raw vs local, both devices.
fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.8), sharey=True)
for ax, name in zip(axes, ("E4", "E6")):
    for c in ROUND[name]["cases"]:
        col = RED if c["pair"] in ("(10, 11)", "(0, 1)") else BLUE
        ax.plot(c["raw"], c["local"], "o", ms=3, color=col, alpha=.7, mec="none")
    ax.plot([0, 1], [0, 1], color=INK, lw=.6); ax.set_xlabel("P(success), no correction"); ax.set_title(f"{name}, {ROUND[name]['backend']}", fontsize=8.5, loc="left")
axes[0].set_ylabel("P(success), virtual-RZ correction")
axes[0].text(.42, .03, "red: pair (10, 11)", color=RED, fontsize=7.5); axes[1].text(.42, .03, "red: pair (0, 1)", color=RED, fontsize=7.5)
fig.tight_layout(); fig.savefig(FIG / "fig3_correction.png"); plt.close(fig)

# E10.
cz = json.load(open(HERE / "czbase_db7u6r0r1c5c738lalhg.json")); tab = {}
for m, c in zip(cz["meta"], cz["counts"]):
    ideal = "11" if m["K"] * m["j"] == 24 else "00"
    tab.setdefault(f"{m['j']}π/24, K={m['K']}", {})[m["variant"]] = c.get(ideal, 0) / sum(c.values())
R["e10"] = tab
fig, ax = plt.subplots(figsize=(4.6, 2.3)); lab = list(tab); w = .27
for o, (v, col, name) in enumerate((("raw", GREY, "fractional"), ("local", BLUE, "fractional + RZ"), ("cz", GREEN, "standard 2-CZ"))):
    ax.bar(np.arange(4) + (o - 1) * w, [tab[l][v] for l in lab], w, color=col, label=name)
ax.set_xticks(range(4)); ax.set_xticklabels(lab, fontsize=7.5); ax.set_ylabel("P(success)"); ax.set_ylim(0, 1); ax.legend(ncol=3, fontsize=7, loc="upper center", bbox_to_anchor=(.5, 1.2))
fig.tight_layout(); fig.savefig(FIG / "fig4_cz.png"); plt.close(fig)

# Stability E2 vs E8.
st = {}
for pr in S["E2"]["pairs"]:
    if pr == "(93, 94)": continue
    a, b = S["E2"]["pairs"][pr], S["E8"]["pairs"][pr]
    st[pr] = dict(delta_r=float(np.corrcoef(a["delta"], b["delta"])[0, 1]), delta_max=float(np.max(np.abs(np.array(a["delta"]) - b["delta"]))), eps_r=float(np.corrcoef(a["eps"], b["eps"])[0, 1]))
R["stability"] = st

# ---------- Part 2: gate model against the correction tests ----------
ZZ = np.array([1, -1, -1, 1.0])
ZA, ZB = np.array([1, 1, -1, -1.0]), np.array([1, -1, 1, -1.0])
H2 = np.array([[1, 1, 1, 1], [1, -1, 1, -1], [1, 1, -1, -1], [1, -1, -1, 1]]) / 2

def predict(K, eff, al, be, eps, ideal):
    """|++>, K gates of the model, H H: the ideal state's probability, then a depolarising decay."""
    phase = -K / 2 * (eff * ZZ + al * ZA + be * ZB)
    psi = H2 @ (np.exp(1j * phase) / 2)
    idx = 3 if ideal == "11" else 0
    f = (1 - 16 / 15 * max(eps, 0)) ** K
    return f * abs(psi[idx]) ** 2 + (1 - f) / 4

def spearman_boot(rows, a, b, c, n=4000):
    pairs = sorted({r["pair"] for r in rows}); by = {p: [r for r in rows if r["pair"] == p] for p in pairs}; diffs = []
    for _ in range(n):
        sample = [r for p in rng.choice(pairs, len(pairs)) for r in by[p]]
        y = [r[c] for r in sample]
        ra = stats.spearmanr([r[a] for r in sample], y).statistic; rb = stats.spearmanr([r[b] for r in sample], y).statistic
        if np.isfinite(ra) and np.isfinite(rb): diffs.append(ra - rb)
    return np.percentile(diffs, [2.5, 97.5]).tolist()

rows = []
for name, sweep in (("E4", "E2"), ("E6", "E7")):
    cases, cal = ROUND[name]["cases"], ROUND[name]["cal"]
    for c in cases:
        q = cal[c["pair"]]; th = c["j"] * np.pi / 24; i = q["th"].index(min(q["th"], key=lambda x: abs(x - th))); K = int(round(24 * c["mult"] / c["j"]))
        sw = S[sweep]["pairs"][c["pair"]]; eps = float(np.interp(th, sw["theta"], sw["eps"])); ideal = "11" if c["mult"] == 1 else "00"
        m = predict(K, q["eff"][i], q["alpha"][i], q["beta"][i], eps, ideal)
        f = (1 - 16 / 15 * sw["reported"]) ** K
        rows.append(dict(exp=name, pair=c["pair"], j=c["j"], K=K, measured=c["raw"], model=m, ibm=f + (1 - f) / 4, local=c["local"]))
y = [r["measured"] for r in rows]
h3 = dict(n=len(rows), rho_model=float(stats.spearmanr([r["model"] for r in rows], y).statistic), rho_ibm=float(stats.spearmanr([r["ibm"] for r in rows], y).statistic),
          r_model=float(np.corrcoef([r["model"] for r in rows], y)[0, 1]), mae_model=float(np.mean(np.abs(np.array([r["model"] for r in rows]) - y))), mae_ibm=float(np.mean(np.abs(np.array([r["ibm"] for r in rows]) - y))))
h3["diff"] = h3["rho_model"] - h3["rho_ibm"]; h3["diff_ci"] = spearman_boot(rows, "model", "ibm", "measured")
nb = [r for r in rows if r["pair"] not in ("(10, 11)", "(0, 1)")]; yn = [r["measured"] for r in nb]
h3["without_bad"] = dict(n=len(nb), rho_model=float(stats.spearmanr([r["model"] for r in nb], yn).statistic), rho_ibm=float(stats.spearmanr([r["ibm"] for r in nb], yn).statistic))
h3["without_bad"]["diff_ci"] = spearman_boot(nb, "model", "ibm", "measured")
R["h3_preview"] = h3
fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.7), sharey=True)
for ax, key, title, col in ((axes[0], "ibm", f"IBM-reported error, ρ = {h3['rho_ibm']:.2f}", GREY), (axes[1], "model", f"Measured gate model, ρ = {h3['rho_model']:.2f}", BLUE)):
    ax.plot([r[key] for r in rows], y, "o", ms=3, color=col, alpha=.65, mec="none"); ax.plot([0, 1], [0, 1], color=INK, lw=.6); ax.set_xlabel("predicted P(success)"); ax.set_title(title, fontsize=8.5, loc="left"); ax.set_xlim(0, 1.02)
axes[0].set_ylabel("measured P(success)"); fig.tight_layout(); fig.savefig(FIG / "fig5_h3.png"); plt.close(fig)

# ---------- Part 3: projections (model outputs) ----------
# H1: resample the measured raw p-values into a confirmatory sweep's size, with Holm across all pairs.
pm = [p["p"] for k in ("E2", "E8") for p in S[k]["pairs"].values()]; pk = [p["p"] for p in S["E7"]["pairs"].values()]
frs = {}
for m in (30, 60):
    f = []
    for _ in range(20000):
        sample = np.concatenate([rng.choice(pm, m // 2), rng.choice(pk, m // 2)])
        f.append(float((holm(sample) < .01).mean()))
    f = np.array(f); frs[m] = dict(median=float(np.median(f)), lo=float(np.percentile(f, 2.5)), hi=float(np.percentile(f, 97.5)), p_ge_50=float((f >= .5).mean()))
R["h1_projection"] = frs

# Device parameters for a synthetic line of qubits: each edge one measured pair, with the same-day calibration.
PARAMS = []
for name, sweep in (("E4", "E2"), ("E6", "E7")):
    for pr, c in ROUND[name]["cal"].items():
        sw = S[sweep]["pairs"][pr]
        PARAMS.append(dict(pair=pr, device=ROUND[name]["backend"], th=np.array(c["th"]), delta=np.array(c["eff"]) - np.array(c["th"]), alpha=np.array(c["alpha"]), beta=np.array(c["beta"]),
                           eps_th=np.array(sw["theta"]), eps=np.maximum(np.array(sw["eps"]), 1e-5), reported=sw["reported"]))
BAD = {"(10, 11)", "(0, 1)"}

def apply_diag(psi, n, a, b, theta):
    """exp(-i theta/2 Z_a Z_b) on a statevector."""
    idx = np.arange(2 ** n); za = 1 - 2 * ((idx >> a) & 1); zb = 1 - 2 * ((idx >> b) & 1)
    return psi * np.exp(-0.5j * theta * za * zb)

def apply_rz(psi, n, q, phi):
    z = 1 - 2 * ((np.arange(2 ** n) >> q) & 1); return psi * np.exp(-0.5j * phi * z)

def apply_rx(psi, n, q, phi):
    c, s = np.cos(phi / 2), -1j * np.sin(phi / 2); idx = np.arange(2 ** n); flip = idx ^ (1 << q)
    return c * psi + s * psi[flip]

def make_circuit(family, n, layers, r):
    """A list of layers: ('zz', a, b, theta) and ('x', q, phi). Angles lie in (0, pi/2]."""
    ops = []
    h = r.uniform(.2, 1.2, n)
    for l in range(layers):
        for parity in (0, 1):
            for a in range(parity, n - 1, 2):
                if family == "lr_qaoa": th = (l + 1) / layers * r.choice([.5, 1.0])
                elif family == "ising": th = .35
                else: th = r.uniform(np.pi / 24, np.pi / 2)
                ops.append(("zz", a, th))
        for q in range(n):
            phi = (1 - (l + 1) / layers) * 1.2 if family == "lr_qaoa" else (.5 if family == "ising" else r.uniform(0, np.pi))
            ops.append(("x", q, phi))
    return ops

def run(ops, n, edges, policy, cz_err, resid):
    """Fidelity of the coherent state with the ideal one, times each gate's depolarising survival."""
    ideal = np.ones(2 ** n, complex) / np.sqrt(2 ** n); psi = ideal.copy(); surv = 1.0; chosen = fracs = 0
    for op in ops:
        if op[0] == "x":
            ideal = apply_rx(ideal, n, op[1], op[2]); psi = apply_rx(psi, n, op[1], op[2]); continue
        _, a, th = op; e = edges[a]
        ideal = apply_diag(ideal, n, a, a + 1, th)
        de, al, be = [float(np.interp(th, e["th"], e[k])) for k in ("delta", "alpha", "beta")]
        eps = float(np.interp(th, e["eps_th"], e["eps"]))
        use_cz = False
        if policy == "theta":
            # The compiler's own estimate of each option, from the measured model: uncorrected over-rotation costs (delta/2)^2.
            frac_cost = 16 / 15 * eps + (de / 2) ** 2
            use_cz = frac_cost > 2 * e["reported"]
        if use_cz:
            psi = apply_diag(psi, n, a, a + 1, th); surv *= (1 - cz_err(e)) ** 2; chosen += 1; continue
        fracs += 1
        psi = apply_diag(psi, n, a, a + 1, th + de)
        if policy == "raw":
            psi = apply_rz(psi, n, a, al); psi = apply_rz(psi, n, a + 1, be)
        else:
            psi = apply_rz(psi, n, a, r_noise(resid)); psi = apply_rz(psi, n, a + 1, r_noise(resid))
        surv *= 1 - 16 / 15 * eps
    return abs(np.vdot(ideal, psi)) ** 2 * surv, chosen / max(chosen + fracs, 1)

sim_rng = np.random.default_rng(777)
r_noise = lambda s: float(sim_rng.normal(0, s))

def project(N=420, n=8, avoid_bad=False, resid=0.01, cz_factor=1.0):
    out = {}
    pool = [p for p in PARAMS if not (avoid_bad and p["pair"] in BAD)]
    for family in ("lr_qaoa", "ising", "random"):
        rows = []
        for inst in range(N):
            r = np.random.default_rng(10_000 + inst + hash(family) % 1000 * 0)
            layers = int(r.choice([2, 4, 6]))
            device = r.choice(["ibm_marrakesh", "ibm_kingston"]); local_pool = [p for p in pool if p["device"] == device]
            edges = [local_pool[r.integers(len(local_pool))] for _ in range(n - 1)]
            ops = make_circuit(family, n, layers, r)
            cz = lambda e: e["reported"] * cz_factor
            raw, _ = run(ops, n, edges, "raw", cz, resid); loc, _ = run(ops, n, edges, "local", cz, resid); the, share = run(ops, n, edges, "theta", cz, resid)
            rows.append((raw, loc, the, share, any(e["pair"] in BAD for e in edges), layers))
        a = np.array(rows, float); 
        gain = (a[:, 2] - a[:, 0]) / np.maximum(a[:, 0], 1e-3); gl = (a[:, 1] - a[:, 0]) / np.maximum(a[:, 0], 1e-3)
        bs = [np.median(rng.choice(gain, len(gain))) for _ in range(2000)]
        clean = a[:, 4] == 0
        out[family] = dict(median_raw=float(np.median(a[:, 0])), median_local=float(np.median(a[:, 1])), median_theta=float(np.median(a[:, 2])), median_rel_gain=float(np.median(gain)), ci=[float(x) for x in np.percentile(bs, [2.5, 97.5])],
                           median_rel_gain_local=float(np.median(gl)), share_cz=float(a[:, 3].mean()), frac_with_bad_edge=float(a[:, 4].mean()), gain_no_bad=float(np.median(gain[clean])) if clean.any() else None, gain_with_bad=float(np.median(gain[~clean])) if (~clean).any() else None,
                           by_layers={int(l): float(np.median(gain[a[:, 5] == l])) for l in (2, 4, 6)}, worse=float((gain < 0).mean()))
    return out

R["h2_projection"] = dict(base=project(), resid_002=project(N=240, resid=.02), avoid_bad=project(N=240, avoid_bad=True), cz_worse=project(N=240, cz_factor=2.0))

fig, ax = plt.subplots(figsize=(4.8, 2.4)); fams = ["lr_qaoa", "ising", "random"]; names = ["LR-QAOA", "Trotter Ising", "Random RZZ"]; w = .25
for o, (key, col, lab) in enumerate((("base", BLUE, "measured pair mix"), ("cz_worse", ORANGE, "CZ twice as noisy"), ("avoid_bad", GREY, "bad pairs avoided by layout"))):
    v = [R["h2_projection"][key][f]["median_rel_gain"] * 100 for f in fams]
    ax.bar(np.arange(3) + (o - 1) * w, v, w, color=col, label=lab)
ax.axhline(10, color=RED, ls="--", lw=1); ax.text(2.45, 12, "H2: 10%", color=RED, fontsize=7.5, ha="right")
ax.set_xticks(range(3)); ax.set_xticklabels(names); ax.set_ylabel("median gain in success (%)\nmodel projection"); ax.legend(fontsize=7, loc="upper left")
fig.tight_layout(); fig.savefig(FIG / "fig6_h2.png"); plt.close(fig)

# H4: QPU seconds for the same CI width: six depths with equal shots vs two depths chosen from the Fisher information.
a_c, b_s = None, None
b_s = (82 / 300 - 9 / 48) / 500; a_c = 9 / 48 - 500 * b_s
cost = lambda circuits, shots: circuits * a_c + circuits * shots * b_s
depths_u = np.array(S["E2"]["depths"], float)
def ci_width(eps, depths, shots, A=.97, n=2500):
    p = 1 - 16 / 15 * eps; s = A * p ** (2 * depths)
    sims = rng.binomial(shots, s, size=(n, len(depths))) / shots
    x = 2 * depths; y = np.log(np.clip(sims, 1e-3, 1)); xb = x.mean(); slope = ((x - xb) * (y - y.mean(1, keepdims=True))).sum(1) / ((x - xb) ** 2).sum()
    e = 15 / 16 * (1 - np.exp(slope)); return float(np.percentile(e, 97.5) - np.percentile(e, 2.5))
EPS_GRID = [3e-4, 1e-3, 3e-3, 8e-3]; h4 = {}
base = 1000
for d2 in (16, 32, 64, 96):
    dd = np.array([1.0, d2]); rec = []
    for e in EPS_GRID:
        target = ci_width(e, depths_u, base); lo, hi = 100, 20000
        for _ in range(12):
            mid = int(np.sqrt(lo * hi))
            if ci_width(e, dd, mid) > target: lo = mid
            else: hi = mid
        rec.append(hi)
    h4[d2] = rec
worst = {d: max(v) for d, v in h4.items()}; best = min(worst, key=worst.get); shots2 = worst[best]
T_u, T_o = cost(len(depths_u), base), cost(2, shots2)
R["h4_projection"] = dict(a_circuit_s=a_c, b_shot_s=b_s, uniform_depths=depths_u.tolist(), uniform_shots=base, needed=h4, best_d2=best, shots_two_depth=shots2, T_uniform=T_u, T_design=T_o, ratio=T_o / T_u,
                          shot_ratio=2 * shots2 / (len(depths_u) * base))

# Budget of the full experiment, from the measured cost per circuit.
sw, cal_c = 300, 280; test_cases = 40 * 4
per = cost(1, 1000); per2000 = cost(1, 2000)
items = dict(sweeps=2 * 3 * sw * per, calibration=2 * 3 * cal_c * per, evaluation=2 * test_cases * per2000)
R["budget"] = dict(items=items, total_s=sum(items.values()), total_min=sum(items.values()) / 60, sec_per_1000=per)
json.dump(R, open(HERE / "paper_results.json", "w"), indent=1, default=float)
print(json.dumps(R, indent=0, default=float)[:12000])
