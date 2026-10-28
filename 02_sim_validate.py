"""Validate the method in simulation before spending QPU time.
We inject a KNOWN over-rotation delta and depolarizing error into RZZ, then check:
  (1) mirror circuits are blind to delta (same decay with and without it)
  (2) phase amplification recovers delta
"""
import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error

P_DEPOL = 0.01          # injected incoherent error per RZZ
DELTA_TRUE = 0.02       # injected coherent over-rotation (rad)
SHOTS = 20000

noise = NoiseModel()
noise.add_all_qubit_quantum_error(depolarizing_error(P_DEPOL, 2), ["rzz"])
sim = AerSimulator(noise_model=noise, seed_simulator=7)

def mirror(theta, depth, delta):
    qc = QuantumCircuit(2)
    for _ in range(depth):
        qc.rzz(theta + delta, 0, 1)
    for _ in range(depth):          # inverse via folding: X . RZZ(theta) . X on qubit 0
        qc.x(0); qc.rzz(theta + delta, 0, 1); qc.x(0)
    qc.measure_all()
    return qc

def survival(qc):
    c = sim.run(qc, shots=SHOTS).result().get_counts()
    return c.get("00", 0) / SHOTS

print("(1) Mirror survival, theta=0.6")
for d in [1, 4, 8, 16]:
    a = survival(mirror(0.6, d, 0.0)); b = survival(mirror(0.6, d, DELTA_TRUE))
    print(f"  depth {d:2d}: no delta {a:.3f} | with delta {b:.3f}")

def phase_amp(theta, n, control, basis, delta):
    qc = QuantumCircuit(2, 1)
    if control: qc.x(0)
    qc.h(1)
    for _ in range(n):
        qc.rzz(theta + delta, 0, 1)
    if basis == "Y": qc.sdg(1)
    qc.h(1)
    qc.measure(1, 0)
    return qc

def expval(qc):
    c = sim.run(qc, shots=SHOTS).result().get_counts()
    return (c.get("0", 0) - c.get("1", 0)) / SHOTS

def wrap(x):
    return (x + np.pi) % (2 * np.pi) - np.pi

print("(2) Phase amplification")
for theta in [0.2, 0.6, 1.2]:
    Ns, res = [1, 2, 4, 8, 16], []
    for n in Ns:
        ph = []
        for ctrl in (0, 1):
            x = expval(phase_amp(theta, n, ctrl, "X", DELTA_TRUE))
            y = expval(phase_amp(theta, n, ctrl, "Y", DELTA_TRUE))
            ph.append(np.arctan2(y, x))       # RZ(phi)|+> gives <X>=cos(phi), <Y>=sin(phi)
        total = wrap(ph[0] - ph[1])           # = 2*N*(theta+delta), single-qubit Z drifts cancel
        res.append(wrap(total - 2 * n * theta) / 2)   # = N*delta
    Ns = np.array(Ns); res = np.array(res)
    est = (Ns @ res) / (Ns @ Ns)
    print(f"  theta={theta}: delta_est={est:+.4f}  (true {DELTA_TRUE:+.4f})")
