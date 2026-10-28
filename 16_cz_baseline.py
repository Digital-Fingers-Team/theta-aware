"""E10 (from E9 script): compiler implementation choice for small angles on pair (10,11).
Below the reachable range (theta < r(min)), a single pre-distorted gate cannot fix delta.
Alternative: RZZ(theta) ~= RZZ(a) . X RZZ(b) X  with r(a) - r(b) = theta, a and b ON calibrated grid points
(r = theta + delta from round-2 calibration), plus virtual-RZ local-phase correction on every physical gate.
  pi/12: a = pi/4, b = pi/12  (r diff 0.267 vs 0.262)
  pi/8 : a = pi/3, b = pi/12  (r diff 0.394 vs 0.393)
Variants: raw | local | cz (standard CX.RZ.CX decomposition, no fractional gate). Pair isolated.
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

CRN = "crn:v1:bluemix:public:quantum-computing:us-east:a/ebc0228bd456434081c18bc094bd91e6:576e2f1c-9255-405d-b933-0f01ca671a9f::"
HERE = Path(__file__).parent
PAIR = (10, 11)
SHOTS = 2000
cal = json.load(open(HERE / "round2_db7t6ier6oqs738898ig.json"))["calibration"]["(10, 11)"]
TH = np.array(cal["th"])
def loc(x):
    k = int(np.argmin(abs(TH - x))); assert abs(TH[k] - x) < 1e-9, x
    return cal["alpha"][k], cal["beta"][k]
CASES = {2: (np.pi / 4, np.pi / 12), 3: (np.pi / 3, np.pi / 12)}   # j -> (a, b)
KS = {2: (12, 24), 3: (8, 16)}

ap = argparse.ArgumentParser(); ap.add_argument("--submit", action="store_true"); args = ap.parse_args()

def circ(j, K, variant):
    th = j * np.pi / 24
    qc = QuantumCircuit(2, 2); qc.h([0, 1]); qc.barrier()
    for _ in range(K):
        if variant == "raw":
            qc.rzz(th, 0, 1)
        elif variant == "local":
            al, be = np.interp(th, TH, cal["alpha"]), np.interp(th, TH, cal["beta"])
            qc.rzz(th, 0, 1); qc.rz(-al, 0); qc.rz(-be, 1)
        else:   # standard decomposition: RZZ(theta) = CX . (I x RZ(theta)) . CX  -> 2 CZ on hardware
            qc.cx(0, 1); qc.rz(th, 1); qc.cx(0, 1)
        qc.barrier()
    qc.h([0, 1]); qc.measure([0, 1], [0, 1])
    return qc

meta, circs = [], []
for j in CASES:
    for K in KS[j]:
        for v in ("raw", "local", "cz"):
            circs.append(circ(j, K, v)); meta.append({"j": j, "K": K, "variant": v})
service = QiskitRuntimeService(channel="ibm_quantum_platform", token=(HERE / ".ibm_key").read_text().strip(), instance=CRN)
backend = service.backend("ibm_marrakesh", use_fractional_gates=True)
isa = transpile(circs, backend, initial_layout=list(PAIR), optimization_level=0)
for qc, m in zip(isa, meta):
    ops = qc.count_ops(); exp = 0 if m["variant"] == "cz" else m["K"]
    if ops.get("rzz", 0) != exp or ops.get("cz", 0) != (2 * m["K"] if m["variant"] == "cz" else 0):
        sys.exit(f"ABORT {m} {dict(ops)}")
u = service.usage()["usage_remaining_seconds"]
print(f"Check OK: {len(isa)} circuits x {SHOTS}; quota remaining {u} s; queue {backend.status().pending_jobs}")
if not args.submit: sys.exit("DRY RUN only.")
if u < 40: sys.exit("ABORT: less than 40 s of quota left")
job = SamplerV2(backend).run(isa, shots=SHOTS); print("JOB ID:", job.job_id(), flush=True)
res = job.result(); counts = [r.data.c.get_counts() for r in res]
out = {"job_id": job.job_id(), "pair": PAIR, "meta": meta, "counts": counts, "usage": job.usage(),
       "cases": {str(k): v for k, v in CASES.items()}, "finished": time.strftime("%Y-%m-%dT%H:%M:%S")}
(HERE / f"czbase_{job.job_id()}.json").write_text(json.dumps(out, indent=1, default=str))
print("QPU s:", job.usage())
for j in CASES:
    for K in KS[j]:
        ideal = "11" if K * j == 24 else "00"
        row = []
        for v in ("raw", "local", "cz"):
            c = counts[next(k for k, m in enumerate(meta) if m == {"j": j, "K": K, "variant": v})]
            row.append(c.get(ideal, 0) / sum(c.values()))
        print(f"{j}pi/24 K={K:2d} ideal {ideal}: raw {row[0]:.3f} | local {row[1]:.3f} | cz {row[2]:.3f}")
