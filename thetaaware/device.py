"""Simulated device: runs a compiled physical circuit under a measured gate model (a "truth" calibration).

Each fractional rzz(x) on a calibrated pair becomes RZZ(x + delta(x)) . RZ_a(alpha(x)) . RZ_b(beta(x))
followed by two-qubit depolarising noise with survival 1 - 16/15 eps(x) (the same convention as the
mirror-circuit fit and as 17_paper_analysis.predict). Each cz gets depolarising noise from the IBM-reported
error. Single-qubit gates and readout are ideal, so differences come from the two-qubit gates only.
The truth may differ from the calibration the compiler used (drift); see drifted().
"""
from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import depolarizing_error

from .calibration import Calibration, PairCal

_SIM = AerSimulator(method="density_matrix")


def compact(qc: QuantumCircuit) -> tuple[QuantumCircuit, list[int]]:
    """Drop idle wires. Returns the small circuit and the original index of each kept qubit."""
    idx = {q: i for i, q in enumerate(qc.qubits)}
    used = sorted({idx[q] for ins in qc.data if ins.operation.name not in ("barrier",) for q in ins.qubits})
    pos = {o: n for n, o in enumerate(used)}
    out = QuantumCircuit(len(used), qc.num_clbits)
    for ins in qc.data:
        if ins.operation.name == "barrier":
            continue
        qs = [pos[idx[q]] for q in ins.qubits]
        cs = [qc.find_bit(c).index for c in ins.clbits]
        out.append(ins.operation, qs, cs)
    return out, used


def noisy(qc: QuantumCircuit, truth: Calibration) -> tuple[QuantumCircuit, list[int]]:
    small, used = compact(qc)
    out = QuantumCircuit(small.num_qubits)
    for ins in small.data:
        op = ins.operation
        q = [small.find_bit(x).index for x in ins.qubits]
        if op.name == "measure":
            continue
        if op.name == "rzz":
            x = float(op.params[0])
            cal = truth.get_pair(used[q[0]], used[q[1]])
            if cal is None:
                out.rzz(x, *q)
                out.append(depolarizing_error(16 / 15 * 1.5e-3, 2).to_instruction(), q)
                continue
            if not (0 <= x <= np.pi / 2 + 1e-9):
                raise ValueError(f"hardware rzz angle out of range: {x}")
            p = cal.at(x)
            out.rzz(x + p["delta"], *q); out.rz(p["alpha"], q[0]); out.rz(p["beta"], q[1])
            out.append(depolarizing_error(min(16 / 15 * p["eps"], 1.0), 2).to_instruction(), q)
        elif op.name == "cz":
            cal = truth.get_pair(used[q[0]], used[q[1]])
            r = cal.reported if cal is not None else 1.5e-3
            out.cz(*q)
            out.append(depolarizing_error(16 / 15 * r, 2).to_instruction(), q)
        else:
            out.append(op, q)
    return out, used


def ideal_probs(qc: QuantumCircuit) -> dict:
    small, _ = compact(qc)
    small = small.remove_final_measurements(inplace=False)
    from qiskit.quantum_info import Statevector
    return Statevector(small).probabilities_dict()


def noisy_probs(qc: QuantumCircuit, truth: Calibration) -> dict:
    circ, _ = noisy(qc, truth)
    circ.save_probabilities_dict()
    res = _SIM.run(circ).result()
    p = res.data(0)["probabilities"]
    n = circ.num_qubits
    return {format(int(k, 16) if isinstance(k, str) else int(k), f"0{n}b"): float(v) for k, v in p.items()}


def state_fidelity(compiled: QuantumCircuit, original: QuantumCircuit, truth: Calibration, layout=None) -> float:
    """layout[i] = the physical qubit that logical qubit i of `original` was placed on (None: the same index)."""
    if layout is not None:
        if any(i.operation.name == "measure" for i in original.data):
            raise ValueError("compile without measurements: the transpiler may drop phase gates before a measurement")
        n_phys = max(max(layout) + 1, compiled.num_qubits)
        moved = QuantumCircuit(n_phys)
        for ins in original.data:
            if ins.operation.name == "barrier":
                continue
            moved.append(ins.operation, [layout[original.find_bit(q).index] for q in ins.qubits])
        return _state_fidelity(compiled, moved, truth)
    return _state_fidelity(compiled, original, truth)


def _state_fidelity(compiled: QuantumCircuit, original: QuantumCircuit, truth: Calibration) -> float:
    """<psi_ideal| rho_device |psi_ideal>, before measurement: the strict metric (every error counts)."""
    if any(i.operation.name == "measure" for i in original.data):
        raise ValueError("compile without measurements: the transpiler may drop phase gates before a measurement")
    from qiskit.quantum_info import Statevector
    circ, used = noisy(compiled, truth)
    circ.save_density_matrix()
    rho = np.asarray(_SIM.run(circ).result().data(0)["density_matrix"])
    small, used0 = compact(original)
    if used0 != used:
        raise ValueError(f"compiled circuit uses other qubits than the original: {used} vs {used0}")
    psi = Statevector(small.remove_final_measurements(inplace=False)).data
    return float(np.real(np.conj(psi) @ rho @ psi))


def hellinger_fidelity(p: dict, q: dict) -> float:
    keys = set(p) | set(q)
    return float(sum(np.sqrt(p.get(k, 0) * q.get(k, 0)) for k in keys) ** 2)


def drifted(cal: Calibration, sigma: float, rng: np.random.Generator) -> Calibration:
    """A copy whose coherent parameters moved by a smooth random drift of typical size sigma (rad):
    an offset plus a slope across the angle grid, independently for delta, alpha and beta."""
    out = Calibration()
    for k, c in cal.items():
        def move(v, th):
            off, slope = rng.normal(0, sigma), rng.normal(0, sigma)
            return v + off + slope * (th - th.mean()) / max(np.ptp(th), 1e-9)
        out[k] = PairCal(c.pair, c.th, move(c.delta, c.th), move(c.alpha, c.th), move(c.beta, c.th), c.eps_th, c.eps, c.reported, c.source + " +drift")
    return out
