"""Round 2: fresh calibration of BOTH qubits' local Z phases + delta, then a correction test right after.

Gate model per pair (a=first qubit, b=second):  RZZ(theta+delta) . RZ_a(alpha) . RZ_b(beta)
  target=b: phase with ctrl a=|0> -> N(theta+delta+beta), ctrl |1> -> N(-(theta+delta)+beta)
  sum -> beta (local), difference -> theta+delta.  Swap roles for alpha.
Correction test: |++> -> K x gate -> H H  (K*theta = pi -> '11', 2pi -> '00'); variants:
  raw | local (virtual RZ(-alpha), RZ(-beta) after each gate) | local+delta (also pre-distorted angle)
Two jobs back to back. Default dry run; --submit sends both.
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
from scipy import stats

CRN = "crn:v1:bluemix:public:quantum-computing:us-east:a/ebc0228bd456434081c18bc094bd91e6:576e2f1c-9255-405d-b933-0f01ca671a9f::"
HERE = Path(__file__).parent
BACKEND = "ibm_marrakesh"
PAIRS = [(10, 11), (2, 3), (91, 98), (12, 13), (21, 36), (32, 33), (14, 15)]
TARGETS = {1: 24, 2: 12, 3: 8, 4: 6, 6: 4, 8: 3, 12: 2}      # theta = j*pi/24, K = 24/j
NS = [1, 2, 4, 8, 16]
SHOTS_CAL, SHOTS_TEST = 1000, 2000
SEED = 20261016
P = len(PAIRS)

ap = argparse.ArgumentParser(); ap.add_argument("--submit", action="store_true"); ap.add_argument("--sim", action="store_true"); args = ap.parse_args()
service = QiskitRuntimeService(channel="ibm_quantum_platform",
                               token=(HERE / ".ibm_key").read_text().strip(), instance=CRN)
backend = service.backend(BACKEND, use_fractional_gates=True)
layout = [q for p in PAIRS for q in p]
wrap = lambda x: (x + np.pi) % (2 * np.pi) - np.pi

def regs():
    return QuantumCircuit(QuantumRegister(2 * P), ClassicalRegister(2 * P, "c"))

# ---------- job 1: calibration ----------
def cal_circ(theta, n, orient, ctrl, basis):
    qc = regs()
    for i in range(P):
        c, t = (2 * i, 2 * i + 1) if orient == 0 else (2 * i + 1, 2 * i)
        if ctrl: qc.x(c)
        qc.h(t)
    qc.barrier()
    for _ in range(n):
        for i in range(P): qc.rzz(theta, 2 * i, 2 * i + 1)
        qc.barrier()
    for i in range(P):
        t = 2 * i + 1 if orient == 0 else 2 * i
        if basis == "Y": qc.sdg(t)
        qc.h(t)
    qc.measure(range(2 * P), range(2 * P))
    return qc

cmeta, ccirc = [], []
for j in TARGETS:
    for n in NS:
        for o in (0, 1):
            for c in (0, 1):
                for b in ("X", "Y"):
                    ccirc.append(cal_circ(j * np.pi / 24, n, o, c, b))
                    cmeta.append({"j": j, "n": n, "orient": o, "ctrl": c, "basis": b})
perm = np.random.default_rng(SEED).permutation(len(ccirc))
ccirc = [ccirc[k] for k in perm]; cmeta = [cmeta[k] for k in perm]
cisa = transpile(ccirc, backend, initial_layout=layout, optimization_level=0)
for qc, m in zip(cisa, cmeta):
    ops = qc.count_ops()
    if ops.get("rzz", 0) != P * m["n"] or any(g in ops for g in ("cz", "ecr", "cx")):
        sys.exit(f"ABORT calib: {m} {dict(ops)}")
print(f"Calibration: {len(cisa)} circuits x {SHOTS_CAL} shots, transpile check OK")

# ---------- job 2: correction test (built after calibration) ----------
def test_circ(j, mult, variant, cal):
    K, theta = TARGETS[j] * mult, j * np.pi / 24
    qc = regs(); qc.h(range(2 * P)); qc.barrier()
    for _ in range(K):
        for i, pr in enumerate(PAIRS):
            ang, al, be = theta, 0.0, 0.0
            if variant != "raw":
                c = cal[pr]
                ang = c["inv"][j] if (variant == "local+delta" and c["inv"][j] is not None) else theta
                al, be = np.interp(ang, c["th"], c["alpha"]), np.interp(ang, c["th"], c["beta"])
            qc.rzz(ang, 2 * i, 2 * i + 1)
            if variant != "raw":
                qc.rz(-al, 2 * i); qc.rz(-be, 2 * i + 1)
        qc.barrier()
    qc.h(range(2 * P)); qc.measure(range(2 * P), range(2 * P))
    return qc

VARIANTS = ("raw", "local", "local+delta")
def build_tests(cal):
    meta, circs = [], []
    for j in TARGETS:
        for mult in (1, 2):
            for v in VARIANTS:
                circs.append(test_circ(j, mult, v, cal)); meta.append({"j": j, "mult": mult, "variant": v})
    perm2 = np.random.default_rng(SEED + 1).permutation(len(circs))
    return [circs[k] for k in perm2], [meta[k] for k in perm2]

dummy = {pr: {"th": [0.1, 1.6], "alpha": [0.01, 0.01], "beta": [0.01, 0.01],
              "inv": {j: j * np.pi / 24 for j in TARGETS}} for pr in PAIRS}
tc, tm = build_tests(dummy)
tisa = transpile(tc, backend, initial_layout=layout, optimization_level=0)
for qc, m in zip(tisa, tm):
    ops = qc.count_ops()
    if ops.get("rzz", 0) != P * TARGETS[m["j"]] * m["mult"] or any(g in ops for g in ("cz", "ecr", "cx")):
        sys.exit(f"ABORT test: {m} {dict(ops)}")
print(f"Test: {len(tisa)} circuits x {SHOTS_TEST} shots, transpile check OK (rz stays virtual)")
print(f"Queue on {backend.name}: {backend.status().pending_jobs}")
if not args.submit and not args.sim:
    sys.exit("DRY RUN only.")

class Res:
    def __init__(self, jid, counts, usage): self.jid, self.counts, self.u = jid, counts, usage
    def job_id(self): return self.jid
    def usage(self): return self.u

def distort(qc):
    """Simulation only: inject a known gate error model to validate the pipeline."""
    out = qc.copy_empty_like()
    for ins in qc.data:
        if ins.operation.name == "rzz":
            th = float(ins.operation.params[0]); a, b = ins.qubits
            out.rzz(th + 0.03 * np.sin(2 * th), a, b); out.rz(0.12 * th - 0.05, a); out.rz(-0.08 * th + 0.02, b)
        else:
            out.append(ins)
    return out

def run(circs, shots):
    if args.sim:
        from qiskit_aer import AerSimulator
        sim = AerSimulator(seed_simulator=3)
        res = sim.run([distort(c) for c in circs], shots=shots).result()
        return Res("SIM", [res.get_counts(k) for k in range(len(circs))], 0)
    job = SamplerV2(backend).run(transpile(circs, backend, initial_layout=layout, optimization_level=0), shots=shots)
    print("JOB ID:", job.job_id(), flush=True)
    r = job.result()
    return Res(job.job_id(), [x.data.c.get_counts() for x in r], job.usage())

job1 = run(ccirc, SHOTS_CAL)
counts1 = job1.counts
print("Calibration QPU seconds:", job1.usage(), flush=True)

def ev(cnt, q):
    t = sum(cnt.values()); z = sum(v for k, v in cnt.items() if k[::-1][q] == "0"); return (2 * z - t) / t
def ix(**kw):
    return next(k for k, m in enumerate(cmeta) if all(m[a] == b for a, b in kw.items()))
def unwrap(meas, prior):
    est = prior
    for n, mv in zip(NS, meas):
        pred = 2 * n * est; est = (pred + wrap(mv - pred)) / (2 * n)
    return est

cal = {}
for i, pr in enumerate(PAIRS):
    th = [j * np.pi / 24 for j in TARGETS]; loc = {0: [], 1: []}; tot = {0: [], 1: []}
    for j in TARGETS:
        for o in (0, 1):
            q = 2 * i + 1 if o == 0 else 2 * i
            s_m, d_m = [], []
            for n in NS:
                ph = [np.arctan2(ev(counts1[ix(j=j, n=n, orient=o, ctrl=c, basis="Y")], q),
                                 ev(counts1[ix(j=j, n=n, orient=o, ctrl=c, basis="X")], q)) for c in (0, 1)]
                s_m.append(wrap(ph[0] + ph[1])); d_m.append(wrap(ph[0] - ph[1]))
            loc[o].append(unwrap(s_m, 0.0)); tot[o].append(unwrap(d_m, j * np.pi / 24))
    eff = (np.array(tot[0]) + np.array(tot[1])) / 2              # theta + delta, averaged over orientations
    inv = {}
    for j in TARGETS:
        x = j * np.pi / 24
        inv[j] = float(np.interp(x, eff, th)) if (np.all(np.diff(eff) > 0) and eff[0] <= x <= eff[-1]) else None
    cal[pr] = {"th": th, "alpha": loc[1], "beta": loc[0], "eff": eff.tolist(), "inv": inv}
    print(f"{pr}: alpha={np.round(loc[1], 3).tolist()} beta={np.round(loc[0], 3).tolist()} "
          f"delta={np.round(eff - np.array(th), 3).tolist()}", flush=True)

tc, tm = build_tests(cal)
job2 = run(tc, SHOTS_TEST)
counts2 = job2.counts
print("Test QPU seconds:", job2.usage(), flush=True)

out = {"backend": backend.name, "pairs": PAIRS, "calib_job": job1.job_id(), "test_job": job2.job_id(),
       "cal_meta": cmeta, "cal_counts": counts1, "calibration": {str(k): v for k, v in cal.items()},
       "test_meta": tm, "test_counts": counts2, "usage": [job1.usage(), job2.usage()],
       "finished": time.strftime("%Y-%m-%dT%H:%M:%S")}
(HERE / f"round2_{job2.job_id()}.json").write_text(json.dumps(out, indent=1, default=str))

def pid(cnt, i, ideal):
    t = sum(cnt.values()); return sum(v for k, v in cnt.items() if k[::-1][2 * i] + k[::-1][2 * i + 1] == ideal) / t
def tget(j, mult, v):
    return counts2[next(k for k, m in enumerate(tm) if m["j"] == j and m["mult"] == mult and m["variant"] == v)]
gains = {v: [] for v in VARIANTS[1:]}
for i, pr in enumerate(PAIRS):
    print(f"\n=== {pr}   theta  total   raw    local  local+delta")
    for j in TARGETS:
        for mult in (1, 2):
            ideal = "11" if mult == 1 else "00"
            p = {v: pid(tget(j, mult, v), i, ideal) for v in VARIANTS}
            for v in VARIANTS[1:]: gains[v].append((p["raw"], p[v]))
            print(f"            {j:2d}pi/24 {mult}pi   {p['raw']:.3f}  {p['local']:.3f}  {p['local+delta']:.3f}")
for v, g in gains.items():
    a, b = np.array(g).T
    w = stats.wilcoxon(b, a, alternative="greater")
    print(f"\n{v}: median relative gain {100 * np.median((b - a) / np.maximum(a, 1e-3)):+.1f}% | "
          f"mean abs gain {np.mean(b - a):+.3f} | Wilcoxon one-sided p={w.pvalue:.2e} | n={len(a)}")
print("Saved", f"round2_{job2.job_id()}.json")
