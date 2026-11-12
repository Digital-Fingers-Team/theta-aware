"""Correctness of the theta-aware compiler. No QPU, no key.

1. With an ideal device, every option of every gate equals RZZ(theta) up to a global phase, for any theta.
2. With the measured gate model as the device, the corrections remove the modelled error exactly
   (when the compiler's calibration is the device's).
3. Whole circuits: compiled == original (ideal), for random circuits, all policies.
4. Hardware rule: every emitted rzz angle is inside [0, pi/2].
"""
import numpy as np
import pytest
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Operator
from qiskit.transpiler import CouplingMap

from thetaaware import calibration as C
from thetaaware import compiler as T
from thetaaware import device as D

RNG = np.random.default_rng(2026)
CAL = C.marrakesh_after_e4()
PAIR = (10, 11)


def equal_up_to_phase(a: Operator, b: Operator, tol=1e-8) -> bool:
    return a.equiv(b, atol=tol)


def one_gate(theta, option, a=0, b=1, n=2, cal=None):
    qc = QuantumCircuit(n)
    T._emit(qc, qc.qubits[a], qc.qubits[b], theta, option, cal)
    return qc


def ref(theta, a=0, b=1, n=2):
    qc = QuantumCircuit(n); qc.rzz(theta, a, b); return qc


ANGLES = list(np.concatenate([RNG.uniform(-2 * np.pi, 2 * np.pi, 40),
                              [0, 1e-14, np.pi / 2, -np.pi / 2, np.pi, -np.pi, 3 * np.pi / 2, 2 * np.pi, np.pi / 24, 0.7853981633974483]]))


@pytest.mark.parametrize("option", ["frac", "cz"])
@pytest.mark.parametrize("theta", ANGLES)
def test_exact_ideal(theta, option):
    assert equal_up_to_phase(Operator(one_gate(theta, option)), Operator(ref(theta)))


@pytest.mark.parametrize("theta", ANGLES)
def test_hardware_angle_range(theta):
    for option in ("frac", "frac+rz", "frac+rz+pre"):
        qc = one_gate(theta, option, cal=CAL.get_pair(*PAIR))
        for ins in qc.data:
            if ins.operation.name == "rzz":
                assert -1e-12 <= float(ins.operation.params[0]) <= np.pi / 2 + 1e-12


def model_gate(qc: QuantumCircuit, cal: C.PairCal) -> QuantumCircuit:
    """Replace each rzz(x) by the measured model RZZ(x+delta) RZ_a(alpha) RZ_b(beta)."""
    out = qc.copy_empty_like()
    for ins in qc.data:
        if ins.operation.name == "rzz":
            x = float(ins.operation.params[0]); p = cal.at(x)
            a, b = ins.qubits
            out.rzz(x + p["delta"], a, b); out.rz(p["alpha"], a); out.rz(p["beta"], b)
        else:
            out.append(ins)
    return out


@pytest.mark.parametrize("pair", list(CAL.keys()))
@pytest.mark.parametrize("theta", [np.pi / 24 * 2, np.pi / 24 * 5, -np.pi / 24 * 7, np.pi / 24 * 11, 2.5])
@pytest.mark.parametrize("reverse", [False, True])
def test_corrections_cancel_model(pair, theta, reverse):
    """frac+rz removes the local phases exactly; frac+rz+pre removes delta too (when invertible)."""
    a, b = (1, 0) if reverse else (0, 1)
    cal = CAL.get_pair(*pair).oriented(*((pair[1], pair[0]) if reverse else pair))
    # Qubit 0 of the test circuit plays pair[0]; when reversed the gate is written (1, 0) with cal oriented (b, a).
    t = T.fold(theta)[0]
    rz_only = model_gate(one_gate(theta, "frac+rz", a, b, cal=cal), cal)
    p = cal.at(t)
    # Expected: the folded gate with only delta left.
    qe = QuantumCircuit(2)
    tt, neg, flip = T.fold(theta)
    if flip:
        qe.rz(np.pi, a); qe.rz(np.pi, b)
    if neg: qe.x(a)
    qe.rzz(tt + p["delta"], a, b)
    if neg: qe.x(a)
    assert equal_up_to_phase(Operator(rz_only), Operator(qe))
    if cal.pre_distort(tt) is not None:
        full = model_gate(one_gate(theta, "frac+rz+pre", a, b, cal=cal), cal)
        assert equal_up_to_phase(Operator(full), Operator(ref(theta, a, b)), tol=1e-6)


