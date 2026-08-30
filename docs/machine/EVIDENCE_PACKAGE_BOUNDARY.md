# MACHINE EVIDENCE PACKAGE BOUNDARY

Canonical implementation owner:

```text
src/fabric_data_framework/evidence/
```

Historical root paths remain compatibility aliases only.

## Canonical modules

```text
integration_evidence.py
integration_checks.py
integration_evidence_merge.py
integration_runner.py
approved_control_plane_runner.py
approved_pipeline_runner.py
approved_capture_runner.py
approved_warehouse_runner.py
approved_warehouse_fault_runner.py
```

## Required invariants

```text
legacy root import module object == canonical evidence module object
root compatibility modules contain no functions/classes
CLI may depend on evidence
evidence must not depend on CLI
evidence proves core semantics/runtime/provider/recovery; it does not redefine them
layout refactor never promotes live-service evidence claims
```

Keep this extraction separate from any future control-plane folder migration.
