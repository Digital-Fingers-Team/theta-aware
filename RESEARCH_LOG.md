# θ-Aware — Research Log

Project notebook for the ISEF project "θ-Aware: measuring the angle-dependent error of IBM fractional RZZ(θ) gates and compiling with it".
Every hardware run is listed with its job ID, its QPU cost and the raw-data file. Raw data (counts) for every job is kept in the JSON files on the server, in `pricelens:~/theta-aware/`.

- **Account:** IBM Quantum Open Plan (10 QPU minutes per 28-day period). Instance CRN `...576e2f1c-9255-405d-b933-0f01ca671a9f`.
- **Software:** Python 3.12, Qiskit 2.5.2, qiskit-aer 0.17.2, qiskit-ibm-runtime 0.50.0.
- **Status:** all results below are **exploratory**. They come from one day (14 Oct 2026). They will NOT be reused as confirmatory evidence. Hypotheses must be pre-registered before the full multi-day sweep.

---

## Summary of findings so far (14 Oct 2026, exploratory)

1. **The error of fractional RZZ(θ) depends on θ.** The constant-error model (which is what IBM reports) is rejected in 5/8 pairs on ibm_marrakesh (E2), 4/8 when repeated an hour later (E8), and **7/8 on ibm_kingston (E7)**.
2. **The fractional gate carries an angle-dependent single-qubit Z phase** on each qubit. It reaches up to ±0.3 rad/gate on a bad pair and ≲0.06 on good pairs (E3 diagnosis, E4, E6). IBM does not report it.
3. **That phase can be removed for free** with virtual RZ gates (no added error, no added time). This improved results significantly on both devices: marrakesh p = 2e-9 (E4), kingston p = 2e-6 (E6). Large gains appear on bad pairs, e.g. 0.06 → 0.87 and 0.41 → 0.96.
4. **Correcting the over-rotation δ alone does not help** (E3, negative).
5. **Coherent errors (δ, local phases) are stable for at least about an hour.** Incoherent error ε(θ) fluctuates (E8). So: calibrate the coherent part once and correct it; treat ε as time-varying.
6. **Limits found:**
   - Small angles on a pair with large δ cannot be fixed by pre-distortion (E5, explained quantitatively). They are not fixed by a two-gate trick either (E9, negative).
   - One kingston pair has an untrustworthy calibration, and correcting it hurts (E6). The compiler therefore needs a calibration-quality gate.
7. **Choosing the implementation matters a lot (E10).** On the bad pair at small angles, the standard 2-CZ decomposition gives 0.86–0.89 success vs 0.05–0.44 for the fractional gate, although IBM reports equal error for both. This is the strongest single result for the compiler (H2).

## QPU budget (account 1, 600 s per rolling 28 days)

| Experiment | QPU s |
|---|---|
| E1 pilot | 9 |
| E2 sweep | 82 |
| E3 compensation v1 | ≈0 |
| E4 round 2 | 77 + ≈0 |
| E5 isolation | 45 + 15 |
| E6 kingston round 2 | 76 + 24 |
| E7 kingston sweep | 81 |
| E8 marrakesh repeat | 82 |
| E9 two-gate | 9 |
| E10 CZ baseline | 9 |
| **Total (IBM-reported)** | **551 of 600** (49 s kept in reserve) |

Cost model: ≈0.27 QPU s per circuit at 1000 shots. Small jobs are sometimes billed 0 s.

---

## Methods used (short)

**Mirror circuits → incoherent error ε(θ).** We apply d layers of RZZ(θ) and then d inverse layers. Each inverse is implemented as X·RZZ(θ)·X, since RZZ(−θ) cannot be sent directly. The ideal output is |00⟩, and survival S(d) = A·p^(2d) is fitted against depth. The error per gate is ε = (15/16)(1 − p). Because the inverse runs the *same* physical gate, coherent over-rotation cancels. ε therefore measures only the incoherent part.

