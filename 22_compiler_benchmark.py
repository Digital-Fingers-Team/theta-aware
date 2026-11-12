"""Simulation benchmark of the compiler on algorithm circuits. MODEL OUTPUTS, NOT HARDWARE DATA.

Device: a line of n qubits; each edge carries the measured parameters of one real pair (same device, same day).
The compiler knows that calibration; the simulated device runs a DRIFTED copy of it, with drift of the size seen
between the two marrakesh sweeps E2 (18:37) and E8 (19:23), so the corrections are never perfect.
Single-qubit gates and readout are ideal: differences come from the two-qubit gates only.

Policies, same circuit and same edges:
  qiskit_frac   Qiskit with fractional gates on: every RZZ is one fractional gate (trusts IBM's single error number)
  qiskit_cz     Qiskit with fractional gates off: every RZZ is two CZ
  theta         theta-aware, gate choice only (same layout as the others)
  theta+layout  theta-aware also picks which measured pairs to use (score_layout over 24 candidate assignments);
                its competitor qiskit_frac+layout picks by IBM's reported error, as Qiskit's layout does
Metric: state fidelity <psi_ideal|rho|psi_ideal> before measurement (strict: every error counts); also two-qubit gate count.
Run at the measured drift and at 6x and 18x larger drift (our data cover about one hour; day-scale drift is not measured yet).
"""
import json, time
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit.transpiler import CouplingMap

from thetaaware import calibration as C
from thetaaware import compiler as T
from thetaaware import device as D

HERE = Path(__file__).parent
N, INST = 6, 40
rng = np.random.default_rng(20261112)

# Drift size: median |delta(E8) - delta(E2)| over the shared grid, pairs with a usable delta ((93, 94) excluded as in the paper).
e2 = json.loads((HERE / "calib_db7sns0r1c5c738l7vm0.json").read_text())["pairs"]
e8 = json.loads((HERE / "calib_marrakesh2.json").read_text())["pairs"]
SIGMA = float(np.median([abs(a - b) for k in e2 if k != "(93, 94)" for a, b in zip(e2[k]["delta"], e8[k]["delta"])]))
print(f"drift sigma from E2 -> E8 = {SIGMA:.4f} rad")

DEVICES = {"ibm_marrakesh": C.marrakesh_after_e4(), "ibm_kingston": C.kingston_e6()}
BAD = {"(10, 11)", "(0, 1)"}  # the paper's bad pairs, used only to label results, never by the compiler


def line_cal(pairs):
    return C.Calibration({(i, i + 1): C.PairCal((i, i + 1), p.th, p.delta, p.alpha, p.beta, p.eps_th, p.eps, p.reported, p.source)
                          for i, p in enumerate(pairs)})


def circuit(family, n, layers, r):
    qc = QuantumCircuit(n)
    qc.h(range(n))
    for l in range(layers):
        for parity in (0, 1):
            for a in range(parity, n - 1, 2):
                if family == "lr_qaoa":
                    th = (l + 1) / layers * float(r.choice([0.5, 1.0]))
                elif family == "ising":
                    th = 0.35
                else:
                    th = float(r.uniform(np.pi / 24, np.pi / 2))
                qc.rzz(th, a, a + 1)
        for q in range(n):
            phi = (1 - (l + 1) / layers) * 1.2 if family == "lr_qaoa" else (0.5 if family == "ising" else float(r.uniform(0, np.pi)))
            qc.rx(phi, q)
    return qc  # no measurement: the metric is the state before measurement


CM = CouplingMap([(i, i + 1) for i in range(N - 1)] + [(i + 1, i) for i in range(N - 1)])
LAYOUT = list(range(N))


def run(qc, cal, truth, policy):
    out, rep = T.compile_circuit(qc, CM, LAYOUT, cal, policy=policy)
    return D.state_fidelity(out, qc, truth), out.count_ops().get("rzz", 0) + out.count_ops().get("cz", 0), rep


def bench(SIGMA, INST):
  rows = []; compile_times = []
  for family in ("lr_qaoa", "ising", "random"):
    for inst in range(INST):
        r = np.random.default_rng(1000 * hash(family) % 7919 + inst)
        dev = ["ibm_marrakesh", "ibm_kingston"][inst % 2]
        pool = list(DEVICES[dev].values())
        layers = int(r.choice([2, 3, 4]))
        qc = circuit(family, N, layers, r)
        # Candidate assignments of measured pairs to the N-1 edges (repeats allowed: a line longer than the pool).
        cands = [[pool[k] for k in r.integers(len(pool), size=N - 1)] for _ in range(24)]
        drift_seed = int(r.integers(1 << 30))

        def truth_of(pairs):
            return D.drifted(line_cal(pairs), SIGMA, np.random.default_rng(drift_seed))

        base = cands[0]; cal = line_cal(base); truth = truth_of(base)
        res = {}
        for pol in ("frac", "cz", "theta"):
            ts = time.time(); res[pol] = run(qc, cal, truth, pol); compile_times.append(time.time() - ts)
        # Layout choice: theta-aware by predicted error, Qiskit-like by IBM's reported errors.
        laid = T.transpile(qc, basis_gates=T.BASIS_FRAC, coupling_map=CM, initial_layout=LAYOUT, optimization_level=1)
        edges = [((laid.find_bit(i.qubits[0]).index, laid.find_bit(i.qubits[1]).index), float(i.operation.params[0])) for i in laid.data if i.operation.name == "rzz"]
        best_theta = min(cands, key=lambda ps: T.score_layout(edges, line_cal(ps)))
        best_ibm = min(cands, key=lambda ps: sum(p.reported for p in ps))
        res["theta+layout"] = run(qc, line_cal(best_theta), truth_of(best_theta), "theta")
        res["frac+ibm_layout"] = run(qc, line_cal(best_ibm), truth_of(best_ibm), "frac")
        res["cz+ibm_layout"] = run(qc, line_cal(best_ibm), truth_of(best_ibm), "cz")
        rows.append(dict(family=family, device=dev, layers=layers, bad_edge=any(str(p.pair) in BAD for p in base),
                         **{f"F_{k}": v[0] for k, v in res.items()}, **{f"g2_{k}": v[1] for k, v in res.items()},
                         theta_choices=dict(res["theta"][2].counts())))
  return rows, compile_times


