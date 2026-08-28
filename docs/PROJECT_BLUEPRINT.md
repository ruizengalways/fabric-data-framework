# fabric-data-framework — Project Blueprint

Status: Canonical
Last updated: 2026-08-29

## 1. Goal

Build a production-grade reusable Microsoft Fabric Data Engineering runtime consumed by domain repositories through explicit immutable framework versions.

The framework standardizes mature cross-domain correctness and operational behavior. Domain repositories declare business semantics, mappings/rules and bounded extensions. The target is a Senior/Principal Data Engineering / Data Platform reference, not a notebook collection and not a BI demo.

Primary product test:

> After an enterprise installs a released framework wheel, ordinary datasets should be onboarded through metadata, environment bindings, capability profiles and bounded domain extensions rather than edits to `fabric-data-framework`.

## 2. Canonical reading order

1. `docs/ECOSYSTEM_BLUEPRINT.md`
2. `docs/PROJECT_BLUEPRINT.md`
3. `docs/PRODUCTION_REQUIREMENTS.md`
4. `docs/EXECUTION_ENGINE_STRATEGY.md`
5. `docs/FABRIC_EXECUTION_MODEL.md`
6. `docs/CDC_DESIGN.md`
7. `docs/REPOSITORY_STRUCTURE.md`
8. `docs/CONTROL_PLANE_DESIGN.md`
9. `docs/CICD_DESIGN.md`
10. `docs/PRODUCTION_READINESS_AUDIT.md`
11. `docs/GUARANTEE_COVERAGE.md`
12. `docs/CURRENT_STATUS.md`

GitHub docs are durable project memory. If docs disagree with code/tests, inspect implementation and repair docs before further architecture work.

## 3. Repository ownership

```text
fabric-infra
  Fabric estate / capacity / workspace / RBAC / network / bindings

fabric-data-framework
  reusable semantic runtime + provider adapters + control-plane contracts

fabric-customer
  deployable domain solution exact-pinning a released framework wheel
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
3. Mature DE semantics have framework-owned portable implementations.
4. Native Fabric features are capability-certified stage delegates.
5. One physical capture has one authoritative source-progress owner.
6. Native/external capture crosses into framework semantics through typed evidence.
7. Provider CDC formats normalize into canonical framework events/positions before semantic apply.
8. Native/external source progress and downstream framework application progress are distinct.
9. Semantic definitions, deployed metadata, overrides and runtime state are separate.
10. Dataset is the default failure/retry boundary.
11. Quarantine, reconciliation and recovery are first-class semantics.
12. State never advances on uncertain/failed completion without evidence.
13. Unknown target commit is reconciled before retry.
14. DEV/UAT/PROD promote immutable definitions/artifacts, never runtime rows.
15. Correctness is proven with deterministic small scenarios before scale claims.
16. Provider-neutral decisions are testable outside Fabric.
17. Releases represent coherent product milestones, not commit cadence.

## 5. Package ownership map

```text
contracts/
  stable typed handoff/planning/recovery contracts

metadata/
  capability profiles and semantic metadata resolution

capture/
  FULL / WATERMARK / SNAPSHOT / CDC / bootstrap-CDC / MIRROR / STREAM semantics

apply/
  REPLACE / UPSERT / SCD1 / SCD2 / CDC apply / SNAPSHOT_DIFF / future APPEND

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

control_plane.py + control_plane_io.py + repository.py
  semantic definitions, environment-local state/evidence, persistence contracts

delivery.py / deployment.py / cli.py
  release identity / bindings / metadata materialization / delivery operations
```

## 6. Current unreleased baseline

Source version remains `0.4.0` development. `v0.3.0` is latest immutable public release.

Latest coherent implementation evidence before the current docs synchronization:

```text
465a2c1e9ddf25b0ace2293f578c2c5bb3a653ae
GitHub Actions 33216281126
171 tests passed
```

The branch now proves at reference/contract level:

- typed metadata/effective config/overrides;
- infrastructure bindings;
- composite WATERMARK + overlap;
- Bronze lineage;
- DQ/quarantine/accounting;
- guarded FULL -> REPLACE;
- guarded SNAPSHOT -> SNAPSHOT_DIFF;
- ordered SCD1 and UPSERT;
- deterministic SCD2;
- dispatcher/failure isolation;
- capture/apply engine separation;
- immutable ExecutionPlan;
- named engine/profile capability resolution;
- Dataflow incremental capture -> framework SCD1/UPSERT planning;
- CaptureReceipt;
- Fabric capture adapter contracts for Copy Job/Copy Activity/Dataflow/Spark;
- retry/backoff/attempt lineage;
- RETRY/BACKFILL/REPLAY/FULL_REBUILD request contracts;
- fail-closed unknown-commit recovery;
- relational environment-local recovery evidence;
- canonical CDC event/order/dedupe/bounded-window correctness;
- CDC -> UPSERT/SCD1;
- CDC -> SCD2;
- durable optimistic CDC downstream checkpoints;
- snapshot/bootstrap -> CDC no-gap/no-double-apply handoff;
- control-plane v2 development schema;
- immutable delivery/release contracts.

No current hardening test is equivalent to an approved real Fabric run.

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
CDC       + Copy Job/external   -> canonical CDC -> UPSERT/SCD1/SCD2
SNAPSHOT  + Copy/Spark          -> SNAPSHOT_DIFF
SNAPSHOT fence + CDC buffer     -> bootstrap -> steady-state CDC
MIRROR    + Mirroring           -> canonical current/history apply
```

