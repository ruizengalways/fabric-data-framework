# Current Status — fabric-data-framework

Status: Canonical recovery checkpoint  
Last updated: 2026-08-30

## Release gate

```text
latest public release = v0.3.0
source version        = 0.4.0 development / unreleased
latest code baseline = 4dfa5e22fd8eab67406ced8af954f2d81ad18321  (PR #51 merge)
latest full code CI   = Actions 33283668067
full test baseline   = 525
```

**Do not publish `0.4.0` yet.** Portable semantics/runtime/approved-runner contracts are broad, but exact-release approved real-environment evidence and external enterprise controls remain incomplete.

## Release-significant merged sequence

```text
PR #17  durable target-operation journal / control-plane v4
PR #19  provider-native downstream recovery
PR #21  production control-plane backend certification contract
PR #22  Fabric REST Job Scheduler + Data Pipeline backend
PR #24  SQLAlchemy relational runtime repository
PR #26  concrete Copy Job + Spark Job Definition REST transports
PR #28  Fabric Warehouse same-transaction target commit proof
PR #30  approved DEV integration evidence harness
PR #32  approved-run preflight + read-only item smoke                    407 tests
PR #34  orthogonal cheatsheet semantics + exact 14 presets              419
PR #35  semantic onboarding validation + CLI                            430
PR #37  full-baseline -> WATERMARK bootstrap                            441
PR #39  strict staged integration evidence merge                        455
PR #41  approved production control-plane certification runner          466
PR #43  approved Fabric Pipeline evidence runner                        477
PR #45  approved Copy Job + Spark capture evidence runner               490
PR #47  approved Fabric Warehouse commit/recovery runner                501
PR #49  approved Warehouse ambiguous-COMMIT fault-drill runner          513
PR #51  Fabric Warehouse session-termination absence certifier contract 525
```

Latest code CI: Actions `33283668067`, Python 3.11 / 3.13 / static / wheel all SUCCESS.

## Governing invariants

```text
capture fidelity <= truthful history fidelity
provider/native cursor != framework downstream semantic checkpoint
provider Completed != framework semantic success
unknown target commit outcome never permits blind re-execution
source-controlled approved-run config stores env-var names, never secret values
mutating approved checks require explicit authorization
contradictory staged reruns are never silently arbitrated
marker absence alone never proves NOT_COMMITTED
simulated framework ACK loss != real driver/network COMMIT disconnect evidence
normal Warehouse transaction return cannot prove the real-fault drill
fault injector != marker-absence certifier
session disappearance alone != rollback proof
```

## Semantic / provider coverage

At semantic-contract + onboarding-validation level, all fourteen cheatsheet patterns are first-class and tested. Provider/runtime surfaces include Fabric Pipeline, Copy Job, Spark Job Definition, Warehouse commit proof, SQLAlchemy control plane, Kafka/Debezium and Delta CDF recovery contracts. Passing deterministic tests does not prove a live provider.

Canonical semantic detail: `CHEATSHEET_PATTERN_ALIGNMENT.md`.

## Target-operation recovery

Control-plane target-operation state remains attempt-independent and CAS protected:

```text
new               -> EXECUTE
SUCCEEDED         -> SKIP_SUCCEEDED
IN_PROGRESS retry -> RECONCILE_REQUIRED
UNKNOWN retry     -> RECONCILE_REQUIRED
NOT_COMMITTED     -> CAS reopen -> EXECUTE
```

Warehouse primary commit truth:

```text
matching same-transaction marker -> COMMITTED
marker absent                     -> UNRESOLVED
marker absent + independently certified no-late-commit proof -> NOT_COMMITTED
```

### PR #47 — approved Warehouse commit/recovery

`integration-warehouse-run` proves the same-transaction marker/recovery contract. The normal deterministic path deliberately simulates framework acknowledgement loss only **after** target transaction success:

```text
EXECUTE
 -> target mutation + marker commit
 -> journal UNKNOWN
 -> marker COMMITTED
 -> journal SUCCEEDED
 -> later SKIP_SUCCEEDED
```

Correct evidence label:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT
```

It does not prove an actual network/driver COMMIT fault.

### PR #49 — approved real-fault drill contract

Separate evidence kind and CLI:

```text
FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL
integration-warehouse-fault-drill-run
fabric_data_framework.warehouse_commit_fault_injectors
```

PASS requires an actually observed provider/driver exception, independently verified same fault identity, marker `COMMITTED`, durable journal `SUCCEEDED`, and later `SKIP_SUCCEEDED`. A normal transaction return can never PASS. Marker absence remains `UNRESOLVED`; fault injectors cannot manufacture `NOT_COMMITTED`.

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE AMBIGUOUS-COMMIT FAULT-DRILL RUNNER CONTRACT
```

No real approved fault drill is retained yet.

### PR #51 — session-termination absence certifier

New provider-specific module:

```text
recovery/fabric_warehouse_session_absence.py
```

Exports:

```text
FabricWarehouseSessionBinding
FabricWarehouseSessionState
FabricWarehouseSessionAuthority
SqlAlchemyFabricWarehouseSessionAuthority
FabricWarehouseSessionTerminationAbsenceCertifier
capture_fabric_warehouse_session_binding
```

This contract defines a narrow Fabric-specific no-late-commit proof. `safe_to_retry=true` is allowed only after:

```text
1. exact target connection_id + session_id captured on target connection before mutation
2. independent authority sees that exact connection/session after the ambiguous exception
3. open_transaction_count > 0
4. Admin KILL succeeds for that exact session
5. exact connection/session disappears
6. target marker is read again after termination
7. marker is still absent
```

Critical fail-closed cases:

```text
session already gone before inspection -> UNRESOLVED; may already have committed
open_transaction_count == 0            -> UNRESOLVED
connection/session mismatch            -> UNRESOLVED
DMV/KILL/post-check error              -> UNRESOLVED; exception type only
session remains observable             -> UNRESOLVED
post-KILL marker read fails            -> UNRESOLVED
marker appears during KILL race        -> NOT_COMMITTED forbidden
```

The exact session binding uses provider `connection_id` plus numeric `session_id`; numeric session ID alone is insufficient. The SQLAlchemy authority uses a separate connection and exact DMV filtering; `KILL` runs under AUTOCOMMIT.

Query Insights remains secondary only because completed history is eventually visible and cannot establish immediate no-late-commit safety.

Correct evidence label:

```text
IMPLEMENTED + CI PROVEN FABRIC WAREHOUSE SESSION-TERMINATION ABSENCE CERTIFIER CONTRACT
```

This is **not** a production-approved marker-absence certifier. It is not yet wired into an approved execution CLI with a separately controlled Admin credential and separate session-termination authorization.

Canonical runbook: `FABRIC_WAREHOUSE_SESSION_ABSENCE_CERTIFIER.md`.

## Approved evidence system

Canonical runbooks:

```text
DEV_INTEGRATION_EVIDENCE.md
APPROVED_CONTROL_PLANE_CERTIFICATION.md
APPROVED_PIPELINE_EVIDENCE.md
APPROVED_CAPTURE_EVIDENCE.md
APPROVED_WAREHOUSE_EVIDENCE.md
APPROVED_WAREHOUSE_FAULT_DRILL.md
FABRIC_WAREHOUSE_SESSION_ABSENCE_CERTIFIER.md
INTEGRATION_EVIDENCE_MERGE.md
```

Evidence remains exact-spec/exact-release. Required checks certify only on PASS. Strict staged merge rules remain:

```text
NOT_RUN = absence
one substantive result = retain unchanged
identical substantive duplicate = allowed
different rerun evidence = conflict
no latest/PASS-wins/FAIL-wins arbitration
```

## Still unproven in approved infrastructure

