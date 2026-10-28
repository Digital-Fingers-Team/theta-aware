"""Pilot = go/no-go + real timing, in ONE job to avoid paying job overhead twice.

Default is a dry run: connects, checks the backend, transpiles, prints the plan. No QPU time.
Add --submit to actually send the job.

Key: put the IBM API key (one line) in ~/theta-aware/.ibm_key  (chmod 600).
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np
from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

CRN = "crn:v1:bluemix:public:quantum-computing:us-east:a/ebc0228bd456434081c18bc094bd91e6:576e2f1c-9255-405d-b933-0f01ca671a9f::"
HERE = Path(__file__).parent
ANGLES = [float(x) for x in np.linspace(np.pi / 24, np.pi / 2, 12)]   # last = pi/2 Clifford reference
MIRROR_DEPTHS = [1, 4, 8, 16, 32]
PHASE_NS = [1, 2, 4, 8, 16]                # doubling -> phase can be unwrapped step by step
PHASE_ANGLES = ANGLES
N_PAIRS = 8
FORCED_PAIRS = [(10, 11), (93, 94), (2, 3), (91, 98), (12, 13), (21, 36), (32, 33), (14, 15)]
SHOTS = 1000
SEED = 20261018

ap = argparse.ArgumentParser()
ap.add_argument("--submit", action="store_true")
ap.add_argument("--backend", default=None)
args = ap.parse_args()

service = QiskitRuntimeService(channel="ibm_quantum_platform",
                               token=(HERE / ".ibm_key").read_text().strip(), instance=CRN)
cands = service.backends(use_fractional_gates=True, operational=True, simulator=False)
print("Fractional-gate backends:", [(b.name, "rzz" in b.target.operation_names) for b in cands])
cands = [b for b in cands if "rzz" in b.target.operation_names]
if not cands:
    sys.exit("NO-GO: no backend exposes rzz on this instance.")
backend = (next(b for b in cands if b.name == args.backend) if args.backend
           else min(cands, key=lambda b: b.status().pending_jobs))
print("Backend:", backend.name, "| queue:", backend.status().pending_jobs)

# pick disjoint pairs with the lowest reported rzz error
props = backend.target["rzz"]
edges = sorted(((p.error if p and p.error is not None else 1.0, q) for q, p in props.items()))
pairs, used = list(FORCED_PAIRS), {q for p in FORCED_PAIRS for q in p}
for err, (a, b) in edges:
    if len(pairs) >= N_PAIRS: break
    if a in used or b in used:
        continue
    pairs.append((a, b)); used |= {a, b}
    if len(pairs) == N_PAIRS:
        break
print("Pairs:", pairs, "| reported rzz errors:", [round(props[p].error, 5) for p in pairs])

def new_circ():
    qr = QuantumRegister(2 * N_PAIRS); cr = ClassicalRegister(2 * N_PAIRS, "c")
    return QuantumCircuit(qr, cr)

def mirror(theta, depth):
    qc = new_circ()
    for _ in range(depth):
        for i in range(N_PAIRS): qc.rzz(theta, 2 * i, 2 * i + 1)
        qc.barrier()
    for _ in range(depth):
        for i in range(N_PAIRS): qc.x(2 * i)
        for i in range(N_PAIRS): qc.rzz(theta, 2 * i, 2 * i + 1)
        for i in range(N_PAIRS): qc.x(2 * i)
        qc.barrier()
    qc.measure(range(2 * N_PAIRS), range(2 * N_PAIRS))
    return qc

def phase_amp(theta, n, control, basis):
    qc = new_circ()
    for i in range(N_PAIRS):
        if control: qc.x(2 * i)
        qc.h(2 * i + 1)
    qc.barrier()
    for _ in range(n):
        for i in range(N_PAIRS): qc.rzz(theta, 2 * i, 2 * i + 1)
        qc.barrier()
    for i in range(N_PAIRS):
        if basis == "Y": qc.sdg(2 * i + 1)
        qc.h(2 * i + 1)
    qc.measure(range(2 * N_PAIRS), range(2 * N_PAIRS))
    return qc

meta, circs = [], []
for th in ANGLES:
    for d in MIRROR_DEPTHS:
        circs.append(mirror(th, d)); meta.append({"kind": "mirror", "theta": th, "depth": d})
for th in PHASE_ANGLES:
    for n in PHASE_NS:
        for c in (0, 1):
            for bas in ("X", "Y"):
                circs.append(phase_amp(th, n, c, bas))
                meta.append({"kind": "phase", "theta": th, "n": n, "control": c, "basis": bas})

# random order inside the job so calibration drift cannot look like angle dependence
order = np.random.default_rng(SEED).permutation(len(circs))
circs = [circs[k] for k in order]; meta = [meta[k] for k in order]
layout = [q for p in pairs for q in p]
# level 0 + barriers: the transpiler must NOT merge repeated rzz into one gate
isa = transpile(circs, backend, initial_layout=layout, optimization_level=0)
for qc, m in zip(isa, meta):
    ops = qc.count_ops()
    expected = N_PAIRS * (2 * m["depth"] if m["kind"] == "mirror" else m["n"])
    if ops.get("rzz", 0) != expected or any(g in ops for g in ("cz", "ecr", "cx")):
        sys.exit(f"ABORT before submit: {m} -> {dict(ops)} (expected {expected} rzz, no cz/ecr)")
print(f"Transpile check OK: {len(isa)} circuits, all rzz native, nothing merged.")
print(f"Plan: {len(isa)} circuits x {SHOTS} shots = {len(isa) * SHOTS} shots in ONE job.")
print("Sample ops:", dict(isa[2].count_ops()))

if not args.submit:
    print("DRY RUN only. Nothing sent. Re-run with --submit.")
    sys.exit(0)

job = SamplerV2(backend).run(isa, shots=SHOTS)
print("JOB ID:", job.job_id())
out = {"job_id": job.job_id(), "backend": backend.name, "pairs": pairs, "shots": SHOTS,
       "reported_rzz_error": {str(p): props[p].error for p in pairs},
       "submitted": time.strftime("%Y-%m-%dT%H:%M:%S"), "meta": meta}
(HERE / f"sweepM2_{job.job_id()}.json").write_text(json.dumps(out, indent=1))
res = job.result()
out["counts"] = [r.data.c.get_counts() for r in res]
out["usage_seconds"] = job.usage()
out["metrics"] = job.metrics()
(HERE / f"sweepM2_{job.job_id()}.json").write_text(json.dumps(out, indent=1, default=str))
print("QPU seconds billed:", out["usage_seconds"])
print("Saved confirm_%s.json" % job.job_id())
