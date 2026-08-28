# fabric-data-framework — Project Blueprint

Status: Canonical
Last updated: 2026-08-29

## 1. Goal

Build a production-grade reusable Microsoft Fabric Data Engineering runtime consumed by domain repositories through explicit immutable framework versions.

The framework standardizes mature cross-domain correctness and operational behavior. Domain repositories declare business semantics, mappings/rules and bounded extensions. The target is a Senior/Principal Data Engineering / Data Platform reference, not a notebook collection and not a BI demo.

Primary product test:

> After an enterprise installs a released framework wheel, ordinary datasets should be onboarded through metadata, environment bindings and bounded domain extensions rather than edits to `fabric-data-framework`.

## 2. Canonical reading order

1. `docs/ECOSYSTEM_BLUEPRINT.md`
2. `docs/PROJECT_BLUEPRINT.md`
3. `docs/PRODUCTION_REQUIREMENTS.md`
4. `docs/EXECUTION_ENGINE_STRATEGY.md`
5. `docs/FABRIC_EXECUTION_MODEL.md`
6. `docs/REPOSITORY_STRUCTURE.md`
7. `docs/CONTROL_PLANE_DESIGN.md`
8. `docs/CICD_DESIGN.md`
9. `docs/PRODUCTION_READINESS_AUDIT.md`
10. `docs/GUARANTEE_COVERAGE.md`
11. `docs/CURRENT_STATUS.md`

GitHub docs are project memory. If docs disagree with code/tests, inspect implementation and repair docs before further architecture work.

## 3. Repository ownership

```text
fabric-infra
  Fabric estate / capacity / workspace / RBAC / network / bindings

fabric-data-framework
  reusable semantic runtime + provider adapters + control-plane contracts

fabric-customer
  deployable Customer domain solution exact-pinning a released framework wheel
```

Dependency direction:

```text
fabric-infra -> environment contract
fabric-data-framework -> versioned package -> fabric-customer
```

Framework never depends on Customer. Share code, not runtime state.

## 4. Design principles

1. Capture semantics and apply semantics are independent.
2. Capture/movement engine and apply engine are independent.
3. Core mature DE semantics have framework-owned portable implementations.
4. Native Fabric features are capability-certified stage delegates.
5. One physical capture has one checkpoint authority.
6. Native/external capture crosses into framework semantics through typed evidence.
7. Semantic definitions, deployed metadata, runtime overrides and runtime state are separate.
8. Dataset is the default failure/retry boundary.
9. Quarantine, reconciliation and recovery are first-class runtime semantics.
10. State never advances on uncertain/failed completion without evidence.
11. Unknown target commit is reconciled before retry.
12. DEV/UAT/PROD promote immutable definitions/artifacts, never runtime rows.
13. Correctness is proven with deterministic small scenarios before scale claims.
14. Provider-neutral decisions are testable outside Fabric.
15. Releases represent coherent product milestones, not internal commit cadence.

## 5. Package ownership map

```text
contracts/
  stable typed handoff/planning/recovery contracts

metadata/
  capability profiles and semantic metadata resolution

capture/
  FULL / WATERMARK / SNAPSHOT / CDC / MIRROR / STREAM semantics

apply/
  REPLACE / UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF / future APPEND

quality/
  DQ / quarantine / schema / reconciliation

data_plane/
  Bronze / staging / publication evidence

orchestration/
  metadata selection / dependency / ready-wave decisions

execution/
  reference dataset runners and physical backend boundaries

recovery/
  retry / attempt lineage / reprocess / unknown outcome

adapters/fabric/
  provider request/evidence translation for Fabric stage execution

control_plane.py + repository.py
  semantic definitions, environment-local state/evidence, repository contracts

delivery.py / deployment.py / cli.py
  release identity / bindings / metadata materialization / delivery operations
```

## 6. Current unreleased baseline

Source version remains `0.4.0` development. `v0.3.0` is the latest immutable public release.

Latest green hardening head before documentation synchronization:

```text
commit a5da06294dfba0c5ae756dcc1d8814931feebec7
GitHub Actions 33179754372
139 tests passed
```

The branch now proves at reference/contract level:

