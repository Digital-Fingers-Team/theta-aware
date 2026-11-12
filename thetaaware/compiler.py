"""The theta-aware compiler: for every RZZ(theta) it picks how to run it on its qubit pair.

Options for one RZZ(theta) on a calibrated pair (theta first folded into (0, pi/2], the range
IBM's fractional gate accepts, with exact identities):

    frac          the fractional gate as it is                     (what Qiskit does with fractional gates on)
    frac+rz       + virtual RZ that undo the measured local phases (free: RZ is a frame change)
    frac+rz+pre   + the requested angle pre-distorted so theta+delta lands on theta
    cz            the standard CX.RZ.CX built from two CZ           (what Qiskit does with fractional gates off)

Each option gets a predicted error from the measured model (calibration.py):

    frac*  : eps(theta) + m * coh(residual coherent error)
    cz     : 2 * IBM-reported two-qubit error

coh() is the average gate infidelity of the coherent residual. A correction removes a measured
error only up to drift and model error; KAPPA is the share of it that survives (fitted on E4 only,
see 21_compiler_replay.py). m is how many times the circuit repeats this (pair, angle): coherent
errors add up in amplitude, so their cost per gate grows with the repetitions.
The option with the lowest predicted error wins; ties go to the one with fewer two-qubit gates.
Gates on pairs with no calibration are left as plain fractional gates (Qiskit's default).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import RZZGate

from .calibration import Calibration, PairCal

OPTIONS = ("frac", "frac+rz", "frac+rz+pre", "cz")
TWO_Q = {"frac": 1, "frac+rz": 1, "frac+rz+pre": 1, "cz": 2}
KAPPA = 0.5  # placeholder; replaced by the value fitted on E4 (21_compiler_replay.py writes compiler_params.json)
BASIS_FRAC = ["rz", "sx", "x", "cz", "rzz"]
BASIS_CZ = ["rz", "sx", "x", "cz"]

_Z = np.array([[1, 1], [1, -1], [-1, 1], [-1, -1]], float)  # (z_a, z_b) for |00>,|01>,|10>,|11> with a first


def coh(delta: float, alpha: float, beta: float) -> float:
    """Average gate infidelity of exp(-i/2 (delta ZZ + alpha Z_a + beta Z_b)) (d = 4)."""
    ph = -0.5 * (delta * _Z[:, 0] * _Z[:, 1] + alpha * _Z[:, 0] + beta * _Z[:, 1])
    tr = np.exp(1j * ph).sum()
    return float(1 - (abs(tr) ** 2 / 4 + 1) / 5)


def fold(theta: float) -> tuple[float, bool, bool]:
    """RZZ(theta) = [Z.Z if pi_flip] . [X_a ... X_a if neg] RZZ(t), with t in [0, pi/2] (global phase ignored)."""
    t = (theta + np.pi) % (2 * np.pi) - np.pi          # (-pi, pi]
    pi_flip = False
    if abs(t) > np.pi / 2:
        t = t - np.sign(t) * np.pi                     # RZZ(t) = RZZ(t -/+ pi) . RZZ(+/-pi), RZZ(pi) ~ Z (x) Z
        pi_flip = True
    neg = t < 0
    return abs(t), neg, pi_flip


@dataclass
class Choice:
    pair: tuple[int, int]
    theta: float
    t: float
    option: str
    costs: dict
    calibrated: bool


@dataclass
class Report:
    choices: list = field(default_factory=list)

    def counts(self) -> Counter:
        return Counter(c.option for c in self.choices)

    def predicted_error(self) -> float:
        return float(sum(c.costs[c.option] for c in self.choices if c.calibrated))

    def two_qubit_gates(self) -> int:
        return int(sum(TWO_Q[c.option] for c in self.choices))


def option_costs(cal: PairCal, t: float, m: int, kappa: float, allowed=OPTIONS) -> dict:
    p = cal.at(t)
    out = {}
    if "frac" in allowed:
        out["frac"] = p["eps"] + m * coh(p["delta"], p["alpha"], p["beta"])
    if "frac+rz" in allowed:
        out["frac+rz"] = p["eps"] + m * coh(p["delta"], kappa * p["alpha"], kappa * p["beta"])
    if "frac+rz+pre" in allowed:
        x = cal.pre_distort(t)
        if x is not None:
            q = cal.at(x)
            # the model says x + delta(x) = t exactly; what survives is the corrected share kappa of each error
            out["frac+rz+pre"] = q["eps"] + m * coh(kappa * p["delta"], kappa * q["alpha"], kappa * q["beta"])
    if "cz" in allowed:
        out["cz"] = 2 * cal.reported
    return out


def choose(costs: dict) -> str:
    best = min(costs.values())
    tied = [o for o in OPTIONS if o in costs and costs[o] <= best * (1 + 1e-9) + 1e-15]
    return min(tied, key=lambda o: (TWO_Q[o], OPTIONS.index(o)))


def _emit(out: QuantumCircuit, a, b, theta: float, option: str, cal: PairCal | None):
    """Append one RZZ(theta) on qubits a, b using `option`. Exact (up to global phase) when the gate is ideal."""
    t, neg, pi_flip = fold(theta)
    if pi_flip:
        out.rz(np.pi, a); out.rz(np.pi, b)
    if t < 1e-12:
        return
    if option == "cz":
        # RZZ(theta) = CX . RZ_b(theta) . CX, CX = H_b CZ H_b; uses the unfolded theta directly.
        out.h(b); out.cz(a, b); out.h(b); out.rz(-t if neg else t, b); out.h(b); out.cz(a, b); out.h(b)
        return
    if neg:
        out.x(a)
    if option == "frac":
        out.rzz(t, a, b)
    else:
        x = cal.pre_distort(t) if option == "frac+rz+pre" else t
        x = t if x is None else x
        p = cal.at(x)
        out.rzz(x, a, b); out.rz(-p["alpha"], a); out.rz(-p["beta"], b)
    if neg:
        out.x(a)


def apply(circuit: QuantumCircuit, calibration: Calibration, policy: str = "theta", kappa: float | None = None,
          allowed=OPTIONS) -> tuple[QuantumCircuit, Report]:
    """Rewrite every rzz of a physical (already laid-out) circuit.

    policy: "theta" (choose per gate), or force one option for every gate ("frac", "frac+rz", "frac+rz+pre", "cz").
    """
    kappa = load_kappa() if kappa is None else kappa
    idx = {q: i for i, q in enumerate(circuit.qubits)}
    reps = Counter()
    for ins in circuit.data:
        if ins.operation.name == "rzz":
            if ins.operation.is_parameterized():
                raise ValueError("bind all parameters before compiling (the choice depends on the angle)")
            a, b = (idx[q] for q in ins.qubits)
            reps[(min(a, b), max(a, b), round(fold(float(ins.operation.params[0]))[0], 6))] += 1
    out = circuit.copy_empty_like()
    rep = Report()
    for ins in circuit.data:
        op = ins.operation
        if op.name != "rzz":
            out.append(ins)
            continue
        if op.is_parameterized():
            raise ValueError("bind all parameters before compiling (the choice depends on the angle)")
        theta = float(op.params[0])
        qa, qb = ins.qubits
        a, b = idx[qa], idx[qb]
        t = fold(theta)[0]
        cal = calibration.get_pair(a, b)
        if cal is None:
            option, costs = ("cz" if policy == "cz" else "frac"), {}
        else:
            m = reps[(min(a, b), max(a, b), round(t, 6))]
            costs = option_costs(cal, t, m, kappa, allowed)
            option = choose(costs) if policy == "theta" else policy
            if option == "frac+rz+pre" and cal.pre_distort(t) is None:
                option = "frac+rz"
        _emit(out, qa, qb, theta, option, cal)
        rep.choices.append(Choice((a, b), theta, t, option, costs, cal is not None))
    return out, rep


def compile_circuit(circuit: QuantumCircuit, coupling_map, layout, calibration: Calibration, policy: str = "theta",
                    kappa: float | None = None, allowed=OPTIONS, seed: int = 1) -> tuple[QuantumCircuit, Report]:
    """Full pipeline: Qiskit lays out and routes with fractional RZZ allowed, then the theta-aware pass,
    then a basis translation that leaves rzz untouched (optimization_level=0)."""
    basis = BASIS_CZ if policy == "cz" else BASIS_FRAC
    laid = transpile(circuit, basis_gates=BASIS_FRAC, coupling_map=coupling_map, initial_layout=layout,
                     optimization_level=1, seed_transpiler=seed)
    rewritten, rep = apply(laid, calibration, policy, kappa, allowed)
    final = transpile(rewritten, basis_gates=basis, optimization_level=0)
    return final, rep


def load_kappa() -> float:
    import json
    from .calibration import ROOT
    f = ROOT / "compiler_params.json"
    return float(json.loads(f.read_text())["kappa"]) if f.exists() else KAPPA


def score_layout(edges_with_angles, calibration: Calibration, kappa: float | None = None) -> float:
    """Predicted error of a candidate layout: sum over its RZZ of the best option's cost.
    edges_with_angles: [((a, b), theta), ...] on physical qubits. Uncalibrated edges count as IBM's error."""
    kappa = load_kappa() if kappa is None else kappa
    reps = Counter(((min(a, b), max(a, b)), round(fold(t)[0], 6)) for (a, b), t in edges_with_angles)
    total = 0.0
    for (a, b), th in edges_with_angles:
        cal = calibration.get_pair(a, b)
        t = fold(th)[0]
        if cal is None:
            total += 2e-3
            continue
        c = option_costs(cal, t, reps[((min(a, b), max(a, b)), round(t, 6))], kappa)
        total += c[choose(c)]
    return total
