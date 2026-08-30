# MACHINE STATE — fabric-data-framework

```yaml
schema: fabric-data-framework-machine-state-v1
updated: 2026-08-30
public_release: v0.3.0
source_version: 0.4.0-development-unreleased
release_allowed: false
code_baseline:
  pull_request: 68
  merge_sha: a117c27a32b4e4f9c4bf1a7dcf6a35e9d3f6d16b
  exact_candidate_head: 930c1b22f9901d447250db0799b3f7e855d38303
  milestone: canonical-only explicit package ownership; root package is namespace-only
  ci_actions: 33291942505
  tests: 592
  python_3_11: success
  python_3_13: success
  wheel: success
documentation_model:
  human: docs/human
  machine: docs/machine
  examples: examples
  rule: human docs explain stable understanding and use; machine docs retain exact engineering state, evidence and compact provenance
```

## Release decision

`0.4.0` remains **UNRELEASED**. Portable semantics/runtime/approved-runner contracts are broad, but exact-candidate retained real enterprise evidence is incomplete. Never infer live proof from CI.

## Canonical source ownership

The unreleased 0.4.0 tree intentionally prefers one explicit owner over compatibility aliases or broad package facades.

```text
src/fabric_data_framework/
  __init__.py               namespace marker only; no imports/re-exports/version symbol

  contracts/                provider-neutral immutable semantic/runtime contracts
    base.py
    schema.py
    audit.py
    reconciliation.py
    quarantine.py
    target_operation.py
    capture_receipt.py
    dispatch.py
    execution_plan.py
    rebuild.py
    recovery.py
    replay.py

  control_plane/            relational control-plane implementation
    schema.py
    io.py
    schema_evidence.py
    certification.py
    repository.py
    sqlalchemy_repository.py
    operator.py
    target_operation_journal.py

  evidence/                 integration evidence + approved exact-run executors
    safety.py
    integration_evidence.py
    integration_checks.py
    integration_evidence_merge.py
    integration_runner.py
    approved_*_runner.py

  deployment/               release/promotion contracts + delivery/materialization
    contracts.py
    delivery.py

  cli/                      removable leaf presentation layer
    main.py
    base.py
    approved.py

  capture/
  apply/
  execution/
  adapters/
  data_plane/
  orchestration/
  quality/
  recovery/
  extensions/
  metadata/
```

Package-root and extracted-package `__init__.py` files do not rebuild convenience APIs through large re-export lists. Callers import the concrete owner module.

Examples:

```python
from fabric_data_framework.config import DatasetConfig
from fabric_data_framework.contracts.target_operation import TargetOperationIntent
from fabric_data_framework.control_plane.sqlalchemy_repository import SqlAlchemyControlPlaneRepository
from fabric_data_framework.deployment.delivery import build_release_manifest
from fabric_data_framework.evidence.integration_evidence import IntegrationEvidenceManifest
```

The root `__version__` symbol is intentionally absent. CLI defaults read the installed distribution version through `importlib.metadata.version("fabric-data-framework")`.

## Readability boundary contracts

CI enforces canonical-only ownership:

```text
removed flat evidence modules stay absent
retained_evidence_safety.py stays absent; evidence/safety.py is the owner
cli_router.py stays absent
removed flat control-plane/repository/operator/journal modules stay absent
root deployment.py and delivery.py stay absent
root schema_contract.py, operations.py and target_operations.py stay absent
contracts/__init__.py does not recreate an eager re-export facade
control_plane/__init__.py does not recreate the old control-plane API
root fabric_data_framework/__init__.py is namespace-only
src/tests may not use root symbol imports such as `from fabric_data_framework import DatasetConfig`
core/control_plane/evidence/deployment do not depend on CLI
physical removal of cli/ does not break explicit reusable-core imports
```

For further readability work: move only ownership-complete modules into an already-clear domain, migrate all callers/tests/docs in the same slice, delete the old path, prove the old path stays absent, and run full Python 3.11 / 3.13 / wheel CI. Do not add compatibility shims for unreleased 0.4.0.

## Dependency direction

