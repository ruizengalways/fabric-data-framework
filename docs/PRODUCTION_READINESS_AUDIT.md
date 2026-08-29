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
current code baseline = e7bd8b7c55c5acdf14c58c24085c30e104edf0d6  (PR #47 merge)
latest code CI        = Actions 33279727906
full test baseline    = 501
```

**Release decision: blocked.** The blocker is retained approved DEV execution/certification and enterprise controls, not another broad provider-neutral abstraction.

## Current assessment

```text
Portable semantic implementation                    STRONG / broad reusable slice
Deterministic CI                                    STRONG for implemented slices
Exact 14 cheatsheet semantic patterns               IMPLEMENTED + CI PROVEN reference
Semantic onboarding/overclaim guardrails            IMPLEMENTED + CI PROVEN reference
Snapshot -> CDC bootstrap                           IMPLEMENTED + CI PROVEN reference
Full baseline -> WATERMARK bootstrap                IMPLEMENTED + CI PROVEN reference
APPEND/REPLACE/UPSERT/SCD1/SCD2/SNAPSHOT_DIFF       IMPLEMENTED + CI PROVEN reference
Target-operation CAS journal                        IMPLEMENTED + CI PROVEN reference
Provider-native recovery contracts                  IMPLEMENTED + CI PROVEN reference
Control-plane certification framework               IMPLEMENTED + CI PROVEN contract
SQLAlchemy relational runtime                       IMPLEMENTED + CI PROVEN relational runtime
Fabric Data Pipeline backend                        IMPLEMENTED + CI PROVEN backend
Copy Job REST transport                             IMPLEMENTED + CI PROVEN transport contract
Spark Job Definition REST transport                 IMPLEMENTED + CI PROVEN transport contract
Fabric Warehouse commit proof                       IMPLEMENTED + CI PROVEN provider contract
Approved evidence harness/preflight                 IMPLEMENTED + CI PROVEN contract
Read-only Fabric item smoke runner                  IMPLEMENTED + CI PROVEN runner contract
Staged integration evidence merge                   IMPLEMENTED + CI PROVEN merge contract
Approved control-plane certification runner         IMPLEMENTED + CI PROVEN runner contract
Approved Fabric Pipeline evidence runner            IMPLEMENTED + CI PROVEN runner contract
Approved Copy/Spark capture evidence runner         IMPLEMENTED + CI PROVEN runner contract
Approved Warehouse commit/recovery runner           IMPLEMENTED + CI PROVEN runner contract
Bounded customer extension surfaces                 IMPLEMENTED + CI PROVEN contract
Real approved DEV Fabric execution                  NOT YET PROVEN
Real production SQL backend                         NOT YET PROVEN
External enterprise controls                        EXTERNAL / NOT YET RETAINED
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
PR #45  Actions 33279105627 / 490 tests  approved Copy/Spark capture runner
PR #47  Actions 33279727906 / 501 tests  approved Warehouse commit/recovery runner
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

PR #45 adds `integration-capture-run` around the concrete transports and `FabricCaptureAdapter.execute_with_evidence()`.

Prerequisites include item-read PASS, control-plane certification PASS, selected Copy/Spark check still NOT_RUN, exact release/config bundle identity, physical workspace/item binding, fingerprinted customer extension artifact, and explicit execution authorization.

Copy Job retains `FABRIC_NATIVE` progress ownership; Spark retains `FRAMEWORK` progress ownership and requires frozen upper bounds for WATERMARK/CDC approved evidence. Provider `Completed` plus observer exception, wrong landing/bounds, missing root activity, or inconsistent native/receipt identity cannot become PASS.

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED CAPTURE RUNNER CONTRACT
```

No live exact-release Copy Job or Spark run is retained.

## Fabric Warehouse target commit readiness

Preferred target transaction:

```text
BEGIN TRAN
  bounded target mutation
  framework target-side operation marker
COMMIT TRAN
```

The control-plane target-operation CAS remains execution/retry authority. Provider-native marker semantics remain:

```text
matching marker -> COMMITTED
marker absent -> UNRESOLVED
marker absent + independently certified no-late-commit absence proof -> NOT_COMMITTED
```

PR #47 adds the exact-release approved runner around this contract. The framework owns the transaction, marker write, journal state transitions, probe/reconciliation and PASS/FAIL decision. A fingerprinted customer extension may only perform the bounded target mutation using the supplied existing SQLAlchemy `Connection`.

The deterministic normal path commits target+marker, then deliberately simulates framework ACK loss and proves:

```text
UNKNOWN -> matching marker COMMITTED -> SUCCEEDED -> later SKIP_SUCCEEDED
```

Provider/driver exceptions around target execution also become UNKNOWN and are probed; provider exception text is not persisted. Matching marker permits reconciliation to SUCCEEDED. Marker absence remains UNRESOLVED and blocks blind retry.

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE COMMIT/RECOVERY RUNNER CONTRACT
```

Important boundary: simulated framework ACK loss is not a real driver/network COMMIT disconnect. A retained real fault-injection approved run is still required for that stronger claim. No live exact-release Fabric Warehouse proof is retained.

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
integration-warehouse-run
integration-evidence-validate
```

Safe intended order:

```text
item read PASS
  -> control-plane certification PASS
  -> strict prerequisite merge
  -> approved Pipeline run
  -> approved Copy/Spark capture runs
  -> approved Warehouse commit/recovery run
  -> complete exact-release manifest
```

The real ambiguous COMMIT fault-injection drill is a separate evidence claim and must not be inferred from the deterministic simulated ACK-loss path.

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
real ambiguous Warehouse COMMIT/network-driver fault-injection drill
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
4. strict-merge prerequisites;
5. run approved Pipeline;
6. run approved Copy Job and Spark capture stages with fingerprinted customer extension artifacts;
7. run approved Warehouse target+marker commit/recovery stage;
8. separately execute a real network/driver ambiguous COMMIT fault-injection drill if required;
9. merge all required evidence and pass `--require-certified`;
10. prove Kafka/Delta only if part of `0.4.0` public scope;
11. run exact-candidate release audit.

If live inputs are unavailable, the next reusable slice should close a remaining evidence boundary rather than duplicate the Warehouse runner—for example a controlled real-fault-injection harness or production-approved marker-absence certifier contract.

## External controls this repo must not fake

Capacity/SKU/throttling, tenant/workspace provisioning, Entra/RBAC, private networking/gateway, secret authority, source CDC/CDF retention configuration, broker/database/API access, backup/restore/DR, monitoring/on-call, privacy/retention/governance and enterprise change controls remain external evidence.

## Release gate

`0.4.0` may be considered only when exact candidate code/tests/docs and retained approved evidence agree.

```text
CI PROVEN != FABRIC PROVEN
CI PROVEN != PRODUCTION DB PROVEN
provider contract != approved live service evidence
```