**Phase amplification → coherent over-rotation δ(θ) and local phases α(θ), β(θ).**
- Gate model: RZZ(θ+δ) · RZ_a(α) · RZ_b(β).
- One qubit (the control) is put in |0⟩ or |1⟩ and the other (the target) in |+⟩. RZZ(θ) is applied N times (N = 1, 2, 4, 8, 16), and the target phase is read out in the X and Y bases.
- With control = |0⟩ the phase is N(θ+δ+β); with control = |1⟩ it is N(−(θ+δ)+β).
- The difference gives θ+δ, and the sum gives the local phase β. Swapping roles gives α.
- Phases are unwrapped step by step over the doubling N.

**Correctness test (used for compensation).** Start in |++⟩, apply RZZ(θ) K times with Kθ = π (ideal output |11⟩) or Kθ = 2π (ideal output |00⟩), then apply H⊗H. Success = P(ideal output).

**Protocol safeguards.**
- All circuits are transpiled with optimization level 0 plus barriers.
- A script check aborts the job before submission if the transpiler merged or decomposed any RZZ.
- Circuit order inside each job is randomized with a fixed seed, so drift cannot look like angle dependence.
- Several disjoint qubit pairs are measured in parallel in the same circuit. This costs no extra QPU time.

**Statistics.**
- Confidence intervals come from a parametric (binomial) bootstrap with 300 resamples.
- Constant-error test per pair: χ² against the weighted mean, then Holm correction across pairs (α = 0.01).
- Compensation tests use a one-sided Wilcoxon signed-rank test.

**Simulation validation (no QPU).** `02_sim_validate.py` injects δ = 0.02 rad into a simulated gate.
- Mirror survival is identical with and without δ, which confirms that mirror circuits are blind to δ.
- Phase amplification recovers δ = 0.0195 / 0.0198 / 0.0200.

`10_round2.py --sim` injects known δ, α and β. The correction then raises success to ≈ 0.99–1.00, which validates the full pipeline before any hardware use.

---

## Experiment log

### E1 — Go/no-go + pilot (14 Oct 2026)
- **Purpose:** check that fractional RZZ works on the free plan, and measure the real QPU cost per circuit.
- **Result:** fractional RZZ is available on **ibm_fez, ibm_kingston, ibm_marrakesh**. **GO.**
- **Job:** `db7sikmil99s73foptfg` on ibm_marrakesh. 48 circuits × 500 shots, 4 pairs, 4 angles. **9 QPU s** (0.19 s/circuit).
- **File:** `pilot_db7sikmil99s73foptfg.json`
- **Finding:** pair (10,11) showed ≈10× larger error at small angles. The pilot was too small for statistics.

### E2 — Confirmation sweep (14 Oct 2026)
- **Job:** `db7sns0r1c5c738l7vm0` on ibm_marrakesh. 300 circuits × 1000 shots. 8 pairs × 12 angles (π/24 … π/2); mirror depths 1–32; N = 1–16. **82 QPU s** (0.27 s/circuit).
- **File:** `confirm_db7sns0r1c5c738l7vm0.json`. Calibration table: `calib_db7sns0r1c5c738l7vm0.json`.
- **Result (H1 preview):** the constant-error model was **rejected in 5/8 pairs (62%)** (Holm p < 0.01).

| Pair | IBM-reported error | Holm p | ε at θ=0.13 | ε minimum (θ) | Verdict |
|---|---|---|---|---|---|
| (10,11) | 0.00149 | 5e-124 | 0.0086 [0.0079, 0.0094] | 0.0003 (0.65) | reject |
| (32,33) | 0.00166 | 9e-41 | 0.0032 | 0.0006 (1.44) | reject |
| (14,15) | 0.00169 | 1e-21 | 0.0003 | 0.0002 (1.05) | reject (peak 0.0020 at 0.52) |
| (21,36) | 0.00162 | 1e-4 | 0.0015 | 0.0007 (0.65) | reject |
| (91,98) | 0.00143 | 9e-3 | 0.0013 | 0.0003 (0.39) | reject |
| (12,13) | 0.00158 | 0.024 | 0.0011 | 0.0003 (0.39) | not rejected |
| (2,3) | 0.00134 | 0.045 | 0.0004 | 0.0002 (0.26) | not rejected |
| (93,94) | 0.00153 | 0.115 | — | — | not rejected; δ unmeasurable (bad pair) |

