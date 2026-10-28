"""Compensation test (first H2 evidence): does correcting the measured delta(theta) give the right answer more often?

Circuit: |++> -> K x RZZ(theta) -> H H, with K*theta = pi (ideal '11') or 2*pi (ideal '00').
Variants per pair:
  raw        RZZ(theta) as asked
  corrected  RZZ(theta') with theta' + delta(theta') = theta (inverted measured response), if reachable;
             else two gates RZZ(a) . X RZZ(b) X with r(a) - r(b) = theta (b = smallest calibrated angle).
Default: dry run. --submit sends ONE job.
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

CRN = "crn:v1:bluemix:public:quantum-computing:us-east:a/ebc0228bd456434081c18bc094bd91e6:576e2f1c-9255-405d-b933-0f01ca671a9f::"
HERE = Path(__file__).parent
CALIB = HERE / "calib_db7sns0r1c5c738l7vm0.json"
EXCLUDE = [(93, 94)]                       # delta not measurable (CI spans +-1.5 rad)
TARGETS = {1: 24, 2: 12, 3: 8, 4: 6, 6: 4, 8: 3, 12: 2}   # theta = j*pi/24, K = 24/j  (K*theta = pi)
SHOTS = 2000
SEED = 20261015

ap = argparse.ArgumentParser(); ap.add_argument("--submit", action="store_true"); args = ap.parse_args()
cal = json.load(open(CALIB))
pairs = [tuple(json.loads(k.replace("(", "[").replace(")", "]"))) for k in cal["pairs"]]
pairs = [p for p in pairs if p not in EXCLUDE]

def plan(pr, theta):
    """Return list of ('rzz', angle) / ('x',) ops implementing the corrected RZZ(theta) on this pair."""
    c = cal["pairs"][str(pr)]
    th, r = np.array(c["theta"]), np.array(c["theta"]) + np.array(c["delta"])
    if np.all(np.diff(r) > 0) and r[0] <= theta <= r[-1]:
        return [("rzz", float(np.interp(theta, r, th)))], "single"
    if np.all(np.diff(r) > 0):
        b = float(th[0]); need = theta + r[0]
        if r[0] <= need <= r[-1]:
            return [("rzz", float(np.interp(need, r, th))), ("x",), ("rzz", b), ("x",)], "two-gate"
    return [("rzz", theta)], "uncorrectable"

impl = {}
for pr in pairs:
    for j in TARGETS:
        impl[(pr, j)] = plan(pr, j * np.pi / 24)
print("Corrected implementations (theta -> ops):")
for pr in pairs:
    print(" ", pr, " | ".join(f"{j}pi/24:{impl[(pr, j)][1][0]}"
                               + (f"({impl[(pr, j)][0][0][1]:.3f})" if impl[(pr, j)][1] == "single" else "")
                               for j in TARGETS))

P = len(pairs)
def circuit(j, mult, corrected):
    K, theta = TARGETS[j] * mult, j * np.pi / 24
    qc = QuantumCircuit(QuantumRegister(2 * P), ClassicalRegister(2 * P, "c"))
    qc.h(range(2 * P)); qc.barrier()
    for _ in range(K):
        for i, pr in enumerate(pairs):
            ops = impl[(pr, j)][0] if corrected else [("rzz", theta)]
            for op in ops:
                if op[0] == "rzz": qc.rzz(op[1], 2 * i, 2 * i + 1)
                else: qc.x(2 * i)
        qc.barrier()
    qc.h(range(2 * P))
    qc.measure(range(2 * P), range(2 * P))
    return qc

meta, circs = [], []
for j in TARGETS:
    for mult in (1, 2):                 # total pi -> '11', total 2pi -> '00'
        for corr in (False, True):
            circs.append(circuit(j, mult, corr)); meta.append({"j": j, "mult": mult, "corrected": corr})
order = np.random.default_rng(SEED).permutation(len(circs))
circs = [circs[k] for k in order]; meta = [meta[k] for k in order]

service = QiskitRuntimeService(channel="ibm_quantum_platform",
                               token=(HERE / ".ibm_key").read_text().strip(), instance=CRN)
backend = service.backend(cal["backend"], use_fractional_gates=True)
isa = transpile(circs, backend, initial_layout=[q for p in pairs for q in p], optimization_level=0)
for qc, m in zip(isa, meta):
    K = TARGETS[m["j"]] * m["mult"]
    exp = sum(K * (sum(1 for o in impl[(pr, m["j"])][0] if o[0] == "rzz") if m["corrected"] else 1) for pr in pairs)
    ops = qc.count_ops()
    if ops.get("rzz", 0) != exp or any(g in ops for g in ("cz", "ecr", "cx")):
        sys.exit(f"ABORT before submit: {m} -> {dict(ops)} expected {exp} rzz")
print(f"Transpile check OK: {len(isa)} circuits x {SHOTS} shots on {backend.name} (queue {backend.status().pending_jobs})")
if not args.submit:
    sys.exit("DRY RUN only.")

job = SamplerV2(backend).run(isa, shots=SHOTS)
print("JOB ID:", job.job_id())
out = {"job_id": job.job_id(), "backend": backend.name, "pairs": pairs, "shots": SHOTS, "meta": meta,
       "impl": {f"{pr}|{j}": impl[(pr, j)] for pr in pairs for j in TARGETS},
       "calibration": str(CALIB.name), "submitted": time.strftime("%Y-%m-%dT%H:%M:%S")}
f = HERE / f"comp_{job.job_id()}.json"
f.write_text(json.dumps(out, indent=1))
res = job.result()
out["counts"] = [r.data.c.get_counts() for r in res]
out["usage_seconds"] = job.usage()
f.write_text(json.dumps(out, indent=1, default=str))
print("QPU seconds billed:", out["usage_seconds"]); print("Saved", f.name)
