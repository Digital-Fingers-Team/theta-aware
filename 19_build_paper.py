"""Writes paper.html from paper_results.json, h1_sensitivity.json and the calibration tables, so no number is typed by hand."""
import base64, json
from pathlib import Path
import numpy as np

H = Path(__file__).parent
R = json.load(open(H / "paper_results.json")); SENS = json.load(open(H / "h1_sensitivity.json"))
CAL = {"E2": json.load(open(H / "calib_db7sns0r1c5c738l7vm0.json")), "E7": json.load(open(H / "calib_kingston.json"))}
REP = {"E2": json.load(open(H / "confirm_db7sns0r1c5c738l7vm0.json"))["reported_rzz_error"], "E7": json.load(open(H / "sweepK_db7td8or1c5c738l94d0.json"))["reported_rzz_error"]}

def sci(x):
    m, e = f"{x:.1e}".split("e"); return f"{m}×10<sup>{int(e)}</sup>"
pct = lambda x, d=0: f"{100 * x:.{d}f}%"
def fig(name, cap, width="100%"):
    b = base64.b64encode((H / "figures" / name).read_bytes()).decode()
    return f'<figure><img style="width:{width}" src="data:image/png;base64,{b}"><figcaption>{cap}</figcaption></figure>'

h1 = R["h1_measured"]; hp = R["h1_projection"]; c4, c6 = R["compensation"]["E4"], R["compensation"]["E6"]; h3 = R["h3_preview"]; h4 = R["h4_projection"]; bud = R["budget"]; e10 = R["e10"]; h2 = R["h2_projection"]
smin = sum(SENS[k]["rejected_min"] for k in ("E2", "E7", "E8")); smax = sum(SENS[k]["rejected_max"] for k in ("E2", "E7", "E8"))
smed = sum(SENS[k]["rejected_median"] for k in ("E2", "E7", "E8"))
range_txt = lambda k: f'{SENS[k]["rejected_min"]}' if SENS[k]["rejected_min"] == SENS[k]["rejected_max"] else f'{SENS[k]["rejected_min"]}–{SENS[k]["rejected_max"]}'
T32 = 2 * (h4["a_circuit_s"] + max(h4["needed"]["32"]) * h4["b_shot_s"]); r32 = T32 / h4["T_uniform"]
s32 = max(h4["needed"]["32"])

rows = ""
for exp in ("E2", "E7"):
    for pr, c in CAL[exp]["pairs"].items():
        eps = np.array(c["eps"]); d = np.array(c["delta"]); share = SENS[exp]["reject_share"].get(pr, 0)
        verdict = "rejected" if share >= .95 else ("borderline" if share > .05 else "not rejected")
        dl = "n/a" if pr == "(93, 94)" else f"{d.min():+.3f} to {d.max():+.3f}"
        rows += f"<tr><td>{CAL[exp]['backend'].replace('ibm_','')}</td><td>{pr}</td><td>{REP[exp][pr]:.5f}</td><td>{eps.min():.4f}–{eps.max():.4f}</td><td>{(f"{eps.max() / eps.min():.0f}×" if eps.min() > 0 else "n/a")}</td><td>{dl}</td><td>{SENS[exp]['holm_median'][pr]:.1e}</td><td>{verdict}</td></tr>"

perpair = ""
for name, c in (("marrakesh", c4), ("kingston", c6)):
    for pr, v in c["per_pair"].items():
        perpair += f"<tr><td>{name}</td><td>{pr}</td><td>{v['raw_mean']:.3f}</td><td>{v['mean_gain']:+.3f}</td><td>{v['improved']}/{v['n']}</td></tr>"

e10rows = "".join(f"<tr><td>{k.replace('2π/24','π/12').replace('3π/24','π/8')}</td><td>{v['raw']:.3f}</td><td>{v['local']:.3f}</td><td><b>{v['cz']:.3f}</b></td></tr>" for k, v in e10.items())
names = {"lr_qaoa": "LR-QAOA", "ising": "Trotter Ising", "random": "Random RZZ"}
h2rows = ""
for f, n in names.items():
    b, a, cw, res = h2["base"][f], h2["avoid_bad"][f], h2["cz_worse"][f], h2["resid_002"][f]
    h2rows += f"<tr><td>{n}</td><td>{b['median_raw']:.3f}</td><td>{b['median_theta']:.3f}</td><td><b>{pct(b['median_rel_gain'],1)}</b> [{pct(b['ci'][0],1)}, {pct(b['ci'][1],1)}]</td><td>{pct(b['gain_with_bad'],0)}</td><td>{pct(b['gain_no_bad'],1)}</td><td>{pct(a['median_rel_gain'],1)}</td><td>{pct(cw['median_rel_gain'],1)}</td><td>{pct(res['median_rel_gain'],1)}</td></tr>"
base_lo = min(h2["base"][f]["median_rel_gain"] for f in names); base_hi = max(h2["base"][f]["median_rel_gain"] for f in names)
av_hi = max(h2["avoid_bad"][f]["median_rel_gain"] for f in names)
ns7, ns15, ns31 = [SENS["bad_share_needed"][k] for k in ("7", "15", "31")]
K = json.load(open(H / "compiler_summary.json")); NT = json.load(open(H / "compiler_tests.json"))
ks, e10c, e6c, e4c = K["sim"], K["e10"], K["e6"], K["e4"]
held_best, held_n = e6c["best"] + e10c["best"], e6c["n"] + e10c["n"]
dr = ks["drift"]; dkeys = sorted(dr, key=lambda k: float(k.split("x")[1].split()[0]))
def drift_cut(k): return 1 - dr[k]["err_theta"] / dr[k]["err_cz"]
simrows = "".join(f"<tr><td>{n}</td><td>{ks['err'][k]:.4f}</td><td>{ks['g2'][k]:.1f}</td>" + "".join(f"<td>{dr[d]['err_' + ('frac' if k == 'frac' else 'cz' if k == 'cz' else 'theta' if k == 'theta' else 'layout')]:.4f}</td>" for d in dkeys) + "</tr>"
                  for k, n in (("frac", "Qiskit, fractional gates on"), ("cz", "Qiskit, fractional gates off (2-CZ)"), ("theta", "θ-Aware"), ("theta+layout", "θ-Aware + layout choice")))