- **Over-rotation δ(θ):** on pair (10,11), δ varied smoothly from **+0.28 rad (θ=0.13) to −0.22 rad (θ=1.31)**. On the other pairs, |δ| < 0.03 rad.
- **Note:** the mirror-circuit ε is mostly *below* IBM's reported value. That is expected, because the mirror excludes coherent error.

### E3 — Compensation v1: correct δ only (14 Oct 2026) — NEGATIVE
- **Job:** `db7sr6mil99s73foqgjg` on ibm_marrakesh. 28 circuits × 2000 shots, 7 pairs. **≈0 QPU s billed.**
- **File:** `comp_db7sr6mil99s73foqgjg.json`
- **Correction:** pre-distort the angle so that θ' + δ(θ') = θ, or use a two-gate decomposition when θ is out of reach.
- **Result:** **no improvement** (median relative gain −0.9% over 92 cases). It was clearly worse on (10,11).
- **Diagnosis (no QPU):**
  - `08_diagnose_sign.py`: neither +δ nor −δ explains the data.
  - `09_local_phase.py`: the *sum* channel of E2 reveals a large **angle-dependent single-qubit phase**. On (10,11) it ran from −0.19 to +0.41 rad/gate. The differential δ measurement cancels this phase by design. It was the dominant error.
- **Lesson:** this negative result is kept and reported. It is what led to the main finding.

### E4 — Round 2: local phases on both qubits + compensation v2 (14 Oct 2026)
- **Jobs:**
  - calibration `db7t1liraffc73fb843g` (280 circuits × 1000 shots, **77 QPU s**);
  - test `db7t6ier6oqs738898ig` (42 circuits × 2000 shots, **≈0 QPU s**).
  - Both on ibm_marrakesh, 7 pairs, 7 angles.
- **File:** `round2_db7t6ier6oqs738898ig.json` (calibration, counts, test).
- **Local phases (rad per gate), pair (10,11):** α = −0.26 → +0.18; β = −0.19 → +0.28 across θ. On the other pairs, |α|, |β| ≲ 0.06.
- **Variants:**
  - **raw:** no correction.
  - **local:** virtual RZ(−α), RZ(−β) after every gate. Zero added error and zero time.
  - **local+δ:** the local correction plus a pre-distorted angle.

| Variant | Mean gain in P(success) | Median relative gain | Wilcoxon one-sided p | n |
|---|---|---|---|---|
| local | +0.040 | +1.0% | 5.7e-8 | 98 |
| local+δ | +0.046 | +1.2% | 1.5e-9 | 98 |

- **Pair (10,11) examples:**
  - π/24 (2π total): 0.11 → 0.74
  - π/12 (2π): 0.06 → 0.87
  - π/6 (2π): 0.41 → **0.96**
  - π/3 (2π): 0.33 → 0.82
  - π/2 (2π): 0.84 → 0.95
- **Failures:** 3/14 cases on (10,11) flipped to ≈0.02, the opposite answer: π/12 (π total), π/8 (2π), π/3 (π). The pattern fits a residual coherent phase of ≈ π/K. Hypothesis: crosstalk from the neighbouring pair (12,13) running in parallel → tested in E5.
- **Good pairs:** already ≈0.93–0.97 raw, with small changes. The median gain is small because the gain is concentrated on bad pairs. **H2's 10% target is not met on this circuit family.**

