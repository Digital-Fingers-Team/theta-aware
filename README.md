# θ-Aware

ISEF project (Systems Software / Algorithms): how the error of IBM's fractional
RZZ(θ) gate depends on the angle θ, and a θ-aware compiler that uses it.

- Incoherent error ε(θ) from mirror circuits, coherent over-rotation δ(θ) from
  phase amplification, on ibm_marrakesh, ibm_kingston and ibm_fez.
- Scripts run in order (01_ ... 16_); each submit is dry-run first. Results
  and job IDs: RESEARCH_LOG.md. Raw job data: *.json. Plan: research-plan.pdf.

Setup: Python 3.12, qiskit 2.5.2, qiskit-ibm-runtime 0.50. Put your IBM
Quantum API key in .ibm_key (never committed).

Compiler: package `thetaaware/` (a Qiskit pass that picks, per RZZ(θ), the fractional gate, the fractional gate with virtual-RZ correction and optional pre-distortion, or two CZ, from the measured per-angle model; plus layout scoring). Tests: `python -m pytest tests`.

Use:

```python
from thetaaware import calibration, compile_circuit
cal = calibration.marrakesh_after_e8()           # or build one with calibration.from_jobs(...)
compiled, report = compile_circuit(circuit, coupling_map, layout, cal)
print(report.counts(), report.predicted_error())
```

Paper: ThetaAware_Research_Paper.pdf (exploratory hardware results, the compiler tested on recorded jobs and in simulation, and model-based projections; the compiler has not run on hardware and the confirmatory experiment has not been run). Rebuild with no QPU use: `python 17_paper_analysis.py; python 18_h1_sensitivity.py; python -m pytest tests; python 21_compiler_replay.py; python 22_compiler_benchmark.py; python 23_compiler_figures.py; python 19_build_paper.py`, then print paper.html to PDF.