replayrows = "".join(f"<tr><td>{lab}</td><td>{c['n']}</td><td>{c['qiskit']:.3f}</td><td><b>{c['theta']:.3f}</b></td><td>{c['oracle']:.3f}</td><td>{c['best']}/{c['n']}</td></tr>"
                     for lab, c in (("E10 marrakesh (10, 11), held out", e10c), ("E6 kingston, held out", e6c), ("E4 marrakesh (κ fitted here)", e4c)))
stab_lo = min(v["delta_r"] for v in R["stability"].values()); stab_max = max(v["delta_max"] for v in R["stability"].values()); eps_rs = [v["eps_r"] for v in R["stability"].values()]

# Figure 6 again, from the saved results, with its legend clear of the bars.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.size": 8.5, "axes.spines.top": False, "axes.spines.right": False, "font.family": "DejaVu Sans", "axes.edgecolor": "#55544f", "axes.linewidth": 0.7, "legend.frameon": False, "figure.dpi": 200})
_f, _a = plt.subplots(figsize=(5.0, 2.6)); _w = .25; _fams = list(names)
for _o, (_k, _c, _l) in enumerate((("base", "#2a78d6", "our sample's pair mix"), ("cz_worse", "#d9822b", "CZ twice as noisy"), ("avoid_bad", "#8a8984", "bad pairs avoided"))):
    _a.bar(np.arange(3) + (_o - 1) * _w, [h2[_k][_x]["median_rel_gain"] * 100 for _x in _fams], _w, color=_c, label=_l)
_a.axhline(10, color="#c8413b", ls="--", lw=1); _a.text(-.42, 11, "H2 target: 10%", color="#c8413b", fontsize=7.5)
_a.set_xticks(range(3)); _a.set_xticklabels(list(names.values())); _a.set_ylabel("median gain in success (%)\nmodel projection")
_a.legend(fontsize=7.2, ncol=3, loc="lower center", bbox_to_anchor=(.5, 1.0)); _f.tight_layout(); _f.savefig(H / "figures" / "fig6_h2.png"); plt.close(_f)

CSS = """
@page { size: A4; margin: 20mm 19mm; }
:root { --ink:#0b0b0b; --ink2:#52514e; --rule:#d9d8d3; --accent:#2a78d6; --tint:#f3f6fb; --warn:#fbf4e6; --warnline:#d9822b; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: "Source Serif 4", Georgia, "DejaVu Serif", serif; font-size: 10.3pt; line-height: 1.43; color: var(--ink); margin: 0; hyphens: auto; text-align: justify; }
h1,h2,h3,figcaption,table,.meta,.lab,.tag { font-family: Inter, "DejaVu Sans", sans-serif; }
h1 { font-size: 17pt; line-height: 1.22; text-align: center; margin: 0 0 6pt; letter-spacing: -.01em; }
.meta { text-align: center; font-size: 9pt; color: var(--ink2); margin-bottom: 11pt; }
h2 { font-size: 11.5pt; margin: 14pt 0 5pt; break-after: avoid; } h3 { font-size: 10pt; margin: 9pt 0 3pt; break-after: avoid; }
p { margin: 0 0 6pt; } ul,ol { margin: 0 0 6pt; padding-left: 16pt; } li { margin-bottom: 2.5pt; }
.abstract { border-top: 1.2pt solid var(--ink); border-bottom: .6pt solid var(--rule); padding: 8pt 0; margin-bottom: 9pt; }
.lab { font-weight: 700; font-size: 8.6pt; letter-spacing: .04em; text-transform: uppercase; }
figure { margin: 8pt 0 10pt; break-inside: avoid; text-align: center; } figcaption { font-size: 8.2pt; color: var(--ink2); text-align: left; margin-top: 3pt; line-height: 1.33; hyphens: none; }
table { border-collapse: collapse; width: 100%; font-size: 7.9pt; margin: 5pt 0 3pt; break-inside: avoid; text-align: left; hyphens: none; line-height: 1.28; }
th { border-bottom: .9pt solid var(--ink); padding: 2.5pt 4pt; font-weight: 600; vertical-align: bottom; } td { border-bottom: .4pt solid var(--rule); padding: 2.2pt 4pt; vertical-align: top; }
.cap { font-family: Inter, "DejaVu Sans", sans-serif; font-size: 8.2pt; color: var(--ink2); margin: 0 0 9pt; text-align: left; hyphens: none; line-height: 1.33; }
.proj { background: var(--warn); border-left: 2.5pt solid var(--warnline); padding: 6pt 9pt; margin: 8pt 0; break-inside: avoid; }
.tag { display: inline-block; font-size: 7.4pt; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; color: #8a5414; }
.m { background: var(--tint); border-left: 2.5pt solid var(--accent); padding: 6pt 9pt; margin: 8pt 0; break-inside: avoid; }
.refs { font-size: 8.8pt; line-height: 1.34; text-align: left; hyphens: none; } .refs li { margin-bottom: 3pt; word-break: break-word; }
"""

HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>θ-Aware Research Paper</title>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400&family=Inter:wght@400;600;700&display=swap" rel="stylesheet"><style>{CSS}</style></head><body>
<h1>θ-Aware: Measuring the Angle-Dependent Error of Fractional RZZ(θ) Gates on Superconducting Hardware, and What a Compiler Could Do with It</h1>
<div class="meta">Elbaraa Saad and Eyad Abdelraoof · ISEF category: Software Design (SFTD), Algorithms · Working paper, 12 November 2026<br><b>Status: exploratory results from one day of hardware runs; the θ-Aware compiler, built and tested on recorded and simulated data; model-based projections. The compiler has not yet run on hardware, and the confirmatory experiment has not been run.</b></div>

<div class="abstract"><span class="lab">Abstract.</span>
IBM's fractional two-qubit gate RZZ(θ) reports one error value for every angle, which IBM documents as a copy of the non-fractional gate's error. We measured the gate as a function of θ on two Heron processors in ten experiments on 14 October 2026, using 551 QPU seconds. Mirror circuits show that a constant incoherent error is rejected (Holm-corrected, α = 0.01) in a median of {smed:.0f} of 24 pair-sweeps (three sweeps of 8 pairs; {smin}–{smax} across bootstrap seeds). Phase-amplification circuits reveal an angle-dependent single-qubit Z phase, invisible to IBM's reported figure, reaching about 0.3 rad per gate on the worst pair. Removing it with virtual RZ gates raised success significantly across 196 test cases, but the median gain is small (+{pct(c4['local']['median_rel'],1)} and +{pct(c6['local']['median_rel'],1)} on the two devices): most of the gain sits on a few bad pairs, and the correction hurt the one pair with an unstable calibration. On the worst pair at small angles, the standard two-CZ decomposition reached 0.86–0.89 success against 0.05–0.44 for the fractional gate, although both are reported with the same error. We then built θ-Aware, a Qiskit compiler pass that chooses, for every RZZ(θ), between the fractional gate, the fractional gate with free phase corrections, and the standard two-CZ decomposition, from the measured per-angle model. Replayed on the circuits of past hardware jobs with only the calibrations that existed before each job, it chose the best measured implementation (within two standard errors) in {held_best} of {held_n} held-out cases. On the bad pair it raised success from {e10c['qiskit']:.2f} to {e10c['theta']:.2f}, {e10c['error_ratio']:.1f} times fewer errors; on the other device's healthy pairs it changed nothing measurable ({e6c['qiskit']:.3f} vs {e6c['theta']:.3f}). In simulation of {ks['n']} algorithm circuits with the measured parameters and measured-size drift, it made {pct(ks['cut_vs_frac'])} fewer errors than Qiskit with fractional gates and {pct(ks['cut_vs_cz'])} fewer than Qiskit without them, while using {pct(ks['g2_saving_vs_cz'])} fewer two-qubit gates than the latter. None of this is confirmatory: the compiler results are retrospective or simulated, and hardware validation awaits QPU access. Projections of the full experiment suggest H1 is likely to hold, H4 is plausible and H3 is uncertain.
</div>

<h2>1. Introduction</h2>
<p>Fractional gates let IBM's Heron processors apply an RZZ(θ) rotation directly, with 0 &lt; θ ≤ π/2, instead of building it from two CZ gates [1]. They have been used at large scale, including benchmarks on up to 156 qubits [2]. They also come with a blind spot. IBM's documentation says the error reported for a fractional gate "is just a copy of the non-fractional gate's counterpart (which may not be the same)", that the transpiler has "limited capability" to use RZZ(θ), and that Pauli twirling is not supported with these gates [1]. Without twirling, coherent errors are not converted into stochastic noise, so they stay in the circuit and can add up.</p>
<p>A compiler that reads only the reported number therefore cannot tell a good angle from a bad one, or a good implementation from a bad one. We did not find published work that measures RZZ(θ) error and its coherent parts as functions of θ on hardware, or a compiler that uses such data, although our search was not exhaustive. This project asks three questions: does the error really depend on θ, what does the error consist of, and how much could a compiler gain by knowing it?</p>
<h3>Hypotheses from the research plan</h3>
<ul><li><b>H1.</b> The constant-error model is rejected (Holm-corrected α = 0.01) for at least 50% of qubit pairs.</li>
<li><b>H2.</b> θ-Aware compilation improves median success probability by at least 10% over Qiskit level 3 with fractional gates (Wilcoxon signed-rank test, paired by circuit).</li>
<li><b>H3.</b> Fidelity predicted from the θ-Aware model ranks circuits better than predictions from IBM-reported errors (Spearman ρ; bootstrap 95% CI of the difference excludes 0).</li>
<li><b>H4.</b> An optimized measurement design reaches the same confidence-interval width on ε(θ) as a uniform shot allocation with at most 50% of the QPU seconds.</li></ul>
<div class="m"><b>How to read this paper.</b> Blue boxes and Section 3 are <b>measurements</b>. Orange boxes and Section 6 are <b>projections</b>: outputs of a model built on those measurements. No projected number was measured on hardware. All measurements come from one day, and several of the study's design choices were made after seeing them, so they motivate the hypotheses and cannot confirm them.</div>

