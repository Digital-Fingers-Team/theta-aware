"""Fair demo: what theta-Aware decides, and what it buys, on a small circuit.

  python 24_demo.py                      offline: choices, predicted error, simulated fidelity (no key, no QPU)
  python 24_demo.py --hardware           dry run on IBM: logs in, builds and checks the jobs, prints the plan, submits nothing
  python 24_demo.py --hardware --submit  runs the plan (Qiskit-fractional vs theta-Aware, 2,000 shots each); ASK BEFORE USING QPU TIME

Offline numbers come from the 14 Oct calibration (marrakesh_after_e8) and the simulated device of device.py.
The hardware path needs a fresh calibration of the chosen pairs first (E11 in RESEARCH_LOG.md): a compiler
fed month-old coherent parameters is not a fair test.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit.transpiler import CouplingMap

from thetaaware import calibration as C
from thetaaware import compiler as T
from thetaaware import device as D

HERE = Path(__file__).parent
ap = argparse.ArgumentParser()
ap.add_argument("--hardware", action="store_true")
ap.add_argument("--submit", action="store_true")
ap.add_argument("--theta", type=float, default=np.pi / 12, help="RZZ angle (default pi/12, where (10, 11) is worst)")
ap.add_argument("--reps", type=int, default=12, help="how many times the gate repeats (K*theta = pi -> ideal output 11)")
args = ap.parse_args()

cal = C.marrakesh_after_e8()


def demo_circuit(theta, reps):
    qc = QuantumCircuit(2)
    qc.h([0, 1])
    for _ in range(reps):
        qc.rzz(theta, 0, 1)
    qc.h([0, 1])
    return qc


qc = demo_circuit(args.theta, args.reps)
print(f"Circuit: |++>, RZZ({args.theta:.4f}) x {args.reps}, H H   (ideal output: '11' when K*theta = pi)\n")
print(f"{'pair':>9} | {'policy':<22} | {'choice':<12} | {'2q gates':>8} | {'error score':>15} | {'simulated fidelity':>18}")
print("-" * 100)
rows = []
for pair in cal:
    cm = CouplingMap([pair, pair[::-1]])
    for label, pol in (("Qiskit, fractional on", "frac"), ("Qiskit, fractional off", "cz"), ("theta-Aware", "theta")):
        out, rep = T.compile_circuit(qc, cm, list(pair), cal, policy=pol)
        # The simulated device is the same calibration: the best case for corrections. Real drift makes it worse.
        F = D.state_fidelity(out, qc, cal, layout=list(pair))
        cost = sum(c.costs.get(c.option, 0) for c in rep.choices)
        g2 = out.count_ops().get("rzz", 0) + out.count_ops().get("cz", 0)
        rows.append((pair, label, F))
        print(f"{str(pair):>9} | {label:<22} | {rep.choices[0].option:<12} | {g2:>8} | {cost:>15.4f} | {F:>18.4f}")
    print("-" * 100)
best = max((r for r in rows if r[1] == "theta-Aware"), key=lambda r: r[2])
print(f"\ntheta-Aware layout choice: pair {best[0]} (simulated fidelity {best[2]:.4f}).")
print("Simulated device = the compiler's own calibration (no drift): the gap is an upper bound; see Section 4.4 of the paper for drift.")
print("Error score: the compiler's ranking cost (sum of per-gate predicted errors); it can exceed 1 and is not a probability.")

if not args.hardware:
    sys.exit(0)

# ---------------- hardware path: dry run unless --submit ----------------
from qiskit import ClassicalRegister, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

key_file = next((HERE / k for k in (".ibm_key", ".ibm_key2") if (HERE / k).exists()), None)
if key_file is None:
    sys.exit("No key file (.ibm_key or .ibm_key2).")
try:
    service = QiskitRuntimeService(channel="ibm_quantum_platform", token=key_file.read_text().strip())
    backend = service.backend("ibm_marrakesh", use_fractional_gates=True)
except Exception as e:
    sys.exit(f"IBM login or backend failed: {str(e)[:200]}")

PAIRS = [(10, 11), (14, 15)]
jobs, meta = [], []
for pair in PAIRS:
    for pol in ("frac", "theta"):
        out, rep = T.apply(transpile(qc, backend, initial_layout=list(pair), optimization_level=0), cal, policy=pol)
        cr = ClassicalRegister(2, "c"); out.add_register(cr); out.measure(pair[0], cr[0]); out.measure(pair[1], cr[1])
        isa = transpile(out, backend, optimization_level=0)
        ops = isa.count_ops()
        n_rzz = ops.get("rzz", 0); n_cz = ops.get("cz", 0)
        expect = {"frac": args.reps, "frac+rz": args.reps, "frac+rz+pre": args.reps, "cz": 0}[rep.choices[0].option]
        if n_rzz != expect:
            sys.exit(f"ABORT: {pair} {pol}: expected {expect} rzz after transpile, found {dict(ops)}")
        jobs.append(isa); meta.append(dict(pair=pair, policy=pol, choice=rep.choices[0].option, rzz=n_rzz, cz=n_cz))
SHOTS = 2000
print(f"\nHardware plan on {backend.name}: {len(jobs)} circuits x {SHOTS} shots (about {len(jobs) * 0.3:.0f}-{len(jobs) * 1.0:.0f} QPU s by the measured cost per circuit).")
for m in meta:
    print("  ", m)
print(f"Queue: {backend.status().pending_jobs} jobs.")
print("WARNING: these use the 14 Oct calibration. Re-calibrate the pairs first (E11) for a fair hardware test.")
if not args.submit:
    sys.exit("DRY RUN only. Nothing was submitted.")
job = SamplerV2(backend).run(jobs, shots=SHOTS)
print("JOB ID:", job.job_id(), flush=True)
res = job.result()
for m, r in zip(meta, res):
    c = r.data.c.get_counts(); t = sum(c.values())
    print(m["pair"], m["policy"], m["choice"], f"P('11') = {c.get('11', 0) / t:.3f}")
print("QPU usage:", job.usage())