### E5 — Isolation of pair (10,11): is the E4 failure crosstalk? (14 Oct 2026) — NO
- **Jobs:**
  - calibration `db7td6er6oqs73889jeg` (160 circuits × 1000 shots, **45 QPU s**);
  - test `db7tldiraffc73fb95gg` (24 circuits × 2000 shots, **15 QPU s**).
  - Both on ibm_marrakesh, pair (10,11) **alone**. Script `11_isolation.py`. File `iso_db7tldiraffc73fb95gg.json`.
- **Result:** the same failures appear without neighbours. At π/12 (π total) local → 0.020; at π/8 (2π) 0.019; at π/3 (π) 0.025. **So they are not crosstalk.** The calibration also reproduced (α, β, δ within ≈0.04 rad of E4).
- **Explanation, worked out quantitatively (no QPU):** at π/12 and π/8, the target angle lies **below the reachable range** of a single gate. Asking for the smallest angle already gives r(0.13) = 0.41. So δ stays uncorrected, and the circuit's total ZZ error is K·δ. The predicted success cos²(Kδ/2) matches the measurements:

| Case | K | δ (rad) | Predicted P | Measured P (local) |
|---|---|---|---|---|
| π/12, π total | 12 | 0.243 | 0.013 | 0.020 |
| π/12, 2π total | 24 | 0.243 | 0.95 | 0.89 |
| π/8, π total | 8 | 0.186 | 0.54 | 0.51 |
| π/8, 2π total | 16 | 0.186 | 0.007 | 0.019 |

- **Unexplained:** π/3 with K=3 (π total) fails at 0.025, while K=6 (2π total) works at 0.75. This remains an open anomaly.
- **Compiler implication:** small angles on this pair need a *different implementation*, not just correction → tested in E9.

### E6 — Round 2 on second device ibm_kingston (14 Oct 2026)
- **Jobs:** calibration `db7td80r1c5c738l9490` (280 circuits, **76 QPU s**); test `db7teq6il99s73forh20` (42 circuits × 2000 shots, **24 QPU s**). 7 pairs. Script `12_round2_kingston.py`. File `round2k_db7teq6il99s73forh20.json`.
- **Local phases:** small on ibm_kingston, |α|, |β| ≲ 0.06 rad. The exception is pair (0,1): its α estimates jump erratically (−0.77, −0.83, −1.55, −1.25 rad), which points to an unstable qubit 0 whose calibration cannot be trusted.
- **Correction result:** overall, the improvement is significant but small (local: Wilcoxon p = 6e-6, mean +0.001; local+δ: p = 2e-6, mean +0.003). Per pair:

| Pair | Mean gain (local) | Cases improved |
|---|---|---|
| (108,109) | +0.030 | 12/14 |
| (151,152) | +0.019 | 12/14 |
| (59,75) | +0.012 | 12/14 |
| (96,103) | +0.005 | 10/14 |
| (16,23) | +0.006 | 10/14 |
| (141,142) | +0.003 | 7/14 |
| (0,1) | **−0.069** | 6/14 |

- **Reading:** the free correction helps 6 of 7 pairs on a second device. It hurts only the pair with an untrustworthy calibration. **This means the compiler needs a calibration-quality gate.** For example: skip correction when α/β/δ are not smooth in θ, or when their bootstrap CI is wide. ibm_kingston pairs are cleaner than marrakesh (10,11), so the gains are smaller.

### E7 — ε(θ) sweep on second device ibm_kingston (14 Oct 2026)
- **Job:** `db7td8or1c5c738l94d0`. 300 circuits × 1000 shots, 8 pairs × 12 angles, **81 QPU s**. File `sweepK_db7td8or1c5c738l94d0.json`. Calibration table `calib_kingston.json`.
- **Result (H1 preview, 2nd device):** the constant-error model was **rejected in 7/8 pairs (88%)** (Holm p < 0.01). Holm p values: (16,23) 3e-27, (141,142) 2e-8, (105,117) 2e-6, (108,109) 3e-5, (59,75) 3e-4, (96,103) 3e-4, (151,152) 6e-3. Not rejected: (0,1) p = 0.72.