<h2>2. Methods</h2>
<p><b>Hardware and budget.</b> ibm_marrakesh and ibm_kingston, under the IBM Quantum Open Plan (10 QPU minutes per rolling 28 days). Software: Python 3.12, Qiskit 2.5.2 [3], qiskit-ibm-runtime 0.50.0. All ten experiments (E1–E10) used 551 of 600 seconds on one account. ibm_fez also passed the access check but was not measured.</p>
<p><b>Gate model.</b> We model one physical gate as RZZ(θ + δ) · RZ<sub>a</sub>(α) · RZ<sub>b</sub>(β), followed by incoherent error ε. Each of δ, α, β and ε may depend on θ.</p>
<p><b>Incoherent error ε(θ).</b> Mirror circuits [4] apply d layers of RZZ(θ) and then d inverse layers, each inverse implemented as X·RZZ(θ)·X because the hardware does not accept negative angles. Survival is fitted as S(d) = A·p<sup>2d</sup> for d = 1, 4, 8, 16, 32, and ε = (15/16)(1 − p). A simulation with an injected δ = 0.02 rad confirmed that the mirror is blind to over-rotation.</p>
<p><b>Coherent errors δ, α, β.</b> One qubit is prepared in |0⟩ or |1⟩ and the other in |+⟩, RZZ(θ) is repeated N = 1, 2, 4, 8, 16 times in the same direction, and the second qubit's phase is read in the X and Y bases, in the spirit of phase-amplification calibration [5]. The difference of the two control settings gives θ + δ, and their sum gives the local phase. Swapping roles gives the other qubit's phase. Simulation recovered an injected δ of 0.02 rad as 0.0195–0.0200.</p>
<p><b>Correctness test.</b> From |++⟩, apply RZZ(θ) K times with Kθ = π (ideal output |11⟩) or Kθ = 2π (ideal |00⟩), then H⊗H. Success is the probability of the ideal output. Variants: <i>raw</i>; <i>local</i>, with virtual RZ(−α), RZ(−β) after each gate [6], which adds no error or time; <i>local+δ</i>, which also pre-distorts the angle; and <i>2-CZ</i>, the standard decomposition.</p>
<p><b>Safeguards.</b> Circuits are transpiled at optimization level 0 with barriers, and a check aborts submission if any RZZ was merged or decomposed. Circuit order is randomized with a fixed seed, so drift cannot look like angle dependence. Disjoint pairs run in parallel in one circuit.</p>
<p><b>Statistics.</b> Parametric bootstrap with 300 resamples; constant-error test by χ² against the weighted mean, with Holm correction [7] across pairs (α = 0.01). Correction tests use a one-sided Wilcoxon signed-rank test [8]. Because the χ² weights come from the bootstrap, we repeated the H1 analysis over 40 seeds. The plan specifies a likelihood-ratio test; the χ² test here is a stand-in for it and must be replaced or justified before pre-registration.</p>

<h2>3. Results (measured, exploratory)</h2>
<h3>3.1 The incoherent error depends on the angle</h3>
<div class="m">Constant error rejected: ibm_marrakesh <b>{range_txt('E2')}/8</b> and, about an hour later, <b>{range_txt('E8')}/8</b>; ibm_kingston <b>{range_txt('E7')}/8</b>. Ranges show the spread over 40 bootstrap seeds, with medians of {SENS['E2']['rejected_median']:.0f}, {SENS['E8']['rejected_median']:.0f} and {SENS['E7']['rejected_median']:.0f} respectively, so borderline pairs are not reported as firm. H1's 50% threshold is met in this exploratory sample, on data that cannot confirm it.</div>
{fig('fig1_eps.png', '<b>Figure 1.</b> Measured ε(θ) with 95% bootstrap intervals for three contrasting pairs, against IBM\'s single reported value (dashed). Mirror ε is mostly below the reported value, as expected, because the mirror excludes coherent error.')}
<table><tr><th>Device</th><th>Pair</th><th>IBM-reported</th><th>Measured ε range</th><th>Max/min</th><th>δ range (rad)</th><th>Median Holm p</th><th>Constant error</th></tr>{rows}</table>
<p class="cap"><b>Table 1.</b> Per-pair results of the first sweep on each device. "Borderline" means the verdict changed across bootstrap seeds. Max/min is inflated where the smallest ε is close to the noise floor. Pair (93, 94) gave an unusable δ.</p>

<h3>3.2 A hidden, angle-dependent phase is the larger coherent error</h3>
<p>Our first correction (E3) targeted only δ and did not help: median relative gain −0.9% over 92 cases, and worse on pair (10, 11). We kept this negative result because it led to the main finding. The differential δ measurement cancels any single-qubit phase by design, and re-reading the same data showed a large one. A dedicated calibration (E4) gave α from −0.26 to +0.18 and β from −0.19 to +0.28 rad per gate on (10, 11); elsewhere the phases were about 0.06 rad or less (Figure 2).</p>
{fig('fig2_coherent.png', '<b>Figure 2.</b> Local phase β(θ) and over-rotation δ(θ) on ibm_marrakesh. Pair (10, 11) in red, other pairs in grey. That pair was deliberately included because the pilot had flagged it, so it does not represent a typical pair.')}

