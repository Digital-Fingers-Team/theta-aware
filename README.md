# θ-Aware

ISEF project (Systems Software / Algorithms): how the error of IBM's fractional
RZZ(θ) gate depends on the angle θ, and a θ-aware compiler that uses it.

- Incoherent error ε(θ) from mirror circuits, coherent over-rotation δ(θ) from
  phase amplification, on ibm_marrakesh, ibm_kingston and ibm_fez.
- Scripts run in order (01_ ... 16_); each submit is dry-run first. Results
  and job IDs: RESEARCH_LOG.md. Raw job data: *.json. Plan: research-plan.pdf.

Setup: Python 3.12, qiskit 2.5.2, qiskit-ibm-runtime 0.50. Put your IBM
Quantum API key in .ibm_key (never committed).
