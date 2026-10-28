"""Go/no-go: does a real RZZ(theta) job run on the free Open Plan?
Run once:  QiskitRuntimeService.save_account(channel="ibm_quantum_platform", token="YOUR_API_KEY")
"""
from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

service = QiskitRuntimeService()
backends = service.backends(use_fractional_gates=True, operational=True, simulator=False)
print("Backends with fractional gates:")
for b in backends:
    print(f"  {b.name:15s} rzz={'rzz' in b.target.operation_names}  rx={'rx' in b.target.operation_names}")

backend = next(b for b in backends if "rzz" in b.target.operation_names)
qc = QuantumCircuit(2)
qc.h([0, 1])
qc.rzz(0.3, 0, 1)
qc.h([0, 1])
qc.measure_all()
isa = transpile(qc, backend, optimization_level=1)
print("Ops after transpile:", dict(isa.count_ops()))  # must contain 'rzz'

job = SamplerV2(backend).run([isa], shots=200)
print("JOB ID:", job.job_id(), "on", backend.name)
print("Counts:", job.result()[0].data.meas.get_counts())
print("Usage (s):", job.usage())
