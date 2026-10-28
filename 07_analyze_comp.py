"""Success probability raw vs corrected, per pair and target angle."""
import json, sys
import numpy as np

d = json.load(open(sys.argv[1]))
pairs, meta, counts, shots = [tuple(p) for p in d["pairs"]], d["meta"], d["counts"], d["shots"]
print(f"Job {d['job_id']} on {d['backend']} | QPU s: {d.get('usage_seconds')}")

def p_ideal(c, i, ideal):
    tot = sum(c.values())
    return sum(v for k, v in c.items() if k[::-1][2 * i] + k[::-1][2 * i + 1] == ideal) / tot

def get(j, mult, corr):
    return counts[next(k for k, m in enumerate(meta) if m["j"] == j and m["mult"] == mult and m["corrected"] == corr)]

js = sorted({m["j"] for m in meta})
gains = []
for i, pr in enumerate(pairs):
    print(f"\n=== pair {pr}")
    print("  theta      total  kind            P(raw)   P(corr)   gain")
    for j in js:
        kind = d["impl"][f"{pr}|{j}"][1]
        for mult in (1, 2):
            ideal = "11" if mult == 1 else "00"
            a, b = p_ideal(get(j, mult, False), i, ideal), p_ideal(get(j, mult, True), i, ideal)
            se = np.sqrt(a * (1 - a) / shots + b * (1 - b) / shots)
            flag = " *" if abs(b - a) > 2.58 * se else ""
            print(f"  {j:2d}pi/24   {mult}pi    {kind:13s}  {a:.3f}    {b:.3f}    {b - a:+.3f}{flag}")
            if kind != "uncorrectable":
                gains.append((pr, j, mult, a, b))

rel = np.array([(b - a) / max(a, 1e-3) for _, _, _, a, b in gains])
print(f"\nAll corrected cases: median relative gain {100 * np.median(rel):+.1f}% over {len(rel)} cases "
      f"(* = |diff| > 2.58 SE, ~p<0.01 each)")
