# Production Readiness Audit — fabric-data-framework

Status: Canonical evidence audit  
Last updated: 2026-08-30

## Evidence model

Keep these levels separate:

```text
1. portable semantic/runtime implementation
2. deterministic CI/reference proof
3. retained real provider/Fabric/database execution evidence
4. external enterprise controls
```

Green CI proves levels 1/2 only. Executable HTTP/SQL/evidence code is not live provider evidence until approved service runs are retained for the exact environment and release hash.

## Current release state

```text
latest public release = v0.3.0
source version        = 0.4.0 development / unreleased
current main          = f8c2f24264480613ca048aaece09371a72aa529a
latest CI             = Actions 33279105627
full test baseline    = 490
```

**Release decision: blocked.** The blocker is retained approved DEV execution/certification and enterprise controls, not another broad provider-neutral abstraction.

## Current assessment

```text
Portable semantic implementation                  STRONG / broad reusable slice
Deterministic CI                                  STRONG for implemented slices
Exact 14 cheatsheet semantic patterns             IMPLEMENTED + CI PROVEN reference
Semantic onboarding/overclaim guardrails          IMPLEMENTED + CI PROVEN reference
Snapshot -> CDC bootstrap                         IMPLEMENTED + CI PROVEN reference
Full baseline -> WATERMARK bootstrap              IMPLEMENTED + CI PROVEN reference
APPEND/REPLACE/UPSERT/SCD1/SCD2/SNAPSHOT_DIFF     IMPLEMENTED + CI PROVEN reference
Target-operation CAS journal                      IMPLEMENTED + CI PROVEN reference
Provider-native recovery contracts                IMPLEMENTED + CI PROVEN reference
Control-plane certification framework             IMPLEMENTED + CI PROVEN contract
SQLAlchemy relational runtime                     IMPLEMENTED + CI PROVEN relational runtime
Fabric Data Pipeline backend                      IMPLEMENTED + CI PROVEN backend
Copy Job REST transport                           IMPLEMENTED + CI PROVEN transport contract
Spark Job Definition REST transport               IMPLEMENTED + CI PROVEN transport contract
Fabric Warehouse commit proof                     IMPLEMENTED + CI PROVEN provider contract
Approved evidence harness/preflight               IMPLEMENTED + CI PROVEN contract
Read-only Fabric item smoke runner                IMPLEMENTED + CI PROVEN runner contract
Staged integration evidence merge                 IMPLEMENTED + CI PROVEN merge contract
Approved control-plane certification runner       IMPLEMENTED + CI PROVEN runner contract
Approved Fabric Pipeline evidence runner          IMPLEMENTED + CI PROVEN runner contract
Approved Copy/Spark capture evidence runner       IMPLEMENTED + CI PROVEN runner contract
Bounded capture observer/executionData extensions IMPLEMENTED + CI PROVEN contract
Real approved DEV Fabric execution                NOT YET PROVEN
Real production SQL backend                       NOT YET PROVEN
External enterprise controls                      EXTERNAL / NOT YET RETAINED
```

## Latest hardening milestones

```text
PR #32  Actions 33251177339 / 407 tests  approved-run preflight + item smoke
PR #34  Actions 33253215030 / 419 tests  exact 14 semantic presets
PR #35  Actions 33253394201 / 430 tests  semantic onboarding + CLI
PR #37  Actions 33253581049 / 441 tests  full-baseline -> WATERMARK bootstrap
PR #39  Actions 33253817758 / 455 tests  strict staged evidence merge
PR #41  Actions 33254804867 / 466 tests  approved control-plane certification runner
PR #43  Actions 33255472348 / 477 tests  approved Pipeline runner
PR #45  Actions 33279105627 / 490 tests  approved Copy/Spark capture runner + bounded evidence extensions
```

Earlier provider/runtime baselines remain PR #17/#19/#21/#22/#24/#26/#28/#30.

## Capture/history truth

The framework separates source semantics, change granularity, read strategy, delete semantics, Bronze meaning and provider family. All fourteen cheatsheet semantic rows are first-class at semantic/onboarding level.

```text
watermark/current state -> observed-change history ceiling
watermark + soft delete -> delete correctness depends on tombstone retention/extraction
net CDC -> batch/window grain; collapsed intermediate changes cannot be reconstructed
snapshot history/diff -> snapshot grain
full ordered CDC/log/Debezium/CDF -> full captured event fidelity only under proven order/completeness/retention
API/files -> SOURCE_DEFINED until payload contract proves stronger semantics
```

SCD2 never upgrades source fidelity.

## Bootstrap readiness

Provider-neutral deterministic contracts exist for:

```text
snapshot -> CDC
full baseline -> WATERMARK
```

Watermark bootstrap requires complete baseline, exact boundary consistency, deterministic ordering and post-boundary visibility proof. A generic timestamp is not automatically safe.

## Fabric Pipeline readiness