- typed metadata/effective config/overrides;
- infrastructure bindings;
- composite WATERMARK + overlap;
- Bronze lineage;
- DQ/quarantine/accounting;
- guarded FULL -> REPLACE;
- guarded SNAPSHOT -> SNAPSHOT_DIFF;
- ordered SCD1;
- ordered UPSERT;
- bounded deterministic SCD2;
- metadata dispatcher/failure isolation;
- capture/apply engine separation;
- immutable ExecutionPlan;
- named engine/profile capability resolution;
- Dataflow incremental capture -> framework SCD1/UPSERT planning;
- CaptureReceipt;
- Fabric capture adapter contracts for Copy Job/Copy Activity/Dataflow/Spark;
- generic retry/backoff/attempt lineage;
- audited RETRY/BACKFILL/REPLAY/FULL_REBUILD request contracts;
- fail-closed unknown-commit recovery;
- relational environment-local recovery evidence;
- control-plane v2 development schema;
- immutable delivery/release contracts.

No current hardening test is equivalent to a real approved Fabric production run.

## 7. Semantic model

Capture:

```text
FULL | WATERMARK | CDC | SNAPSHOT | MIRROR | STREAM
```

Apply:

```text
APPEND | REPLACE | UPSERT | SCD1 | SCD2 | SNAPSHOT_DIFF
```

Capture/movement engine:

```text
FABRIC_COPY_JOB | FABRIC_COPY_ACTIVITY | DATAFLOW_GEN2 |
SPARK | FABRIC_MIRRORING | EXTERNAL_CDC | SQL | CUSTOM
```

Apply engine is selected independently.

Representative compositions:

```text
FULL      + Copy/Spark          -> REPLACE
WATERMARK + Dataflow/Copy/Spark -> UPSERT/SCD1/SCD2
CDC       + Copy Job/external   -> normalize CDC -> UPSERT/SCD1/SCD2
SNAPSHOT  + Copy/Spark          -> SNAPSHOT_DIFF
MIRROR    + Mirroring           -> canonical current/history apply
```

## 8. Framework-first native delegation

Canonical invariant:

```text
semantic contract
    -> framework portable implementation
    -> optional provider stage delegation if capability-certified
```

A native provider operation is represented through:

```text
ExecutionPlan unit
    -> provider request
    -> native run evidence
    -> validated framework evidence/receipt
    -> remaining semantic stages
```

Native capture status alone does not prove the whole dataset run succeeded.

## 9. Fabric capture adapter boundary

Current provider adapter package:

```text
adapters/fabric/contracts.py
adapters/fabric/adapter.py
```

Contracts:

```text
FabricCaptureRequest
FabricCaptureTransport
FabricNativeRunEvidence
FabricNativeRunStatus
```

Concrete capture adapters:

```text
CopyJobCaptureAdapter
CopyActivityCaptureAdapter
DataflowGen2CaptureAdapter
SparkJobCaptureAdapter
```

Adapter responsibilities:

- validate compiled unit engine/kind/roles;
- invoke injected transport;
- validate native status/evidence;
- fail closed on wrong landing/source/snapshot/bounds;
- produce immutable CaptureReceipt.

Transport responsibilities:

- authentication/client construction;
- actual REST/SDK/CLI invocation;
- run polling;
- provider response conversion to `FabricNativeRunEvidence`.

This split prevents provider APIs from becoming semantic framework logic.

## 10. Current-state apply

SCD1 and UPSERT share `apply/current_state.py`.

Certified shared correctness:

```text
composite key
ordered source position
latest incoming candidate
exact-rerun idempotency
stale IGNORE/ERROR
equal-position conflict failure
unordered changed update fail-closed by default
separate duplicate/superseded/stale metrics
```

UPSERT is not merely an alias for SCD1; they expose distinct semantic APIs while sharing the hard current-state primitive.

## 11. Recovery architecture

Recovery is layered:

```text
operator/system intent
  ReprocessRequest
       |
       v
attempt orchestration
  execute_with_retry
       |
       +-- DatasetAttemptLineage
       +-- DatasetRunAudit
       |
       v
strategy-specific executor
       |
       v
physical target/capture evidence
```

Failure classes:

```text
RETRYABLE
NON_RETRYABLE
UNKNOWN_OUTCOME
```

Unknown target commit:

```text
reconcile
  COMMITTED     -> converge success, no duplicate write
  NOT_COMMITTED -> retry may proceed
  UNRESOLVED    -> stop
```

This generic core is implemented. Strategy-specific source restaging/replay/rebuild remains a separate layer and is not yet complete.

## 12. Reprocess modes

```text
RETRY
  exact continuation from an original dataset run

BACKFILL
  explicit bounded lower/upper source range

REPLAY
  original run and/or quarantine identity

FULL_REBUILD
  explicit authoritative-reset intent before destructive reset/rebuild
```

A `ReprocessRequest` is immutable in semantics. Only lifecycle status/timestamps may change.

## 13. Control plane

Promotable definitions:

```text
dataset
dataset_contract
load_policy
ordering_policy
execution_policy
apply_execution_policy
orchestration_policy
data_quality_policy
reconciliation_policy
```

Environment-local state/evidence:

```text
schema_migration_history
runtime_override
watermark
dataset_state
dataset_lease
pipeline_run
dataset_run
dataset_attempt_lineage
capture_receipt
step_run
reconciliation_result
quarantine_batch
schema_change
reprocess_request
deployment_history
```

Runtime state is never promoted.

`dataset_attempt_lineage` is append-only evidence. `reprocess_request` records auditable operator/system intent and lifecycle.

## 14. Stateful execution invariant

For framework-owned progress:

```text
read committed state
  -> acquire concurrency guard
  -> freeze source boundary
  -> execute idempotent candidate/mutation
  -> reconcile
  -> prove target outcome
  -> commit next state
  -> finalize audit
```

For native/external progress:

```text
provider owns source checkpoint
  -> framework records provider receipt/checkpoint correlation
  -> downstream apply/reconciliation has independent failure/recovery semantics
```

The framework must never invent a competing source watermark simply because it owns downstream apply.

## 15. Dispatcher/orchestration

Reference planner/dispatcher proves:

- selection/group/request filters;
- dependency/cycle validation;
- bounded parallelism;
- sibling isolation;
- dependent BLOCKED;
- unrelated continuation;
- criticality-aware aggregate status.

`ThreadPoolExecutor` is reference execution only. Real Fabric Pipeline backend remains future work.

## 16. Many-table topology

Avoid both one handcrafted pipeline per table and one giant opaque source pipeline.

Use metadata-selected execution groups based on operational boundaries:

```text
source/gateway/concurrency
capture engine/profile
schedule/SLA
volume/runtime class
criticality/blast radius
dependency stage
capacity/network boundary
```

Ordinary new tables should change domain metadata, not framework algorithms.

## 17. Current P0 roadmap

1. CDC canonical I/U/D envelope + event identity/order.
2. CDC dedupe/conflict/poison-event behavior.
3. CDC checkpoint commit gate.
4. `CDC -> UPSERT/SCD1/SCD2` certification.
5. snapshot/bootstrap -> CDC no-gap/no-double-apply handoff.
6. complete strategy-specific recovery: retained ranges, quarantine replay, FULL_REBUILD execution, native-progress recovery.
7. APPEND identity/collision semantics.
8. schema evolution + broader temporal policies.
9. supported persistent control-plane repository/operator surface.
10. real Fabric transport/backend + DEV hybrid execution evidence.
11. final audit and release-scope decision.

## 18. Release model

- public baseline: `v0.3.0`;
- current source: unreleased `0.4.0`;
- domains formally consume exact released framework versions;
- same immutable artifact moves through environments;
- environment bindings differ, runtime state does not move.

Do not publish v0.4.0 until the release milestone contains real Fabric integration evidence and the remaining P0 correctness scope is explicitly closed or intentionally bounded.

## 19. Documentation obligation

Every substantive implementation slice updates `CURRENT_STATUS.md`. Architecture changes update this blueprint/ADR. Requirements/evidence changes update `PRODUCTION_REQUIREMENTS.md`, `GUARANTEE_COVERAGE.md` and `PRODUCTION_READINESS_AUDIT.md` in the same coherent branch.