t0 = time.time()
ALL = {}
for label, sig, inst in (("measured_drift", SIGMA, INST), ("drift_x6", 6 * SIGMA, INST // 2), ("drift_x18", 18 * SIGMA, INST // 2)):
    ALL[label] = (sig,) + bench(sig, inst)
rows, compile_times = ALL["measured_drift"][1], ALL["measured_drift"][2]

a = lambda key, sel=None: np.array([r[key] for r in rows if sel is None or sel(r)])
out = dict(note="simulation with measured parameters plus measured-size drift; not hardware data", sigma=SIGMA, n_circuits=len(rows), qubits=N, by={})


def summarise(label, sel=None):
    s = {}
    for k in ("frac", "cz", "theta", "theta+layout", "frac+ibm_layout", "cz+ibm_layout"):
        s[f"F_{k}"] = float(np.mean(a(f"F_{k}", sel)))
        s[f"err_{k}"] = float(np.mean(1 - a(f"F_{k}", sel)))
        s[f"g2_{k}"] = float(np.mean(a(f"g2_{k}", sel)))
    s["n"] = int(len(a("F_theta", sel)))
    s["theta_beats_frac"] = float(np.mean(a("F_theta", sel) > a("F_frac", sel) + 1e-9))
    s["theta_worse_than_frac"] = float(np.mean(a("F_theta", sel) < a("F_frac", sel) - 1e-3))
    s["theta_beats_cz"] = float(np.mean(a("F_theta", sel) > a("F_cz", sel) + 1e-9))
    s["err_reduction_vs_frac"] = 1 - s["err_theta"] / s["err_frac"]
    s["err_reduction_vs_cz"] = 1 - s["err_theta"] / s["err_cz"]
    s["err_reduction_layout_vs_ibm_frac"] = 1 - s["err_theta+layout"] / s["err_frac+ibm_layout"]
    s["err_reduction_layout_vs_ibm_cz"] = 1 - s["err_theta+layout"] / s["err_cz+ibm_layout"]
    s["g2_saving_vs_cz"] = 1 - s["g2_theta"] / s["g2_cz"]
    out["by"][label] = s
    print(f"\n== {label}  n={s['n']}")
    for k in ("frac", "cz", "theta", "frac+ibm_layout", "cz+ibm_layout", "theta+layout"):
        print(f"   {k:16s} fidelity {s['F_' + k]:.4f}  errors {s['err_' + k]:.4f}  2q gates {s['g2_' + k]:.1f}")
    print(f"   theta vs frac: errors -{100 * s['err_reduction_vs_frac']:.1f}% (better in {100 * s['theta_beats_frac']:.0f}%, worse in {100 * s['theta_worse_than_frac']:.0f}%)")
    print(f"   theta vs cz:   errors -{100 * s['err_reduction_vs_cz']:.1f}% with {100 * s['g2_saving_vs_cz']:.0f}% fewer 2q gates")
    print(f"   with layout:   errors -{100 * s['err_reduction_layout_vs_ibm_frac']:.1f}% vs Qiskit-frac, -{100 * s['err_reduction_layout_vs_ibm_cz']:.1f}% vs Qiskit-cz")


summarise("all")
for fam in ("lr_qaoa", "ising", "random"):
    summarise(fam, lambda r, f=fam: r["family"] == f)
summarise("no_bad_edge", lambda r: not r["bad_edge"])
summarise("with_bad_edge", lambda r: r["bad_edge"])
for label in ("drift_x6", "drift_x18"):
    rows = ALL[label][1]
    summarise(f"{label} (sigma={ALL[label][0]:.4f} rad)")
rows = ALL["measured_drift"][1]
out["compile_seconds_median"] = float(np.median(compile_times))
out["rows"] = rows
(HERE / "compiler_benchmark.json").write_text(json.dumps(out, indent=1, default=float))
print(f"\nmedian compile time {out['compile_seconds_median'] * 1000:.0f} ms; total {time.time() - t0:.0f} s. Saved compiler_benchmark.json")
