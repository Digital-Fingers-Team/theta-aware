"""Figures and headline numbers for the compiler, from compiler_replay.json and compiler_benchmark.json.
Writes figures/fig7_replay.png, figures/fig8_benchmark.png and compiler_summary.json. No QPU."""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

H = Path(__file__).parent
FIG = H / "figures"; FIG.mkdir(exist_ok=True)
RP = json.loads((H / "compiler_replay.json").read_text())
BM = json.loads((H / "compiler_benchmark.json").read_text())
GREY, BLUE, GREEN, ORANGE, RED, INK = "#8a8984", "#2a78d6", "#2f9e6e", "#d9822b", "#c8413b", "#0b0b0b"
plt.rcParams.update({"font.size": 8.5, "axes.spines.top": False, "axes.spines.right": False, "font.family": "DejaVu Sans",
                     "axes.edgecolor": "#55544f", "axes.linewidth": 0.7, "legend.frameon": False, "figure.dpi": 200})

# ---------- Figure 7: replay on past hardware jobs (measured outcomes) ----------
fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.5), gridspec_kw=dict(width_ratios=[1.25, 1]))
ax = axes[0]; rows = RP["E10"]["rows"]
lab = [f"{r['j']}π/24, K={r['K']}" for r in rows]; x = np.arange(len(rows)); w = .38
ax.bar(x - w / 2, [r["measured"]["raw"] for r in rows], w, color=GREY, label="Qiskit (fractional gate)")
ax.bar(x + w / 2, [r["chosen"] for r in rows], w, color=BLUE, label="θ-Aware's choice (2-CZ)")
ax.set_xticks(x); ax.set_xticklabels(lab, fontsize=7.3); ax.set_ylim(0, 1); ax.set_ylabel("measured P(success)")
ax.set_title("E10, pair (10, 11), held out", loc="left", fontsize=8.5, pad=4); ax.legend(fontsize=7, loc="lower center", bbox_to_anchor=(.5, 1.1), ncol=2)
ax = axes[1]
sets = [("E4\nmarrakesh\n(fit κ)", RP["E4"]["summary"]), ("E6\nkingston\n(held out)", RP["E6"]["summary"]), ("E10\n(held out)", RP["E10"]["summary"])]
pols = [("qiskit_fractional(raw)", GREY, "Qiskit"), ("theta_aware", BLUE, "θ-Aware"), ("oracle", GREEN, "best possible")]
for o, (k, col, name) in enumerate(pols):
    ax.bar(np.arange(3) + (o - 1) * .26, [s[k] for _, s in sets], .26, color=col, label=name)
ax.set_xticks(range(3)); ax.set_xticklabels([n for n, _ in sets], fontsize=7.3); ax.set_ylim(0, 1); ax.set_ylabel("mean measured P(success)")
ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(.5, 1.27), ncol=3)
fig.tight_layout(); fig.savefig(FIG / "fig7_replay.png"); plt.close(fig)

# ---------- Figure 8: simulation benchmark (projection) ----------
B = BM["by"]
fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.5))
ax = axes[0]
pol = [("frac", GREY, "Qiskit, fractional"), ("cz", ORANGE, "Qiskit, CZ only"), ("theta", BLUE, "θ-Aware"), ("theta+layout", GREEN, "θ-Aware + layout")]
fams = [("lr_qaoa", "LR-QAOA"), ("ising", "Trotter Ising"), ("random", "Random RZZ")]
for o, (k, col, name) in enumerate(pol):
    ax.bar(np.arange(3) + (o - 1.5) * .2, [B[f]["err_" + k] for f, _ in fams], .2, color=col, label=name)
ax.set_yscale("log"); ax.set_xticks(range(3)); ax.set_xticklabels([n for _, n in fams]); ax.set_ylabel("state infidelity (1 − F)\nlog scale, lower is better")
ax.legend(fontsize=6.8, ncol=2, loc="upper center", bbox_to_anchor=(.5, 1.3))
ax = axes[1]
keys = [k for k in B if k.startswith("drift_x") or k == "all"]
order = ["all"] + sorted([k for k in keys if k != "all"], key=lambda s: float(s.split("x")[1].split()[0]))
xs = [1] + [float(k.split("x")[1].split()[0]) for k in order[1:]]
for k, col, name in pol:
    ax.plot(xs, [B[o]["err_" + k] for o in order], "o-", color=col, label=name, lw=1.2, ms=3.5)
ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xticks(xs); ax.set_xticklabels([f"{x:g}×" for x in xs])
ax.set_xlabel("drift relative to the measured one-hour drift"); ax.set_ylabel("state infidelity (1 − F)")
fig.tight_layout(); fig.savefig(FIG / "fig8_benchmark.png"); plt.close(fig)

# ---------- Headline numbers (every one traceable to the two JSON files) ----------
e10 = RP["E10"]["summary"]; e6 = RP["E6"]["summary"]; e4 = RP["E4"]["summary"]; a = B["all"]
S = dict(
    kappa=RP["kappa"],
    e10=dict(qiskit=e10["qiskit_fractional(raw)"], theta=e10["theta_aware"], oracle=e10["oracle"], n=e10["n"],
             error_ratio=e10["errors_raw"] / e10["errors_theta"], best=e10["picked_best_or_within_noise"]),
    e6=dict(qiskit=e6["qiskit_fractional(raw)"], theta=e6["theta_aware"], oracle=e6["oracle"], n=e6["n"], best=e6["picked_best_or_within_noise"],
            better=e6["improved_vs_raw"], worse=e6["worse_vs_raw"]),
    e4=dict(qiskit=e4["qiskit_fractional(raw)"], theta=e4["theta_aware"], oracle=e4["oracle"], n=e4["n"], best=e4["picked_best_or_within_noise"],
            err_cut=1 - e4["errors_theta"] / e4["errors_raw"], better=e4["improved_vs_raw"], worse=e4["worse_vs_raw"]),
    sim=dict(n=a["n"], sigma=BM["sigma"], err=dict((k, a["err_" + k]) for k, _, _ in pol), err_cz_layout=a["err_cz+ibm_layout"], err_frac_layout=a["err_frac+ibm_layout"],
             g2=dict((k, a["g2_" + k]) for k, _, _ in pol), cut_vs_frac=a["err_reduction_vs_frac"], cut_vs_cz=a["err_reduction_vs_cz"],
             g2_saving_vs_cz=a["g2_saving_vs_cz"], cut_layout_vs_cz=a["err_reduction_layout_vs_ibm_cz"], cut_layout_vs_frac=a["err_reduction_layout_vs_ibm_frac"],
             worse_than_frac=a["theta_worse_than_frac"], no_bad=B["no_bad_edge"], with_bad=B["with_bad_edge"],
             drift={k: dict(err_theta=B[k]["err_theta"], err_cz=B[k]["err_cz"], err_frac=B[k]["err_frac"], err_layout=B[k]["err_theta+layout"]) for k in order[1:]}),
    compile_ms=BM["compile_seconds_median"] * 1000,
    e10_rows=[dict(case=f"{r['j']}π/24, K={r['K']}", raw=r["measured"]["raw"], local=r["measured"]["local"], cz=r["measured"]["cz"], choice=r["choice"]) for r in RP["E10"]["rows"]],
)
(H / "compiler_summary.json").write_text(json.dumps(S, indent=1))
print(json.dumps(S, indent=1)[:3000])