### E8 — Drift: repeat of the E2 sweep on ibm_marrakesh, ≈1 h later (14 Oct 2026)
- **Job:** `db7td8or1c5c738l94dg`. Same 8 pairs and design as E2, **82 QPU s**. File `sweepM2_db7td8or1c5c738l94dg.json`. Calibration table `calib_marrakesh2.json`.
- **H1 preview:** rejected in **4/8 pairs (50%)**: (10,11), (91,98), (21,36), (32,33). These 4 were also rejected in E2. (14,15) was rejected in E2 but not now.
- **Stability over ≈1 h:**

| Pair | δ(θ) correlation E2 vs E8 | max \|Δδ\| (rad) | ε(θ) correlation | ε at θ=0.13: E2 → E8 |
|---|---|---|---|---|
| (10,11) | 1.00 | 0.005 | 0.17 | 0.0086 → **0.0006** |
| (32,33) | 0.97 | 0.004 | 0.79 | 0.0032 → 0.0019 |
| (91,98) | 0.94 | 0.006 | −0.07 | 0.0013 → 0.0006 |
| (14,15) | 0.92 | 0.004 | −0.10 | 0.0003 → 0.0004 |
| (2,3) | 0.89 | 0.004 | 0.55 | 0.0004 → 0.0004 |
| (12,13) | 0.85 | 0.007 | 0.50 | 0.0011 → 0.0008 |
| (21,36) | 0.83 | 0.018 | 0.28 | 0.0015 → 0.0013 |

- **Key finding:** the **coherent** errors (δ, and the local phases from E4/E5) are **stable** over this hour (changes ≤ 0.02 rad). So "calibrate once, then correct for free" is viable. The **incoherent** ε(θ) is real at any given moment, but its *shape* fluctuates. Example: the large small-angle error on (10,11) disappeared, which suggests a fluctuating defect (e.g. a two-level system). The confirmatory H1 test must therefore be **multi-day**, and the compiler should treat ε(θ) as time-varying. δ, α and β can be treated as quasi-static.

### E9 — Two-gate implementation for small angles on (10,11) (14 Oct 2026)
- **Job:** `db7tqbmil99s73fos67g` on ibm_marrakesh. 12 circuits × 2000 shots. Script `15_twogate.py`.
- **Design:** RZZ(θ) ≈ RZZ(a)·X RZZ(b) X with r(a) − r(b) = θ, where a and b are on calibrated grid points. π/12 uses a=π/4, b=π/12; π/8 uses a=π/3, b=π/12. A virtual-RZ local correction follows every physical gate. This is compared with raw and with the single-gate local correction.
- **QPU:** 9 s. File `twogate_db7tqbmil99s73fos67g.json`.

| Case | ideal | raw | local (1 gate + RZ) | two-gate + RZ |
|---|---|---|---|---|
| π/12, K=12 | 11 | 0.430 | 0.015 | 0.279 |
| π/12, K=24 | 00 | 0.055 | **0.802** | 0.162 |
| π/8, K=8 | 11 | 0.334 | 0.508 | 0.529 |
| π/8, K=16 | 00 | 0.121 | 0.011 | 0.065 |

- **Result: NEGATIVE.** The two-gate implementation does not fix small angles on this pair. Likely reasons: (1) twice the physical gates, so twice the incoherent error; (2) a and b use calibrated values from an earlier job, and even a 0.005 rad/gate residual adds up over 24–48 gates; (3) the local phases of the folded gate may not simply flip sign as assumed. Next test (E10): the standard 2-CZ decomposition.

### E10 — Standard CZ decomposition as an alternative for small angles on (10,11) (14 Oct 2026)
- **Job:** `db7u6r0r1c5c738lalhg` on ibm_marrakesh. 12 circuits × 2000 shots, **9 QPU s**. Script `16_cz_baseline.py`. File `czbase_db7u6r0r1c5c738lalhg.json`. Compares raw, local, and RZZ(θ) = CX·RZ(θ)·CX (2 CZ per gate, no fractional gate).