## 8. Framework-first native delegation

```text
semantic contract
    -> framework portable implementation
    -> optional provider stage delegation if capability-certified
```

Provider boundary:

```text
ExecutionPlan unit
    -> provider request
    -> native/external evidence
    -> validated framework receipt
    -> remaining semantic stages
```

A native capture status alone does not prove the whole dataset run succeeded.

## 9. Fabric capture adapter boundary

Current provider adapter package contains typed request/evidence contracts and concrete capture adapters for Copy Job, Copy Activity, Dataflow Gen2 and Spark.

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
- provider response conversion.

Real transports remain unimplemented.

## 10. Current-state apply

SCD1/UPSERT share `apply/current_state.py` for ordered batch/current-state logic and `apply/cdc.py` for CDC current-state execution.

Certified current-state behavior includes composite keys, deterministic source order, rerun idempotency, stale/equal-position handling, target-only field retention, CDC INSERT/UPDATE/DELETE/reinsert and explicit delete policy.

UPSERT is not merely an alias for SCD1; they expose distinct semantic APIs while sharing hard correctness primitives.

## 11. CDC architecture

Canonical detail: `docs/CDC_DESIGN.md`.

Provider-specific coordinates normalize into:

```text
CDCSourcePosition(partition, integer tuple)
CDCEvent
CDCCheckpoint
```

Normalization proves event identity, duplicate/conflict behavior, frozen upper boundary, completeness and deterministic order. Ambiguous shared positions or same-key cross-partition ordering fail closed.

Target apply remains independently selected:

```text
CDC -> UPSERT
CDC -> SCD1
CDC -> SCD2
```

For SCD2:

```text
source position -> event order
event_time      -> valid interval
```

Retroactive valid-time history correction is currently rejected rather than silently rewritten.

## 12. Snapshot/bootstrap -> CDC

Certified reference protocol:

```text
retain CDC from S
S <= snapshot consistency checkpoint B
complete snapshot consistent through B
apply/publish snapshot
CDC <= B -> ignore as snapshot-covered overlap
CDC >  B -> apply
```

Current proof rejects partition-set change during handoff.

## 13. Recovery architecture

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

Generic core is implemented. Strategy/provider-specific source restaging/replay/rebuild remains partial.

## 14. Reprocess modes

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

Reprocess semantic identity is immutable; lifecycle status/timestamps may change.

## 15. Control plane

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
cdc_checkpoint
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

`cdc_checkpoint` records downstream framework CDC application positions, committing dataset run and optimistic-concurrency version. It is not a replacement for FABRIC_NATIVE/EXTERNAL source checkpoint authority.

Runtime state is never promoted.

## 16. Stateful execution invariant

Framework-owned progress:

```text
read committed state/version
  -> concurrency guard
  -> freeze source boundary
  -> idempotent candidate/mutation
  -> reconcile/prove target outcome
  -> commit next state
  -> finalize audit
```

Native/external progress:

```text
provider owns source checkpoint
  -> framework records receipt/native correlation
  -> framework downstream apply has independent checkpoint/recovery
```

## 17. Dispatcher/orchestration

Reference planner/dispatcher proves selection/group filters, dependency/cycle validation, bounded parallelism, sibling isolation, dependent BLOCKED, unrelated continuation and criticality-aware aggregate status.

`ThreadPoolExecutor` remains reference execution only. Real Fabric Pipeline backend is future work.

## 18. Many-table topology

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

## 19. Current P0 roadmap

CDC semantic core/checkpoint/bootstrap are complete at reference level. Current sequence:

1. selected built-in/provider CDC envelope adapters + capability profiles;
2. provider-specific CDC source-offset resume/commit recovery;
3. quarantine REPLAY + FULL_REBUILD execution;
4. APPEND identity/collision semantics;
5. file manifest + API pagination/window capture guardrails;
6. schema evolution + broader temporal policies;
7. supported persistent control-plane/operator surface;
8. real Fabric transport/backend + DEV hybrid execution evidence;
9. final audit and release-scope decision.

## 20. Release model

- public baseline: `v0.3.0`;
- current source: unreleased `0.4.0`;
- domains formally consume exact released framework versions;
- same immutable artifact moves through environments;
- environment bindings differ; runtime state never moves.

Do not publish v0.4.0 until the agreed milestone includes real Fabric integration evidence and remaining P0 correctness is explicitly closed or intentionally bounded.

## 21. Documentation obligation

Every substantive implementation slice updates `CURRENT_STATUS.md`. Architecture changes update this blueprint/ADR. Requirements/evidence changes update `PRODUCTION_REQUIREMENTS.md`, `GUARANTEE_COVERAGE.md`, `PRODUCTION_READINESS_AUDIT.md` and relevant strategy docs in the same coherent branch.
