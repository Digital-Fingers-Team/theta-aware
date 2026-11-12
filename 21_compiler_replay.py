"""Replay test: run the compiler on the exact circuits of past hardware jobs, using only calibrations that
existed before each job, and look up how the option it chose actually did on the QPU. No QPU, no key.

Step 1 (fit, E4 only): KAPPA, the share of a measured coherent error that survives correction,
        by least absolute error between the model's prediction and E4's measured 'local' and 'local+delta'.
Step 2 (held-out tests):
  E6  ibm_kingston, other device, 98 cases, options measured: raw / local / local+delta
  E10 ibm_marrakesh (10,11), 4 cases, options measured: raw / local / cz (2 h after the calibration)
  E4  reported too, but marked in-sample (its outcomes were used to fit KAPPA)
Policies compared on the same cases: Qiskit with fractional gates (always raw), Qiskit without (always cz,
where measured), always local, always local+delta, theta-aware, and the oracle (best measured option).
Writes compiler_params.json and compiler_replay.json.
"""
import json
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit

from thetaaware import calibration as C
from thetaaware import compiler as T

HERE = Path(__file__).parent
bit = lambda key, i: key[::-1][i]
VAR = {"frac": "raw", "frac+rz": "local", "frac+rz+pre": "local+delta", "cz": "cz"}

ZZ = np.array([1, -1, -1, 1.0]); ZA, ZB = np.array([1, 1, -1, -1.0]), np.array([1, -1, 1, -1.0])
H2 = np.array([[1, 1, 1, 1], [1, -1, 1, -1], [1, 1, -1, -1], [1, -1, -1, 1]]) / 2


def predict(K, eff, al, be, eps, ideal):
    """Same formula as 17_paper_analysis.predict: |++>, K model gates, H H."""
    psi = H2 @ (np.exp(1j * (-K / 2) * (eff * ZZ + al * ZA + be * ZB)) / 2)
    f = (1 - 16 / 15 * max(eps, 0)) ** K
    return f * abs(psi[3 if ideal == "11" else 0]) ** 2 + (1 - f) / 4


def round_cases(fname):
    d = json.loads((HERE / fname).read_text()); meta, counts = d["test_meta"], d["test_counts"]
    out = []
    for i, pr in enumerate(d["pairs"]):
        for j in sorted({m["j"] for m in meta}):
            for mult in (1, 2):
                ideal = "11" if mult == 1 else "00"
                row = dict(pair=tuple(pr), j=j, mult=mult, K=int(round(24 * mult / j)), ideal=ideal)
                for v in ("raw", "local", "local+delta"):
                    k = next(k for k, m in enumerate(meta) if m["j"] == j and m["mult"] == mult and m["variant"] == v)
                    c = counts[k]; t = sum(c.values())
                    row[v] = sum(n for key, n in c.items() if bit(key, 2 * i) + bit(key, 2 * i + 1) == ideal) / t
                out.append(row)
    return out


def e10_cases():
    d = json.loads((HERE / "czbase_db7u6r0r1c5c738lalhg.json").read_text()); tab = {}
    for m, c in zip(d["meta"], d["counts"]):
        ideal = "11" if m["K"] * m["j"] == 24 else "00"
        row = tab.setdefault((m["j"], m["K"]), dict(pair=(10, 11), j=m["j"], K=m["K"], ideal=ideal))
        row[m["variant"]] = c.get(ideal, 0) / sum(c.values())
    return list(tab.values())


def compile_case(case, cal, kappa, allowed):
    """The compiler on the real test circuit (on the physical pair), as it would run before the job."""
    a, b = case["pair"]; th = case["j"] * np.pi / 24
    qc = QuantumCircuit(max(a, b) + 1)
    qc.h([a, b])
    for _ in range(case["K"]):
        qc.rzz(th, a, b)
    qc.h([a, b])
    _, rep = T.apply(qc, cal, "theta", kappa, allowed)
    opts = {c.option for c in rep.choices}
    assert len(opts) == 1, opts
    return opts.pop()


# ---------- Step 1: fit KAPPA on E4 only ----------
E4 = round_cases("round2_db7t6ier6oqs738898ig.json")
cal4 = C.marrakesh_after_e4()