The established backend requires provider terminal state plus the exact durable framework child outcome. PR #43 connects that invariant to an approved exact-release runner.

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED PIPELINE RUNNER CONTRACT
```

No live exact-release Pipeline run is retained.

## Copy Job / Spark readiness

PR #45 adds `integration-capture-run` around the existing concrete transports and `FabricCaptureAdapter.execute_with_evidence()`.

Prerequisites:

```text
FABRIC_ITEM_READ PASS
CONTROL_PLANE_CERTIFICATION PASS
selected Copy/Spark check NOT_RUN
exact release/config bundle
physical workspace/item binding
fingerprinted customer extension artifact
explicit mutation authorization
```

The customer/domain extension package may supply only bounded provider/item-specific logic via:

```text
fabric_data_framework.capture_observers
fabric_data_framework.spark_execution_data
```

The release manifest must fingerprint the extension artifact used by the approved run. This records intended exact artifact provenance; it does not by itself prove what is deployed in a live Fabric Environment.

The framework still owns the provider call, one-shot execution, native evidence validation, `CaptureReceipt`, provider correlation and PASS/FAIL decision.

Copy Job:

```text
FABRIC_NATIVE progress owner
no framework source bounds or arbitrary runtime parameters
provider Completed -> observer -> native evidence -> verified receipt
```

Spark:

```text
FRAMEWORK progress owner
WATERMARK/CDC requires frozen upper bound
bounds/parameters require logical executionData resolver
capture-only evidence requires a dedicated EXTRACT+STAGE Spark unit
```

A combined Spark unit that also owns APPLY/RECONCILE/COMMIT_STATE is rejected for capture-only evidence.

Provider `Completed` plus observer exception, wrong landing, wrong framework bound, missing root activity, or inconsistent native/receipt identity cannot become PASS.

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED CAPTURE RUNNER CONTRACT
```

No live exact-release Copy Job or Spark run is retained.

## Fabric Warehouse target commit readiness

Preferred transaction:

```text
BEGIN TRAN
  target mutation
  framework target-side operation marker
COMMIT TRAN
```

The control-plane target-operation CAS remains execution/retry authority. Matching marker proves `COMMITTED`; marker absence remains `UNRESOLVED` unless an independently certified no-late-commit proof exists. Real transaction and ambiguous COMMIT/network drill remain unproven.

The next reusable code slice is the approved Warehouse transaction + ambiguous COMMIT drill runner. It must reuse this existing provider contract, not weaken it.

## Relational control-plane readiness

Production candidates remain:

```text
fabric_sql_database_v1
azure_sql_database_v1
```

PR #41 provides the approved execution bridge. Real selected-backend service/driver/auth/network execution and retained production-certified PASS remain missing.

## Approved evidence sequencing

Implemented stages:

```text
integration-run-preflight
integration-item-smoke-run
integration-control-plane-certify-run
integration-evidence-merge
integration-pipeline-run
integration-capture-run
integration-evidence-validate
```

Safe intended order:

```text
item read PASS
  -> control-plane certification PASS
  -> strict prerequisite merge
  -> approved Pipeline run
  -> approved Copy/Spark capture runs
  -> approved Warehouse transaction/ambiguous COMMIT drill
  -> complete exact-release manifest
```

## Real approved-environment gaps

Still missing retained evidence for the exact candidate:

```text
enterprise Entra token acquisition
real workspace/item authorization
real Fabric SQL Database or Azure SQL Database certification PASS
real approved Pipeline execution
real Copy Job execution + approved post-run observation
real bounded Spark execution + approved observation
real Fabric Warehouse target+marker transaction
ambiguous Warehouse COMMIT/network drill
production-approved marker-absence certifier
live Kafka consumer coordination if release scope includes Kafka
live Delta CDF bounded read/retention if release scope includes Delta
capacity/SKU/throttling/gateway behavior
backup/restore/HA/DR/monitoring/retention/governance controls
complete certified exact-release evidence bundle
```

## Next order

When approved real inputs are available:

1. set exact DEV candidate release hash and real item UUIDs;
2. run real item smoke;
3. run real production control-plane certification;
4. merge prerequisites;
5. run approved Pipeline;
6. run approved Copy Job and Spark capture stages with fingerprinted customer extension artifacts;
7. run Warehouse target+marker transaction and ambiguous COMMIT drill;
8. merge all required evidence and pass `--require-certified`;
9. prove Kafka/Delta only if part of `0.4.0` public scope;
10. run exact-candidate release audit.

If live inputs are unavailable, implement the approved Warehouse transaction + ambiguous COMMIT drill runner next.

## External controls this repo must not fake

Capacity/SKU/throttling, tenant/workspace provisioning, Entra/RBAC, private networking/gateway, secret authority, source CDC/CDF retention configuration, broker/database/API access, backup/restore/DR, monitoring/on-call, privacy/retention/governance and enterprise change controls remain external evidence.

## Release gate

`0.4.0` may be considered only when exact candidate code/tests/docs and retained approved evidence agree.

```text
CI PROVEN != FABRIC PROVEN
CI PROVEN != PRODUCTION DB PROVEN
provider contract != approved live service evidence
```