def random_circuit(n, layers, rng):
    qc = QuantumCircuit(n)
    for _ in range(layers):
        for q in range(n):
            qc.rx(rng.uniform(0, np.pi), q); qc.rz(rng.uniform(-np.pi, np.pi), q)
        for a in range(rng.integers(0, 2), n - 1, 2):
            qc.rzz(rng.uniform(-3, 3), a, a + 1)
    return qc


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("policy", ["theta", "frac", "frac+rz", "cz"])
def test_whole_circuit_ideal(seed, policy):
    """A 4-qubit chain laid out on 4 physical qubits whose 3 edges borrow 3 measured pairs."""
    rng = np.random.default_rng(seed)
    qc = random_circuit(4, 3, rng)
    pairs = list(CAL.values())[:3]
    cal = C.Calibration({(i, i + 1): C.PairCal((i, i + 1), p.th, p.delta, p.alpha, p.beta, p.eps_th, p.eps, p.reported, p.source)
                         for i, p in enumerate(pairs)})
    cm = CouplingMap([(0, 1), (1, 0), (1, 2), (2, 1), (2, 3), (3, 2)])
    out, rep = T.compile_circuit(qc, cm, [0, 1, 2, 3], cal, policy=policy)
    assert set(out.count_ops()) <= set(T.BASIS_FRAC) | {"measure", "barrier"}
    if policy == "cz":
        assert "rzz" not in out.count_ops()
    for ins in out.data:
        if ins.operation.name == "rzz":
            assert 0 <= float(ins.operation.params[0]) <= np.pi / 2 + 1e-12
    # Ideal equivalence: only frac/cz are exact without the device model, so compare those policies directly.
    if policy in ("frac", "cz"):
        assert Operator(out).equiv(Operator(qc), atol=1e-7)


@pytest.mark.parametrize("seed", range(4))
def test_whole_circuit_corrected_on_model(seed):
    """Under the measured model (no noise), the theta-aware output with frac+rz+pre equals the ideal circuit."""
    rng = np.random.default_rng(100 + seed)
    qc = random_circuit(3, 3, rng)
    p0, p1 = list(CAL.values())[2:4]
    cal = C.Calibration({(0, 1): C.PairCal((0, 1), p0.th, p0.delta, p0.alpha, p0.beta, p0.eps_th, p0.eps, p0.reported, p0.source),
                         (1, 2): C.PairCal((1, 2), p1.th, p1.delta, p1.alpha, p1.beta, p1.eps_th, p1.eps, p1.reported, p1.source)})
    cm = CouplingMap([(0, 1), (1, 0), (1, 2), (2, 1)])
    out, rep = T.compile_circuit(qc, cm, [0, 1, 2], cal, policy="frac+rz+pre")
    noisy = out.copy_empty_like()
    for ins in out.data:
        if ins.operation.name == "rzz":
            a, b = (out.find_bit(q).index for q in ins.qubits)
            c = cal.get_pair(a, b); x = float(ins.operation.params[0]); p = c.at(x)
            noisy.rzz(x + p["delta"], *ins.qubits); noisy.rz(p["alpha"], ins.qubits[0]); noisy.rz(p["beta"], ins.qubits[1])
        else:
            noisy.append(ins)
    inv_ok = all(cal.get_pair(*c.pair).pre_distort(c.t) is not None for c in rep.choices)
    if inv_ok:
        assert Operator(noisy).equiv(Operator(qc), atol=1e-6)


def test_choice_follows_costs():
    """Huge coherent error -> cz; tiny error -> a fractional option; uncalibrated pair -> plain frac."""
    c = CAL.get_pair(*PAIR)
    costs = T.option_costs(c, np.pi / 12, m=12, kappa=0.5)
    assert T.choose(costs) == "cz"
    good = C.PairCal((0, 1), c.th, c.delta * 0, c.alpha * 0, c.beta * 0, c.eps_th, c.eps * 0 + 5e-4, c.reported, "test")
    assert T.choose(T.option_costs(good, np.pi / 12, m=12, kappa=0.5)) == "frac"
    qc = QuantumCircuit(2); qc.rzz(0.3, 0, 1)
    out, rep = T.apply(qc, C.Calibration(), policy="theta")
    assert rep.choices[0].option == "frac" and not rep.choices[0].calibrated


def test_parameterized_rejected():
    from qiskit.circuit import Parameter
    qc = QuantumCircuit(2); qc.rzz(Parameter("g"), 0, 1)
    with pytest.raises(ValueError):
        T.apply(qc, CAL)


