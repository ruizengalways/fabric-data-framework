# `fabric_data_framework.evidence`

This folder owns **retained integration evidence and explicitly approved real-environment execution**. It does not define dataset semantics, capture semantics, apply semantics, provider transports, or recovery truth; it proves those existing contracts and retains safe evidence about them.

## Reading order

```text
integration_evidence.py
  evidence vocabulary, spec, result, manifest, PASS/FAIL/NOT_RUN
        ↓
integration_checks.py
  safe projections from provider/runtime outcomes into evidence results
        ↓
integration_evidence_merge.py
  strict staged merge; contradictory substantive reruns conflict
        ↓
integration_runner.py
  credential-free exact-release preflight and runtime env-var presence checks
        ↓
approved_*_runner.py
  explicitly authorized environment-facing executions
```

Representative business-path candidate proof has an additional hard boundary:

```text
approved_business_path_runner.py
  executes/evaluates one exact path and returns an execution report only
        ↓
business_path_release_proof.py + exact ReleaseManifest
  packages the already-evaluated result into a domain-bound ReleaseReadinessProofBundle
```

The runner must not expose an unbound partial-proof writer. Candidate proof packaging requires the exact customer/domain `ReleaseManifest.bundle.release_hash`.

## Approved runners

| File | Responsibility |
|---|---|
| `approved_control_plane_runner.py` | production-eligible control-plane certification |
| `approved_pipeline_runner.py` | Fabric Pipeline execution plus exact durable framework child outcome |
| `approved_capture_runner.py` | Copy Job / Spark execution plus verified post-run observation and `CaptureReceipt` |
| `approved_warehouse_runner.py` | same-transaction target marker plus fail-closed UNKNOWN reconciliation |
| `approved_warehouse_fault_runner.py` | real ambiguous-COMMIT drill and separately-authorized session recovery |
| `approved_business_path_runner.py` | representative path execution/evaluation report; no candidate proof bundle packaging |

## Dependency direction

```text
semantic/runtime/provider/recovery core
                 ↑
             evidence
                 ↑
                CLI
```

Evidence may depend on core contracts. Core semantics must not be rewritten inside an evidence runner just to make a check pass.

## Canonical imports

This folder is the only evidence import surface. Use canonical paths such as:

```python
from fabric_data_framework.evidence.integration_evidence import IntegrationEvidenceSpec
from fabric_data_framework.evidence.approved_capture_runner import execute_approved_capture
from fabric_data_framework.evidence.business_path_release_proof import (
    build_business_path_partial_proof_bundle,
)
```

Root-level evidence aliases are intentionally not provided.

## Safety rules

- Provider `Completed` is not framework semantic success.
- Source-controlled run config stores env-var names, never secret values.
- Mutating checks require explicit authorization.
- Retained evidence rejects credential-like material.
- Unknown target commit outcome never permits blind retry.
- Marker absence is `UNRESOLVED` unless independently certified otherwise.
- A simulated framework ACK loss is not evidence of a real provider/network COMMIT disconnect.
- Candidate business-path proof cannot be packaged without the exact customer/domain ReleaseManifest identity.

`evidence/safety.py` owns fail-closed validation for text retained as integration evidence.
