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
current code baseline = 264c7547b4e70d24f258bdc3962af83d972e967d  (PR #49 merge)
latest code CI        = Actions 33282725576
full test baseline    = 513
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
Approved Warehouse ambiguous-COMMIT fault runner    IMPLEMENTED + CI PROVEN runner contract
Bounded customer extension surfaces                 IMPLEMENTED + CI PROVEN contract
Real approved DEV Fabric execution                  NOT YET PROVEN
Real production SQL backend                         NOT YET PROVEN
Real provider-specific ambiguous-COMMIT fault       NOT YET PROVEN
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
PR #49  Actions 33282725576 / 513 tests  approved Warehouse ambiguous-COMMIT fault drill
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

No live exact-release Fabric Warehouse proof is retained.

## Fabric Warehouse ambiguous-COMMIT fault readiness

PR #49 deliberately separates the stronger real-fault claim from the normal Warehouse evidence kind.

New evidence kind and command:

```text
FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL
integration-warehouse-fault-drill-run
```

A same-spec normal Warehouse PASS is a prerequisite before fault injection is even eligible. Both the mutation extension artifact and provider-specific fault-injector artifact must be fingerprinted in the exact release manifest, and fault injection requires a separate explicit authorization flag.

PASS requires the framework to observe all of these:

```text
fault armed for the exact operation/phase
execute_atomic actually raises a provider/driver exception
fault disarmed before marker probe
injector independently verifies the intended fault triggered
arm and verification fault identity agree
matching marker -> COMMITTED
journal -> SUCCEEDED
later claim -> SKIP_SUCCEEDED
```

Important fail-closed boundaries:

```text
normal transaction return -> fault drill FAIL
injector says triggered but no execution exception -> FAIL
exception + marker absent -> UNRESOLVED / UNKNOWN / FAIL
fault identity mismatch -> FAIL
fault injector cannot convert marker absence to NOT_COMMITTED
```

Execution, disarm, verification and Warehouse secondary-correlation provider errors retain exception type only, not raw provider text.

Correct label:

```text
IMPLEMENTED + CI PROVEN APPROVED WAREHOUSE AMBIGUOUS-COMMIT FAULT-DRILL RUNNER CONTRACT
```

The CI test that commits and then raises is a deterministic contract double. It proves the runner can distinguish and reconcile the shape of an ambiguous commit; it does **not** prove a real Fabric/network/driver disconnect occurred.

A stronger claim requires a retained exact-release approved run using a real provider-specific injector with durable fault identity/correlation evidence.

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
integration-warehouse-fault-drill-run
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
  -> optional stronger approved ambiguous-COMMIT fault drill
  -> complete exact-release manifest
```

The fault drill remains a separate evidence claim and must not be inferred from the deterministic simulated ACK-loss path.

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
provider-specific live Warehouse COMMIT fault injector
retained real ambiguous Warehouse COMMIT/network-driver fault-drill PASS
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
8. if required, install/fingerprint a provider-specific live fault injector and run the separate ambiguous-COMMIT drill;
9. merge all required evidence and pass `--require-certified`;
10. prove Kafka/Delta only if part of `0.4.0` public scope;
11. run exact-candidate release audit.

If live inputs are unavailable, do not duplicate the Warehouse or fault-drill runner. A possible remaining reusable slice is a production-approved marker-absence certifier contract, but only when a provider/session-specific no-late-commit proof is identified. `marker absent -> UNRESOLVED` must remain the default.

## External controls this repo must not fake

Capacity/SKU/throttling, tenant/workspace provisioning, Entra/RBAC, private networking/gateway, secret authority, source CDC/CDF retention configuration, broker/database/API access, backup/restore/DR, monitoring/on-call, privacy/retention/governance and enterprise change controls remain external evidence.

## Release gate

`0.4.0` may be considered only when exact candidate code/tests/docs and retained approved evidence agree.

```text
CI PROVEN != FABRIC PROVEN
CI PROVEN != PRODUCTION DB PROVEN
CI fault-drill contract != real ambiguous-COMMIT fault proof
provider contract != approved live service evidence
```