```text
contracts / config / semantic core
             ↓
 capture / apply / execution / recovery
             ↓
 adapters + control_plane
             ↓
 evidence
             ↓
 cli
```

This is conceptual rather than a requirement that every module import exactly downward; the hard rule is that CLI remains a leaf and evidence must not redefine semantic/runtime truth merely to make checks pass.

## Current highest evidence labels

```text
IMPLEMENTED + CI PROVEN EVIDENCE HARNESS CONTRACT
IMPLEMENTED + CI PROVEN APPROVED-RUN PREFLIGHT / READ-ONLY RUNNER CONTRACT
IMPLEMENTED + CI PROVEN EVIDENCE MERGE CONTRACT
IMPLEMENTED + CI PROVEN APPROVED CONTROL-PLANE CERTIFICATION RUNNER CONTRACT
IMPLEMENTED + CI PROVEN APPROVED PIPELINE RUNNER CONTRACT
IMPLEMENTED + CI PROVEN APPROVED CAPTURE RUNNER CONTRACT
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE AMBIGUOUS-COMMIT FAULT-DRILL RUNNER CONTRACT
IMPLEMENTED + CI PROVEN FABRIC WAREHOUSE SESSION-TERMINATION ABSENCE CERTIFIER CONTRACT
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE SESSION-TERMINATION RECOVERY CONTRACT
```

Readability refactors do not promote any live-service evidence label. Do not use `FABRIC PROVEN`, `FABRIC WAREHOUSE PROVEN`, `PRODUCTION DB PROVEN`, or equivalent without retained exact-release approved real-service evidence.

## Current real-service gaps

```text
enterprise Entra token acquisition under selected identity
real workspace/item authorization smoke
real Fabric SQL Database or Azure SQL Database production-certified PASS
real approved Pipeline execution
real Copy Job execution + approved post-run observation + verified CaptureReceipt
real bounded Spark execution + approved post-run observation + verified CaptureReceipt
real Fabric Warehouse target mutation + same-transaction marker
provider-specific live Warehouse COMMIT fault injector
retained real ambiguous-COMMIT fault-drill PASS
live exact Warehouse connection_id + session_id capture using selected SQL driver
live Admin DMV observation / KILL / rollback chain
production-approved marker-absence recovery
capacity/SKU/throttling/gateway evidence
backup/restore/HA/DR/monitoring/retention/governance evidence
live Kafka coordination if included in 0.4.0 public scope
live Delta CDF bounded read/retention if included in 0.4.0 public scope
complete exact-release certified IntegrationEvidenceManifest
```

## Preferred real evidence order

```text
1. exact candidate release hash / item UUIDs / artifact fingerprints
2. read-only item smoke
3. production control-plane certification
4. strict merge item + control-plane prerequisites
5. approved Pipeline
6. approved Copy Job / Spark capture
7. approved Warehouse target+marker recovery
8. optional provider-specific real ambiguous-COMMIT fault drill
9. optional exact-session termination recovery under separate Admin authority
10. strict merge required evidence
11. integration-evidence-validate --require-certified
12. Kafka/Delta live only if in public release promise
13. exact-candidate release audit
14. only then consider 0.4.0 release
```

## Next reusable readability work

Do not add another generic Warehouse recovery algorithm. With no real enterprise credentials, the useful source-layout work is to reduce the remaining root stragglers only where an existing owner is obvious. Candidates to inspect/move independently:

```text
watermark.py       -> capture/
scd2.py            -> apply/
bronze.py          -> data_plane/
reconciliation.py  -> quality/
fabric_auth.py     -> adapters/fabric/
```

Inspect `runtime.py` and `infrastructure.py` before deciding ownership; do not create a directory merely to reduce root file count.

## Repository ownership

```text
fabric-data-framework = reusable semantics/runtime/adapters/recovery/evidence/package
fabric-customer       = business/domain DatasetConfig + bounded extensions + Fabric content
fabric-infra          = optional capacity/workspace/infrastructure lifecycle
```

Initial enterprise evaluation may proceed without `fabric-infra`.