| Case | ideal | fractional raw | fractional + local RZ | **standard 2-CZ** |
|---|---|---|---|---|
| π/12, K=12 | 11 | 0.439 | 0.014 | **0.873** |
| π/12, K=24 | 00 | 0.050 | 0.806 | **0.862** |
| π/8, K=8 | 11 | 0.340 | 0.511 | **0.894** |
| π/8, K=16 | 00 | 0.102 | 0.011 | **0.891** |

- **Result: STRONG.** On this pair, at small angles, the standard decomposition is far better (0.86–0.89) than the fractional gate (0.05–0.44 raw). It uses *twice* as many two-qubit gates, yet still wins. IBM reports the same error for the fractional gate as for CZ, so a compiler that trusts IBM's numbers (e.g. Qiskit with fractional gates enabled) would pick the fractional gate here and lose most of the signal.
- **Compiler rule this justifies:** for each (pair, angle), choose between {fractional + virtual-RZ correction, fractional + pre-distortion, standard 2-CZ} using the *measured* per-angle data. This is exactly the "implementation choice" stage of θ-Aware. E10 is the first direct hardware evidence that the choice matters: success rises from ≈0.1–0.4 to ≈0.87–0.89 on the affected circuits.
- The repeat of the E9 raw/local columns (0.44/0.014, 0.05/0.81, 0.34/0.51, 0.10/0.011) reproduces E9 closely about 30 min later. This is further evidence that the coherent error is stable.

---

## Paper (7 Nov 2026, no QPU used)
- `ThetaAware_Research_Paper.pdf`, built from `17_paper_analysis.py`, `18_h1_sensitivity.py` and `19_build_paper.py`, which recompute every number from the raw job files.
- **H1 count depends on the bootstrap seed:** across 40 seeds, E2 gives 4-7 of 8 rejected (median 5), E7 6-7 (median 7), E8 4. Use a test that does not depend on the seed before pre-registering.
- **H3 preview:** rho 0.74 (model) vs 0.53 (IBM) on 196 raw cases; difference CI [-0.07, +0.42] includes 0, and the advantage goes away without the two bad pairs.
- **Projections (model outputs, not data):** H1 likely; H2 7-24% with our pair mix, under 1% with bad pairs avoided, so it depends on how common bad pairs are; H4 about 43% of the QPU time with two depths {1, 32}; full experiment about 18 QPU minutes.
- **Design problem found:** mirrored evaluation circuits would cancel delta and one qubit's local phase, hiding the coherent error under study.

---

## Scripts

| File | Role |
|---|---|
| `01_go_nogo.py` | minimal hardware access check |
| `02_sim_validate.py` | simulation check of the mirror and phase-amplification methods |
| `03_pilot.py` | E1 |
| `04_analyze_pilot.py` | ε(θ), δ(θ), CIs, Holm test; `python 04_analyze_pilot.py <json> [calib_out.json]` |
| `05_confirm.py` | E2 (8 pairs × 12 angles sweep) |
| `06_compensation.py`, `07_analyze_comp.py` | E3 |
| `08_diagnose_sign.py`, `09_local_phase.py` | E3 diagnosis (no QPU) |
| `10_round2.py` | E4 (`--sim` for simulation validation) |
| `11_isolation.py` … `14_sweep_marrakesh_repeat.py` | E5–E8 |

## Open questions / next steps
1. Is the (10,11) failure caused by crosstalk (E5)?
2. Does the local-phase effect exist on a second device (E6, E7)?
3. How stable are ε(θ), δ(θ), α(θ), β(θ) over hours and days (E8, then a multi-day sweep)?
4. **Pre-register** H1–H4, the analysis and a bad-pair exclusion rule (e.g. δ CI width > 0.5 rad) before the confirmatory sweep.
5. Compiler: add a per-gate virtual-RZ correction pass, plus pair avoidance and scheduling rules.