def kappa_loss(k):
    err = []
    for c in E4:
        p = cal4.get_pair(*c["pair"]); th = c["j"] * np.pi / 24; q = p.at(th)
        err.append(abs(predict(c["K"], th + q["delta"], k * q["alpha"], k * q["beta"], q["eps"], c["ideal"]) - c["local"]))
        x = p.pre_distort(th)
        if x is not None:
            r = p.at(x)
            err.append(abs(predict(c["K"], th + k * q["delta"], k * r["alpha"], k * r["beta"], r["eps"], c["ideal"]) - c["local+delta"]))
    return float(np.mean(err))


grid = np.round(np.arange(0, 1.0001, 0.01), 2)
losses = [kappa_loss(k) for k in grid]
KAPPA = float(grid[int(np.argmin(losses))])
(HERE / "compiler_params.json").write_text(json.dumps(dict(kappa=KAPPA, fitted_on="E4 round2_db7t6ier6oqs738898ig.json (local, local+delta)",
                                                           mae=min(losses), mae_kappa0=losses[0], mae_kappa1=losses[-1]), indent=1))
print(f"KAPPA fitted on E4 = {KAPPA}  (MAE {min(losses):.4f}; kappa=0 {losses[0]:.4f}; kappa=1 {losses[-1]:.4f})")


# ---------- Step 2: replay ----------
def evaluate(name, cases, cal, allowed, in_sample):
    rows = []
    for c in cases:
        opt = compile_case(c, cal, KAPPA, allowed)
        measured = {o: c[VAR[o]] for o in allowed if VAR[o] in c}
        best = max(measured.values())
        rows.append(dict(pair=str(c["pair"]), j=c["j"], K=c["K"], choice=opt, chosen=measured[opt], best=best,
                         measured={VAR[o]: v for o, v in measured.items()}))
    pol = {"qiskit_fractional(raw)": "frac", "always_local": "frac+rz", "always_local+delta": "frac+rz+pre", "qiskit_no_fractional(cz)": "cz"}
    summary = dict(n=len(rows), in_sample=in_sample, allowed=[VAR[o] for o in allowed])
    for label, o in pol.items():
        if o in allowed:
            summary[label] = float(np.mean([r["measured"][VAR[o]] for r in rows]))
    summary["theta_aware"] = float(np.mean([r["chosen"] for r in rows]))
    summary["oracle"] = float(np.mean([r["best"] for r in rows]))
    # A 2000-shot estimate has SE <= 0.011; "within noise" = less than 2 SE (0.022) below the best measured option.
    summary["picked_best_or_within_noise"] = int(sum(r["best"] - r["chosen"] <= 0.022 for r in rows))
    raw = np.array([r["measured"]["raw"] for r in rows]); ch = np.array([r["chosen"] for r in rows])
    summary["improved_vs_raw"] = int((ch > raw + 0.022).sum()); summary["worse_vs_raw"] = int((ch < raw - 0.022).sum())
    summary["errors_raw"] = float(np.mean(1 - raw)); summary["errors_theta"] = float(np.mean(1 - ch))
    summary["choices"] = {VAR[o]: sum(r["choice"] == o for r in rows) for o in allowed}
    summary["two_qubit_gates_per_rzz"] = float(np.mean([T.TWO_Q[r["choice"]] for r in rows]))
    print(f"\n== {name} ({'in-sample' if in_sample else 'HELD-OUT'}) n={len(rows)} choices={summary['choices']}")
    for k, v in summary.items():
        if isinstance(v, float):
            print(f"   {k:28s} {v:.3f}")
    print(f"   picked best (or within noise): {summary['picked_best_or_within_noise']}/{len(rows)}; better than raw: {summary['improved_vs_raw']}, worse: {summary['worse_vs_raw']}")
    return dict(summary=summary, rows=rows)


FR = ("frac", "frac+rz", "frac+rz+pre")
out = dict(kappa=KAPPA,
           E6=evaluate("E6 ibm_kingston", round_cases("round2k_db7teq6il99s73forh20.json"), C.kingston_e6(), FR, False),
           E10=evaluate("E10 ibm_marrakesh (10,11)", e10_cases(), C.marrakesh_after_e8(), ("frac", "frac+rz", "cz"), False),
           E4=evaluate("E4 ibm_marrakesh", E4, cal4, FR, True))
for r in out["E10"]["rows"]:
    print("   E10", r)
(HERE / "compiler_replay.json").write_text(json.dumps(out, indent=1))
print("\nSaved compiler_params.json, compiler_replay.json")
