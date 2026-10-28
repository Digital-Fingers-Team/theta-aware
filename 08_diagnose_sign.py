"""Zero-QPU diagnostic: which model of the true over-rotation explains the compensation-test results?
Predict P(ideal) = A * cos^2(total_error/2) * decay, with true gate angle = x + s*delta(x), s in {+1, -1, 0}."""
import json, sys
import numpy as np
comp = json.load(open(sys.argv[1])); cal = json.load(open(sys.argv[2]))
meta, counts = comp["meta"], comp["counts"]
for i, pr in enumerate([tuple(p) for p in comp["pairs"]]):
    c = cal["pairs"][str(pr)]
    th, dl, et, ep = map(np.array, (c["theta"], c["delta"], c["eps_theta"], c["eps"]))
    obs, rows = [], []
    for k, m in enumerate(meta):
        ideal = "11" if m["mult"] == 1 else "00"
        cnt = counts[k]; tot = sum(cnt.values())
        obs.append(sum(v for b, v in cnt.items() if b[::-1][2 * i] + b[::-1][2 * i + 1] == ideal) / tot)
        ops = comp["impl"][f"{pr}|{m['j']}"][0] if m["corrected"] else [["rzz", m["j"] * np.pi / 24]]
        rows.append((m, ops))
    obs = np.array(obs)
    out = []
    for s in (+1, -1, 0):
        pred = []
        for m, ops in rows:
            K = (24 // m["j"]) * m["mult"]
            per, eps, flip = 0.0, 0.0, 1
            for op in ops:
                if op[0] == "x": flip = -flip; continue
                x = op[1]; per += flip * (x + s * np.interp(x, th, dl)); eps += max(np.interp(x, et, ep), 0)
            err = K * per - m["mult"] * np.pi
            pred.append(np.cos(err / 2) ** 2 * (1 - 16 / 15 * eps) ** K)
        pred = np.array(pred); A = (pred @ obs) / (pred @ pred)
        rmse = np.sqrt(np.mean((A * pred - obs) ** 2))
        out.append(f"s={s:+d}: rmse={rmse:.3f}")
    print(pr, " | ".join(out))