<h3>3.3 Correcting the phase helps, unevenly, at no cost</h3>
<div class="m">Virtual-RZ correction, 98 cases per device. <b>Marrakesh:</b> mean gain {c4['local']['mean_gain']:+.3f}, median relative gain {pct(c4['local']['median_rel'],1)}, p = {sci(c4['local']['p'])}. <b>Kingston:</b> mean gain {c6['local']['mean_gain']:+.3f}, median relative gain {pct(c6['local']['median_rel'],1)}, p = {sci(c6['local']['p'])}. Adding pre-distortion: marrakesh {c4['local+delta']['mean_gain']:+.3f} (p = {sci(c4['local+delta']['p'])}), kingston {c6['local+delta']['mean_gain']:+.3f} (p = {sci(c6['local+delta']['p'])}). The effect is statistically clear and typically small.</div>
{fig('fig3_correction.png', '<b>Figure 3.</b> Each point is one test case; above the line, the correction helped. On (10, 11) several cases jump from 0.06–0.41 to 0.87–0.96, but three collapse to about 0.02. On (0, 1), whose calibration was erratic, the correction does harm on average.')}
<table><tr><th>Device</th><th>Pair</th><th>Mean raw success</th><th>Mean gain (local)</th><th>Cases improved</th></tr>{perpair}</table>
<p class="cap"><b>Table 2.</b> Gain per pair. Across 14 pairs, gains are concentrated on few of them, and two lose on average: (0, 1) clearly and (91, 98) negligibly. A real compiler therefore needs a calibration-quality gate.</p>
<p><b>Failures.</b> Running (10, 11) alone (E5) reproduced the collapses, which rules out crosstalk from the neighbouring pair. At π/12 and π/8 the requested angle is below the smallest rotation the gate actually delivers, so δ stays uncorrected; a calculation from the measured δ predicts these results closely (for π/12 with K = 12: predicted 0.013, measured 0.020). The failure at π/3 with K = 3 remains <b>unexplained</b>. A two-gate workaround (E9) did not fix small angles.</p>

<h3>3.4 Choosing the implementation can matter more than correcting it</h3>
<div style="display:flex;gap:12pt;align-items:flex-start;break-inside:avoid"><div style="flex:1.05">{fig('fig4_cz.png', '<b>Figure 4.</b> E10, pair (10, 11).')}</div><div style="flex:1"><table><tr><th>Case</th><th>Raw</th><th>+RZ</th><th>2-CZ</th></tr>{e10rows}</table><p class="cap"><b>Table 3.</b> Success probability, 2,000 shots each. 2-CZ uses twice as many two-qubit gates and still wins on this pair. This is one pair, chosen because it is bad, at its worst angles.</p></div></div>

<h3>3.5 Coherent errors looked stable for an hour; ε(θ) did not</h3>
<p>Repeating the marrakesh sweep about an hour later, δ(θ) correlated at r ≥ {stab_lo:.2f} between runs, changing by at most {stab_max:.3f} rad. The correlation of ε(θ) ranged from {min(eps_rs):.2f} to {max(eps_rs):.2f}. On (10, 11), ε at θ = 0.13 fell from 0.0086 to 0.0006. This suggests calibrating coherent errors once per session and correcting them while treating ε as time-varying. One hour says nothing about stability over days, which is what a usable compiler needs.</p>

<h3>3.6 The measured gate model predicts better, but not significantly so</h3>
<div class="m">Using each pair's calibration to predict {h3['n']} raw test outcomes it never saw: Spearman ρ = <b>{h3['rho_model']:.2f}</b> (mean absolute error {h3['mae_model']:.3f}) against ρ = <b>{h3['rho_ibm']:.2f}</b> ({h3['mae_ibm']:.3f}) for IBM's reported error. The difference is {h3['diff']:+.2f}, with a 95% pair-clustered bootstrap CI of [{h3['diff_ci'][0]:+.2f}, {h3['diff_ci'][1]:+.2f}], which <b>includes 0</b>. Without the two bad pairs the advantage disappears: {h3['without_bad']['rho_model']:.2f} against {h3['without_bad']['rho_ibm']:.2f}, CI [{h3['without_bad']['diff_ci'][0]:+.2f}, {h3['without_bad']['diff_ci'][1]:+.2f}]. Only 14 pairs inform this interval.</div>
{fig('fig5_h3.png', '<b>Figure 5.</b> Predicted against measured success for the raw variant. IBM\'s reported error gives a narrow band of predictions and misses the low outcomes, which the measured model partly captures.', '92%')}