```text
enterprise Entra token acquisition
real workspace/item authorization smoke
real Fabric SQL Database / Azure SQL Database certification PASS
real approved Pipeline execution
real Copy Job capture + approved observation
real bounded Spark execution + approved observation
real Fabric Warehouse target+marker transaction
provider-specific live Warehouse COMMIT fault injector
retained real ambiguous Warehouse COMMIT/network-driver fault-drill PASS
live exact Warehouse session binding via selected driver
live Admin DMV observation / KILL / rollback proof
approved-run wiring with separate Admin credential and termination authorization
production-approved marker-absence certifier
live Kafka coordination if release scope includes Kafka
live Delta CDF bounded read/retention if release scope includes Delta
capacity/throttling/gateway behavior
backup/restore/HA/DR/monitoring/retention/governance evidence
complete exact-release approved DEV evidence bundle
```

Never upgrade CI/reference evidence to a live-service label without retained approved execution for the exact release hash.

## Exact next order

When approved enterprise inputs are available:

1. replace placeholder DEV release hash/item UUIDs with exact candidate values;
2. run real read-only item smoke;
3. run real production control-plane certification;
4. strict-merge prerequisite evidence;
5. run approved Pipeline;
6. run approved Copy Job + bounded Spark capture;
7. run approved Warehouse target+marker recovery;
8. if required, run provider-specific real ambiguous-COMMIT fault drill;
9. if `NOT_COMMITTED` recovery is required, run exact-session termination recovery under separately controlled Admin authority;
10. merge required evidence and pass `integration-evidence-validate --require-certified`;
11. prove Kafka/Delta live only if part of `0.4.0` public promise;
12. run exact-candidate release audit.

If real inputs remain unavailable, next reusable slice is **approved session-termination recovery wiring**. It must add a separate Admin DB URL environment-variable name and separate explicit authorization. Normal Warehouse mutation/fault authorization must never silently grant `KILL` authority.

## Repository boundaries

```text
fabric-data-framework  reusable semantics/runtime/transports/evidence/package
fabric-customer        domain/business config + bounded extensions
fabric-infra           optional capacity/workspace/infrastructure lifecycle
```

## Canonical recovery order

For a new conversation, read:

```text
README.md
CURRENT_STATUS.md
CHEATSHEET_PATTERN_ALIGNMENT.md
PRODUCTION_READINESS_AUDIT.md
DEV_INTEGRATION_EVIDENCE.md
APPROVED_CONTROL_PLANE_CERTIFICATION.md
APPROVED_PIPELINE_EVIDENCE.md
APPROVED_CAPTURE_EVIDENCE.md
APPROVED_WAREHOUSE_EVIDENCE.md
APPROVED_WAREHOUSE_FAULT_DRILL.md
FABRIC_WAREHOUSE_SESSION_ABSENCE_CERTIFIER.md
INTEGRATION_EVIDENCE_MERGE.md
GUARANTEE_COVERAGE.md
EXTENSION_MODEL.md
PROJECT_BLUEPRINT.md
PRODUCTION_REQUIREMENTS.md
CAPTURE_PATTERN_CATALOG.md
TARGET_OPERATION_IDEMPOTENCY.md
PROVIDER_NATIVE_RECOVERY.md
FABRIC_WAREHOUSE_TARGET_COMMIT_PROOF.md
CONTROL_PLANE_CERTIFICATION.md
RELATIONAL_RUNTIME_REPOSITORY.md
FABRIC_PIPELINE_BACKEND.md
FABRIC_CAPTURE_REST_TRANSPORTS.md
EXECUTION_ENGINE_STRATEGY.md
FABRIC_EXECUTION_MODEL.md
CDC_DESIGN.md
CONTROL_PLANE_DESIGN.md
REPOSITORY_STRUCTURE.md
CICD_DESIGN.md
ECOSYSTEM_BLUEPRINT.md
```

If docs disagree with code/tests, inspect implementation and repair docs before continuing.
