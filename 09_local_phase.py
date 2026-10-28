"""Zero-QPU: from the confirm-run phase data, extract the LOCAL Z phase per gate on the target qubit
(mean of control=0 and control=1 phases), which the differential delta estimate cancels by design."""
import json, sys
import numpy as np
d = json.load(open(sys.argv[1])); meta, counts = d["meta"], d["counts"]
wrap = lambda x: (x + np.pi) % (2 * np.pi) - np.pi
def ev(c, i):
    t = sum(c.values()); z = sum(v for k, v in c.items() if k[::-1][2 * i + 1] == "0"); return (2 * z - t) / t
def idx(**kw):
    return next(k for k, m in enumerate(meta) if all(m.get(a) == b for a, b in kw.items()))
ths = sorted({m["theta"] for m in meta if m["kind"] == "phase"}); Ns = sorted({m["n"] for m in meta if m["kind"] == "phase"})
print("local Z phase per gate on target qubit (rad); pair rows, theta columns")
print("pair      " + "".join(f"{t:7.3f}" for t in ths))
for i, pr in enumerate(d["pairs"]):
    row = []
    for t in ths:
        est = 0.0
        for n in Ns:
            ph = [np.arctan2(ev(counts[idx(kind="phase", theta=t, n=n, control=c, basis="Y")], i),
                             ev(counts[idx(kind="phase", theta=t, n=n, control=c, basis="X")], i)) for c in (0, 1)]
            meas = wrap(ph[0] + ph[1])          # = 2 N * local  (ZZ part cancels)
            pred = 2 * n * est
            est = (pred + wrap(meas - pred)) / (2 * n)
        row.append(est)
    print(f"{str(tuple(pr)):10s}" + "".join(f"{x:+7.3f}" for x in row))