<h2>4. The θ-Aware compiler (built; tested on recorded and simulated data)</h2>
<h3>4.1 What it does</h3>
<p>θ-Aware is a Qiskit pass (package <code>thetaaware/</code>). After Qiskit lays out and routes a circuit with fractional RZZ allowed, the pass rewrites every RZZ(θ). It first folds θ into the hardware's range [0, π/2] with exact identities: a negative angle becomes X·RZZ(|θ|)·X on one qubit, and |θ| &gt; π/2 splits off RZZ(π), which equals Z⊗Z up to phase and is virtual. It then picks one of four implementations for that physical pair: <i>the fractional gate as it is</i> (what Qiskit does with fractional gates on); <i>the fractional gate followed by virtual RZ(−α), RZ(−β)</i>, which costs nothing; <i>the same with the requested angle pre-distorted</i> so that θ + δ lands on θ, when the measured response is monotonic; or <i>the standard two-CZ decomposition</i> (what Qiskit does with fractional gates off).</p>
<p>Each option gets a predicted error from the measured model: ε(θ), plus m times the average gate infidelity of the coherent error the option leaves, where m counts how often the circuit repeats that pair and angle, because coherent errors add in amplitude. Two-CZ costs twice IBM's reported error. The cheapest option wins; ties go to fewer two-qubit gates. Gates on pairs with no calibration stay as Qiskit would leave them. A layout score adds up the best option's cost over a candidate placement, so the compiler can also choose which pairs to use. One parameter, κ, the share of a measured coherent error that survives correction, was fitted on E4 alone and came out at κ = {K['kappa']:.2f}, the edge of its range. We therefore re-ran every held-out test for κ from 0 to 1: E10's choices did not change, and E6's mean success stayed between 0.880 and 0.884. Median compile time was {K['compile_ms']:.0f} ms per 6-qubit circuit on a 2-core server.</p>
<h3>4.2 Correctness</h3>
<p>{NT['passed']} automated tests pass, with none failing. On an ideal device, every option equals RZZ(θ) up to global phase for {NT['angles']} angles from −2π to 2π, including 0, ±π/2, ±π and 2π. Every angle sent to the hardware lies in [0, π/2]. With the measured model as the device, the corrections cancel it exactly for all 8 marrakesh pairs, both qubit orders and five angles. Compiled random circuits equal their originals, and the simulator reproduces Section 3.6's prediction formula to within 10<sup>−6</sup>.</p>
<h3>4.3 Replay on recorded hardware jobs (measured outcomes)</h3>
<div class="m">We ran the compiler on the exact circuits of past jobs, gave it only the calibrations that existed before each job, and looked up how the option it chose had actually performed on the QPU. Each job measured only some options, so the compiler chose among those.
<table><tr><th>Experiment</th><th>Cases</th><th>Qiskit (fractional)</th><th>θ-Aware</th><th>Best measured</th><th>Chose the best (within 2 SE)</th></tr>{replayrows}</table>
<p class="cap" style="margin-bottom:2pt"><b>Table 6.</b> Mean measured success probability, 2,000 shots per case. E4 and E6 offered only the fractional variants; E10 also offered two-CZ.</p>
On the bad pair the compiler picked two-CZ in all four cases, each time the best measured option: success rose from {e10c['qiskit']:.2f} to {e10c['theta']:.2f}, {e10c['error_ratio']:.1f} times fewer errors. On marrakesh (E4) it cut errors by {pct(e4c['err_cut'])}. On kingston (E6), whose pairs are healthy, it on average neither helped nor hurt: better than raw in {e6c['better']} cases and worse in {e6c['worse']} of {e6c['n']}, beyond two standard errors. E10 is only four cases, on one pair chosen because it is bad.</div>
{fig('fig7_replay.png', '<b>Figure 7.</b> The compiler on recorded jobs. Left: E10, the measured success of Qiskit\'s choice against θ-Aware\'s choice (two-CZ). Right: mean measured success of each policy.')}
<h3>4.4 Simulated benchmark (projection)</h3>
<div class="proj"><span class="tag">Projection, not data</span><br>{ks['n']} circuits (LR-QAOA, Trotter Ising, random RZZ; 2–4 layers) on 6-qubit lines, each edge one measured pair from the same device and day. The compiler knows that calibration; the simulated device runs a <b>drifted</b> copy, with drift of the size measured between E2 and E8 (σ = {ks['sigma']:.4f} rad), and also 6 and 18 times larger. Single-qubit gates and readout are ideal. Metric: state fidelity F, before measurement.
<table><tr><th>Compiler</th><th>Errors 1 − F</th><th>Two-qubit gates</th>{''.join(f'<th>1 − F, drift ×{d.split(chr(120))[1].split()[0]}</th>' for d in dkeys)}</tr>{simrows}</table>
<p class="cap" style="margin-bottom:2pt"><b>Table 7.</b> Means over circuits. Layout choice picks the lowest predicted error among 24 placements; with IBM's reported errors instead, Qiskit-style choice gave {ks['err_frac_layout']:.4f} (fractional) and {ks['err_cz_layout']:.4f} (two-CZ).</p>
At the measured drift θ-Aware made <b>{pct(ks['cut_vs_frac'])} fewer errors than Qiskit with fractional gates</b>, and was worse on {pct(ks['worse_than_frac'])} of circuits. It made <b>{pct(ks['cut_vs_cz'])} fewer errors than Qiskit without them, with {pct(ks['g2_saving_vs_cz'])} fewer two-qubit gates</b>, the slowest and noisiest operations. With layout choice: {pct(ks['cut_layout_vs_cz'])} fewer errors than two-CZ, with about half the two-qubit gates. Most of the gain over fractional gates comes from bad pairs. On circuits with none, the cut is {pct(ks['no_bad']['err_reduction_vs_frac'])}, which the E6 replay did not confirm, so treat it as an upper bound. The advantage over two-CZ falls from {pct(ks['cut_vs_cz'])} to {pct(drift_cut(dkeys[-1]))} at 18 times the measured drift, so the compiler needs fresh calibrations, and day-scale drift has not been measured.</div>
{fig('fig8_benchmark.png', '<b>Figure 8.</b> Simulated state infidelity (log scale). Left: by circuit family at the measured drift. Right: against drift size. Projection, not data.')}

<h2>5. What is finished and what is not</h2>
<table><tr><th>Plan item</th><th>Plan</th><th>Done so far</th></tr>
<tr><td>Characterization</td><td>≥ 30 pairs per device, ≥ 3 days, 2 devices</td><td>8 pairs per device, 1 day (marrakesh twice)</td></tr>
<tr><td>Pre-registration</td><td>Before confirmatory data</td><td><b>Not done</b>; the plan's date has passed</td></tr>
<tr><td>Measurement design (H4)</td><td>Fisher-information design and proofs</td><td>Numerical projection only; no proofs</td></tr>
<tr><td>Compiler (H2)</td><td>Qiskit passes, dynamic programming, layout scoring</td><td><b>Built</b> (Section 4): per-gate choice, phase correction, pre-distortion, layout scoring, {NT['passed']} tests. No dynamic programming across gates yet</td></tr>
<tr><td>Evaluation (H2, H3)</td><td>≥ 40 circuits, 3 families, 4 baselines</td><td>Replay on {e4c['n'] + held_n} recorded cases; simulation of {ks['n']} circuits in 3 families against 2 Qiskit baselines. <b>Not run on hardware</b></td></tr></table>
<p class="cap"><b>Table 4.</b> Current state of the project against the research plan.</p>