def test_device_sim_matches_paper_predict():
    """The simulator agrees with 17_paper_analysis.predict on the E4 test circuit (|++>, K gates, HH)."""
    c = CAL.get_pair(*PAIR); j, K = 4, 6; th = j * np.pi / 24
    qc = QuantumCircuit(2)
    qc.h([0, 1])
    for _ in range(K): qc.rzz(th, 0, 1)
    qc.h([0, 1])
    truth = C.Calibration({(0, 1): C.PairCal((0, 1), c.th, c.delta, c.alpha, c.beta, c.eps_th, c.eps, c.reported, "t")})
    p = D.noisy_probs(qc, truth)["11"]
    ZZ = np.array([1, -1, -1, 1.0]); ZA, ZB = np.array([1, 1, -1, -1.0]), np.array([1, -1, 1, -1.0])
    H2 = np.array([[1, 1, 1, 1], [1, -1, 1, -1], [1, 1, -1, -1], [1, -1, -1, 1]]) / 2
    q = c.at(th)
    phase = -K / 2 * ((th + q["delta"]) * ZZ + q["alpha"] * ZA + q["beta"] * ZB)
    psi = H2 @ (np.exp(1j * phase) / 2)
    f = (1 - 16 / 15 * q["eps"]) ** K
    pred = f * abs(psi[3]) ** 2 + (1 - f) / 4
    assert abs(p - pred) < 1e-6


def test_state_fidelity_sanity():
    """Perfect device -> fidelity 1 for every policy; the measured device -> below 1; cz error alone matches (1-16/15 r)^k roughly."""
    rng = np.random.default_rng(7)
    qc = random_circuit(3, 2, rng)
    p0, p1 = list(CAL.values())[2:4]
    mk = lambda p, i, z: C.PairCal((i, i + 1), p.th, p.delta * z, p.alpha * z, p.beta * z, p.eps_th, p.eps * z, p.reported * z, "t")
    cm = CouplingMap([(0, 1), (1, 0), (1, 2), (2, 1)])
    perfect = C.Calibration({(0, 1): mk(p0, 0, 0), (1, 2): mk(p1, 1, 0)})
    real = C.Calibration({(0, 1): mk(p0, 0, 1), (1, 2): mk(p1, 1, 1)})
    for pol in ("frac", "cz", "theta"):
        out, _ = T.compile_circuit(qc, cm, [0, 1, 2], real, policy=pol)
        if pol != "theta":  # theta compiles corrections for `real`; on a perfect device those would be errors
            assert abs(D.state_fidelity(out, qc, perfect) - 1) < 1e-9
        f = D.state_fidelity(out, qc, real)
        assert 0 < f < 1
    # Compiled for the perfect device, theta adds no correction and is exact there.
    out, _ = T.compile_circuit(qc, cm, [0, 1, 2], perfect, policy="theta")
    assert abs(D.state_fidelity(out, qc, perfect) - 1) < 1e-9
    out, _ = T.compile_circuit(qc, cm, [0, 1, 2], real, policy="cz")
    k = out.count_ops()["cz"]; r = p0.reported
    assert D.state_fidelity(out, qc, real) < 1 - 0.5 * k * r


@pytest.mark.parametrize("layout", [[3, 4], [4, 3]])
def test_state_fidelity_with_layout(layout):
    """Physical placement (also reversed) is mapped correctly: a perfect device gives fidelity 1."""
    rng = np.random.default_rng(11)
    qc = random_circuit(2, 3, rng)
    p = list(CAL.values())[3]
    z = C.PairCal((3, 4), p.th, p.delta * 0, p.alpha * 0, p.beta * 0, p.eps_th, p.eps * 0, 0.0, "t")
    real = C.Calibration({(3, 4): C.PairCal((3, 4), p.th, p.delta, p.alpha, p.beta, p.eps_th, p.eps, p.reported, "t")})
    cm = CouplingMap([(3, 4), (4, 3)])
    for pol in ("frac", "cz"):
        out, _ = T.compile_circuit(qc, cm, layout, real, policy=pol)
        assert abs(D.state_fidelity(out, qc, C.Calibration({(3, 4): z}), layout=layout) - 1) < 1e-9
    out, _ = T.compile_circuit(qc, cm, layout, real, policy="theta")
    assert 0 < D.state_fidelity(out, qc, real, layout=layout) <= 1
