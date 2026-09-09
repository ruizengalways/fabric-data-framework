# `fabric_data_framework.evidence`

This folder owns **retained integration evidence and explicitly approved real-environment execution**. It does not define dataset semantics, capture semantics, apply semantics, provider transports, or recovery truth; it proves those existing contracts and retains safe evidence about them.

## Reading order

```text
integration/evidence.py
  evidence vocabulary, spec, result, manifest, PASS/FAIL/NOT_RUN
        ↓
integration/checks.py
  safe projections from provider/runtime outcomes into evidence results
        ↓
integration/merge.py
  strict staged merge; contradictory substantive reruns conflict
        ↓
integration/runner.py
  credential-free exact-release preflight and runtime env-var presence checks
        ↓
approved_*_runner.py
  explicitly authorized environment-facing executions
```

Representative business-path candidate proof has an additional hard boundary:

```text
business_paths/approved_runner.py
  executes/evaluates one exact path and returns an execution report only
        ↓
business_paths/release_proof.py + exact ReleaseManifest
  packages the already-evaluated result into a domain-bound ReleaseReadinessProofBundle
```

The runner must not expose an unbound partial-proof writer. Candidate proof packaging requires the exact customer/domain `ReleaseManifest.bundle.release_hash`.

## Approved runners

| File | Responsibility |
|---|---|
| `integration/approved/control_plane.py` | production-eligible control-plane certification |
| `integration/approved/pipeline.py` | Fabric Pipeline execution plus exact durable framework child outcome |
| `integration/approved/capture.py` | Copy Job / Spark execution plus verified post-run observation and `CaptureReceipt` |
| `integration/approved/warehouse.py` | same-transaction target marker plus fail-closed UNKNOWN reconciliation |
| `integration/approved/warehouse_fault.py` | real ambiguous-COMMIT drill and separately-authorized session recovery |
| `business_paths/approved_runner.py` | representative path execution/evaluation report; no candidate proof bundle packaging |

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
from fabric_data_framework.evidence.integration.evidence import IntegrationEvidenceSpec
from fabric_data_framework.evidence.integration.approved.capture import execute_approved_capture
from fabric_data_framework.evidence.business_paths.release_proof import (
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