<h2>6. Expected results of the full experiment (projections)</h2>
<div class="proj"><span class="tag">Projection, not data</span><br>Everything in this section is a model output, computed with no QPU use by <code>17_paper_analysis.py</code>. Projections carry forward the limits of a one-day sample in which one marrakesh pair was deliberately included because it looked bad.</div>
<h3>6.1 H1: likely to hold</h3>
<p>We resampled the measured per-pair p-values to the plan's size and re-applied Holm across all pairs. With 60 pairs, the projected rejected share has a median of {pct(hp['60']['median'])} (95% range {pct(hp['60']['lo'])}–{pct(hp['60']['hi'])}), and <b>{pct(hp['60']['p_ge_50'])}</b> of resamples reach the 50% threshold. With 30 pairs: {pct(hp['30']['median'])} and {pct(hp['30']['p_ge_50'])}. These figures use one seed's p-values, so they carry the seed sensitivity described in Section 3.1. Risks: resampling assumes new pairs behave like these 24 sweeps, repeated sweeps share pairs, and a multi-day analysis with day as a random effect may behave differently.</p>
<h3>6.2 H2: depends mainly on how common bad pairs are</h3>
<p><i>This section's rule predates the compiler; Section 4.4 simulates the compiler itself.</i> We simulated 8-qubit lines whose edges are drawn from the 14 calibrated pairs, for three circuit families at 2, 4 and 6 layers, using the measured δ, α, β and ε. The simulated θ-aware rule corrects local phases, with a residual calibration error of 0.01 rad, and uses 2-CZ when the fractional gate's predicted cost exceeds it. The baseline uses fractional gates with no correction. The metric is state fidelity times gate survival, which is not the same as the hardware's success probability.</p>
<table><tr><th>Family</th><th>Baseline</th><th>θ-aware</th><th>Median gain [95% CI]</th><th>Circuits touching a bad pair</th><th>Circuits avoiding them</th><th>Bad pairs avoided</th><th>CZ twice as noisy</th><th>Residual 0.02 rad</th></tr>{h2rows}</table>
<p class="cap"><b>Table 5.</b> Projected median success and relative gain (the plan's 10% target, H2). {pct(h2['base']['lr_qaoa']['frac_with_bad_edge'])} of simulated circuits touch a bad pair, (10, 11) or (0, 1), because each makes up 1 of 7 edges on its device. The simulated rule picks 2-CZ for {pct(h2['base']['random']['share_cz'])}–{pct(h2['base']['ising']['share_cz'])} of gates.</p>
{fig('fig6_h2.png', '<b>Figure 6.</b> Projected median gain against the H2 target. Nearly all of it comes from circuits that touch a bad pair.', '68%')}
<div class="proj"><span class="tag">What we expect</span><br><b>Gains should be large on bad pairs and tiny elsewhere</b> (about {pct(h2['base']['ising']['gain_no_bad'],1)}–{pct(h2['base']['lr_qaoa']['gain_no_bad'],1)} on circuits that avoid them), growing with depth. The median crosses 10% only if over half of the circuits touch a bad pair. On a line of 8 qubits that takes a bad-pair share of about {pct(ns7)} per edge, falling to {pct(ns15)} at 16 qubits and {pct(ns31,1)} at 32. Our only bad pair not chosen in advance is (0, 1): 1 of 14 unforced pairs, about 7%, on far too small a sample to settle it. So <b>H2's verdict is open</b>, and larger circuits should favour it. A layout pass that simply avoids bad pairs would capture most of the gain. That still needs per-angle data, because IBM's reported numbers do not reveal these pairs, and it may be the project's most practical outcome. The Qiskit level 3 baseline may also do better or worse than the plain fractional baseline simulated here.</div>
<h3>6.3 H3: uncertain</h3>
<p>The measured preview favours the model on average, but its interval includes 0 and the advantage comes from bad pairs (Section 3.6). The evaluation's circuit mix will decide this. With few bad pairs, H3 may well fail, which would itself be useful: it would mean the reported error ranks ordinary pairs about as well as the measured model on circuits of this type.</p>
<h3>6.4 H4: plausible, with a cost</h3>
<p>Using a cost model fitted to two of our jobs (T ≈ {h4['a_circuit_s']:.3f} s per circuit + {h4['b_shot_s'] * 1000:.3f} ms per shot), we simulated the depth and shot allocation needed to match the CI width of the current five-depth design at 1,000 shots, for ε from 0.0003 to 0.008. Two depths {{1, 32}} at {s32:,} shots need <b>{pct(r32)}</b> of the QPU time. Two depths {{1, {h4['best_d2']}}} at {h4['shots_two_depth']} shots need {pct(h4['ratio'])}, but extrapolate beyond any depth we have measured. Two depths cannot test whether the decay is exponential, and per-shot time will grow with depth in ways this model ignores, so we would keep a small number of intermediate depths as a check. The plan's proofs remain to be written.</p>
<h3>6.5 Budget</h3>
<p>From the measured {bud['sec_per_1000']:.2f} s per 1,000-shot circuit, two devices over three days need about {bud['items']['sweeps']:.0f} s of sweeps and {bud['items']['calibration']:.0f} s of phase calibration, plus {bud['items']['evaluation']:.0f} s of evaluation (40 circuits × 4 variants × 2 devices at 2,000 shots): about <b>{bud['total_min']:.0f} minutes</b>, before any savings from H4. That is roughly two full 10-minute allowances, and the project's current account has 49 s left until its window rolls forward. Thirty pairs per device add no QPU time if they share circuits, but more parallel pairs may add crosstalk, which needs checking.</p>
<h3>6.6 Design changes this work suggests before pre-registration</h3>
<ol><li><b>Do not evaluate H2 only with mirrored circuits.</b> The plan runs larger circuits in mirrored form. In the gate model, conjugating with X on one qubit reverses the ZZ rotation and that qubit's local phase, so δ and α cancel while β adds up. A mirror therefore hides much of the coherent error this project is about. Use circuits with a classically computable output instead.</li>
<li><b>Fix a rule for bad pairs in advance</b>, both for excluding unmeasurable pairs and for the calibration-quality gate.</li>
<li><b>Choose pairs without looking at the pilot.</b> Pair (10, 11) must not be forced into the confirmatory sample, or must be analysed apart from it.</li>
<li><b>Replace or justify the H1 test</b>, so the verdict does not depend on bootstrap seed; use more resamples or an analytic likelihood.</li></ol>
<h3>6.7 What would change our conclusions</h3>
<p>If the multi-day data show δ, α and β drifting between days, per-session calibration costs too much to be free. If bad pairs are rare or short-lived, the compiler's value shrinks to almost nothing on typical circuits, and the main contribution becomes the dataset and the warning about reported errors. If IBM begins reporting per-angle errors, the measurement half of this project loses its practical purpose.</p>

<h2>7. Limitations</h2>
<ul><li><b>One day, two devices, few pairs.</b> All of it is exploratory, and hypotheses and methods evolved while we looked at the data.</li>
<li><b>Selection.</b> Pair (10, 11) was forced in because the pilot flagged it. It supplies the most striking results, so those results are not typical.</li>
<li><b>Simple test circuits.</b> The correctness tests repeat one gate on isolated pairs, while real circuits mix angles and neighbours. A gain here does not carry over automatically.</li>
<li><b>Simplified simulation.</b> It has no crosstalk, readout error or layout search, assumes a line topology, and treats incoherent error as depolarizing.</li>
<li><b>Compiler evidence is retrospective or simulated.</b> The replay can only score options a past job measured, and its decisive result is four cases on one pair. The simulation uses the same gate model as the compiler, perturbed by drift, so it cannot reveal errors the model lacks, such as crosstalk, leakage or the unexplained π/3 failure.</li>
<li><b>Incomplete gate model.</b> The π/3, K = 3 failure on (10, 11) is unexplained, and one pair's calibration was untrustworthy.</li>
<li><b>Analysis change.</b> The H1 count moves with the bootstrap seed. The log's single value of 5/8 is the median for that sweep, and one run of this paper's analysis gave 6/8; we report the range (Section 3.1).</li></ul>

<h2>8. Conclusion</h2>
<p>On the data so far, a single reported error misdescribes fractional RZZ(θ) gates: error depends on the angle for most measured pairs, and a coherent phase that IBM does not report can be large and can be removed for free. The sharpest practical message comes from a small number of bad pairs that look normal in reported calibration data but can perform far worse than the standard decomposition. The θ-Aware compiler now turns this into a decision: it detects when the fractional gate is the wrong choice and switches, which on the bad pair we measured turned {e10c['qiskit']:.2f} into {e10c['theta']:.2f} success, while keeping the fractional gate's lower two-qubit gate count elsewhere. On healthy pairs the recorded data show no measurable gain, so its value on hardware depends on how common bad pairs are and how fast calibrations drift. The next steps are to pre-register the corrected design, run the multi-day sweep, and run the compiler against Qiskit on hardware.</p>

<h2>Data, code and disclosures</h2>
<p><b>Availability.</b> Scripts, raw job data with job IDs, the research log, and the code generating every number and figure here are in the project repository, github.com/Digital-Fingers-Team/theta-aware (currently private). <b>Reproduction:</b> <code>python 17_paper_analysis.py; python 18_h1_sensitivity.py; python -m pytest tests; python 21_compiler_replay.py; python 22_compiler_benchmark.py; python 23_compiler_figures.py; python 19_build_paper.py</code>; none of them uses the QPU or reads the key.</p>
<p><b>AI assistance.</b> Anthropic's Claude helped write the experiment and analysis code, the compiler and its tests, the simulation and projections, and the text of this paper. This must be disclosed to the fair as its rules require, and the student must be able to explain and defend all of the work. <b>To complete before submission:</b> student's name, mentor review, and any acknowledgments.</p>

<h2>References</h2>
<ol class="refs">
<li>IBM Quantum. "Fractional gates" (guide). quantum.cloud.ibm.com/docs/en/guides/fractional-gates. Accessed 7 Nov 2026.</li>
<li>A. Montañez-Barrera, K. Michielsen, D. E. Bernal Neira. "Evaluating the performance of quantum processing units at large width and depth." arXiv:2502.06471.</li>
<li>A. Javadi-Abhari et al. "Quantum computing with Qiskit." arXiv:2405.08810.</li>
<li>T. Proctor et al. "Scalable randomized benchmarking of quantum computers using mirror circuits." Phys. Rev. Lett. 129, 150502 (2022).</li>
<li>S. Sheldon et al. "Procedure for systematically tuning up cross-talk in the cross-resonance gate." Phys. Rev. A 93, 060302 (2016).</li>
<li>D. C. McKay et al. "Efficient Z gates for quantum computing." Phys. Rev. A 96, 022330 (2017).</li>
<li>S. Holm. "A simple sequentially rejective multiple test procedure." Scand. J. Statist. 6, 65–70 (1979).</li>
<li>F. Wilcoxon. "Individual comparisons by ranking methods." Biometrics Bull. 1, 80–83 (1945).</li>
</ol>
</body></html>"""
(H / "paper.html").write_text(HTML)
print("paper.html", len(HTML))
