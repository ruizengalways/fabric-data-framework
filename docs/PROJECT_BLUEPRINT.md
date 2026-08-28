# fabric-data-framework — Project Blueprint

Status: Canonical
Last updated: 2026-08-28

## 1. Goal

Build a production-grade reusable Microsoft Fabric Data Engineering runtime consumed by domain repositories through explicit immutable versions.

The framework standardizes stable cross-domain correctness and operational behavior while domain transformations and business rules remain explicit in domain repositories.

The target is a Data Platform / Senior-Principal Data Engineering reference, not a collection of notebooks and not a BI demo.

## 2. Canonical reading order

New conversations and contributors should read:

1. `docs/ECOSYSTEM_BLUEPRINT.md` — three-repository ownership and ecosystem boundary.
2. `docs/PROJECT_BLUEPRINT.md` — framework architecture and roadmap.
3. `docs/PRODUCTION_REQUIREMENTS.md` — durable production capability/backlog matrix.
4. `docs/FABRIC_EXECUTION_MODEL.md` — Pipeline/Spark Job Definition/Notebook/Copy execution model.
5. `docs/REPOSITORY_STRUCTURE.md` — target package/test/Fabric-item ownership.
6. `docs/CONTROL_PLANE_DESIGN.md` — durable metadata/state/evidence model.
7. `docs/CICD_DESIGN.md` — immutable delivery/promotion model.
8. `docs/CURRENT_STATUS.md` — exact current implementation and next work.

GitHub documentation is project memory. If docs are stale relative to code/tests, inspect implementation and repair docs before continuing.

## 3. Design principles

1. Share versioned code, not a cross-domain shared runtime.
2. Metadata drives stable behavior; business logic remains domain code.
3. Capture and apply strategies are independent axes.
4. Semantic config, deployed snapshots, operational overrides and runtime state are separate concerns.
5. Dataset is the default failure/isolation boundary.
6. Quarantine, reconciliation, audit and recovery are execution semantics, not afterthoughts.
7. Stateful progress advances only after required target/reconciliation gates.
8. DEV/UAT/PROD promote the same immutable release identity while runtime state remains environment-local.
9. Correctness is proved with small deterministic scenarios before strategy breadth or scale claims.
10. Parent orchestration selects/coordinates datasets; it does not duplicate capture/apply algorithms.
11. Fabric is an execution/deployment adapter; provider-neutral correctness remains testable outside Fabric.
12. Activity/notebook count is not a professionalism metric; clear ownership, invariants and operational evidence are.
13. A production capability is not claimed merely because an interface/ADR exists; real Fabric/enterprise evidence is labeled separately.
14. Releases represent meaningful product milestones, not every small internal change.

## 4. Architecture ownership

The framework is evolving from the initial flat package into explicit production ownership areas:

```text
contracts       stable typed contracts and error taxonomy
metadata        loading/validation/effective config/hashing
capture         FULL/WATERMARK/SNAPSHOT/CDC/... source semantics
apply           APPEND/REPLACE/UPSERT/SCD1/SCD2/SNAPSHOT_DIFF
quality         DQ/quarantine/schema/reconciliation gates
data_plane      Bronze/staging/publication/row accounting
state           watermark/checkpoint/lease/idempotency transitions
orchestration   planning/dependencies/concurrency/aggregation
execution       dataset/step runner + execution backends
recovery        retry/backfill/replay/rebuild/unknown-outcome
control_plane   durable schema/repository/migrations/operator queries
observability   structured audit/events/metrics/status/errors
connectors      physical capability contracts and registry
adapters/fabric Pipeline/SJD/Notebook/Copy/Environment/Fabric run integration
delivery        release manifest/bindings/materialization/deployment/CLI
testing         deterministic framework certification utilities
```

See `docs/REPOSITORY_STRUCTURE.md` for the target tree and migration plan.

## 5. Current implemented baseline

The current source version is `0.4.0` development on `main`.

Implemented code already proves:

- typed dataset/config/runtime override contracts;
- infrastructure binding abstraction;
- logical relational control-plane schema;
- environment-local in-memory repository/state adapters;
- release/deployment provenance and delivery CLI;
- immutable `v0.3.0` wheel/checksum release path;
- composite `(watermark, tie_breaker...)` incremental selection;
- normalized Bronze envelope;
- reusable row DQ/quarantine primitives;
- deterministic reference SCD2 behavior;
- reconciliation/state-commit gate;
- one WATERMARK -> Bronze -> DQ -> SCD2 execution slice;
- metadata-driven multi-dataset dispatcher with dependency validation, bounded concurrency, fault isolation and aggregate pipeline status.

The current 44 tests are useful evidence, but they do **not** yet cover the full production requirement matrix.

## 6. Metadata contract

`DatasetConfig` and future split metadata contracts declare source/target identity, capture/apply strategy, business/merge keys, watermark/event-time semantics, schema contract, delete semantics, execution group/criticality/dependencies and DQ/reconciliation policy.

Runtime overrides remain allow-listed operational values only. Semantic changes such as merge keys, apply strategy, schema contract or delete behavior require source-controlled deployment.

Effective runtime semantics remain:

```text
DeployedDatasetDefinition
    + active approved RuntimeOverride(s)
    + RunRequest
    = immutable EffectiveDatasetConfig
```

The effective configuration is hashed and bound to run evidence.

## 7. Capture and apply strategy model

Capture:

```text
FULL
WATERMARK
SNAPSHOT
CDC
MIRROR
STREAM
```

Apply:

```text
APPEND
REPLACE
UPSERT
SCD1
SCD2
SNAPSHOT_DIFF
```

Examples:

```text
FULL       -> REPLACE
WATERMARK  -> UPSERT
WATERMARK  -> SCD2
SNAPSHOT   -> SNAPSHOT_DIFF -> SCD2/current-state apply
CDC        -> UPSERT
CDC        -> APPEND
STREAM     -> APPEND
```

A connector/product does not define a new semantic strategy when an existing strategy contract fits.

## 8. Production FULL refresh

FULL refresh is now a required first-class production template.

`FULL -> REPLACE` is not defined as `truncate + insert`.

Correctness boundary:

```text
create run / freeze source intent
  -> extract complete candidate
  -> isolated stage
  -> schema + completeness + DQ guards
  -> reconciliation
  -> safe/atomic publication
  -> commit run/state
  -> retain/clean staging according to recovery policy
```

An unexpected empty/incomplete extraction must not wipe a healthy target. Publication and recovery semantics must be explicit and testable.

`FULL/SNAPSHOT -> SNAPSHOT_DIFF` is a separate template because absence becomes deletion only after complete-snapshot evidence is established.

## 9. WATERMARK semantics

For `WATERMARK`, the framework orders source records by:

```text
(watermark_column, tie_breaker...)
```

and selects positions strictly greater than committed progress, with optional bounded overlap relying on idempotent apply.

Null/invalid watermark or tie-breaker values are capture-contract failures because the source position cannot be ordered safely.

Late/stale current-state behavior still requires broader explicit policy work.

## 10. Data quality, quarantine and reconciliation

Row-level quarantinable defects can be redirected with lineage while accepted rows continue when policy permits.

Batch/contract violations can block target/state progression.

Connection/permission/code failures are failures, not quarantine.

No silent loss:

```text
rows_read = rows_accepted + rows_quarantined + rows_intentionally_filtered
```

Reconciliation is part of successful completion for critical/stateful loads and may block state commit.

## 11. Stateful execution and recovery

Canonical state ordering:

```text
read committed state
  -> acquire lease / concurrency guard
  -> freeze source range/boundary
  -> execute idempotent mutation candidate
  -> reconcile
  -> publish/commit target
  -> commit framework state
  -> finalize audit
  -> release lease
```

Recovery modes:

```text
NORMAL
RETRY
BACKFILL
REPLAY
FULL_REBUILD
```

The next runtime milestone must implement attempt lineage, retryability, bounded backfill/replay and unknown-commit recovery.

## 12. Orchestration evolution

The merged dispatcher currently proves:

- deployed/effective metadata selection;
- execution-group/request filtering;
- dependency/cycle validation;
- bounded parallel execution;
- dataset exception isolation;
- dependent `BLOCKED` behavior;
- criticality-aware `SUCCESS/PARTIAL_SUCCESS/FAILED` aggregation.

The current `ThreadPoolExecutor` implementation is a reference backend, not the final definition of enterprise orchestration.

Target split:

```text
orchestration planner
  selection
  dependency graph
  ready waves
  aggregate policy
        |
        +--> in-process reference backend
        +--> Fabric Pipeline backend
```

This preserves deterministic unit testing while enabling Fabric-visible dataset execution.

## 13. Fabric execution boundary

Accepted in ADR 0007.

Fabric Data Factory Pipeline owns coarse orchestration, schedule/trigger, parameters, fan-out, child pipeline invocation and Fabric-visible activity status.

Preferred generic production Spark entrypoint: **Spark Job Definition**.

Notebook remains a supported thin interactive/smoke/diagnostic/exception execution surface and may be used in production where justified.

Fabric Copy/SQL/database-native execution is preferred where the task and correctness contract fit those engines better than Spark.

A child dataset pipeline may contain only one SJD/Notebook activity and still be professional if it is a thin execution adapter with durable framework audit/state. A single opaque notebook acting as the whole domain scheduler/runtime is not the target.

See `docs/FABRIC_EXECUTION_MODEL.md`.

## 14. Semantic template versus physical plan

Framework correctness and Fabric UI shape are separate concepts.

Example semantic profile:

```text
capture=FULL
apply=REPLACE
complete_snapshot_required=true
reconciliation=required
empty_source_guard=policy
```

Possible physical plans:

```text
Copy Activity -> SJD validate/publish
```

or:

```text
one SJD executes the complete bounded plan
```

or:

```text
Copy/Spark stage -> SQL publication
```

The framework should compile effective config into a provider-neutral `ExecutionPlan` and let adapters execute it without weakening semantic guarantees.

## 15. Control plane

The logical control-plane model continues to cover:

### Semantic/deployed configuration

```text
dataset
dataset_contract
load_policy
orchestration_policy
data_quality_policy
reconciliation_policy
runtime_override
```

### Runtime/recovery/deployment state

```text
watermark
dataset_state
dataset_lease
pipeline_run
dataset_run
step_run
reconciliation_result
quarantine_batch
schema_change
reprocess_request
deployment_history
```

The physical production repository adapter and schema-migration lifecycle remain future implementation; SQLite/in-memory evidence is not a Fabric production-store claim.

## 16. Observability and operator surface

Every production run should answer:

- which dataset/step/attempt failed and why;
- which source boundary/window/offset was processed;
- which framework version/domain release/config hash ran;
- source/stage/target/quarantine/delete row accounting;
- watermark/state before/after;
- reconciliation results;
- retryability/replayability;
- blocked dependency reason;
- original/reprocess lineage;
- Fabric pipeline/activity/SJD/notebook run correlation.

Future operator commands/surfaces include status, retry, backfill, replay, disable/cancel and bounded diagnostics.

## 17. Release and deployment model

`v0.3.0` is the current immutable released baseline and its GitHub UI release path has been proven end to end.

`main` currently declares `0.4.0` as an **unreleased development version**.

The project is intentionally **not publishing v0.4.0 now**. The next release should represent a larger production milestone rather than merely the dispatcher merge.

Before the next release, target at minimum:

- production package ownership restructure;
- provider-neutral `ExecutionPlan`;
- planner/backend orchestration separation;
- production FULL -> REPLACE;
- SNAPSHOT -> SNAPSHOT_DIFF;
- retry/backfill/replay attempt model;
- delete/schema-evolution contracts;
- Fabric Pipeline + SJD/Notebook/Copy adapter contracts;
- expanded certification/production-readiness documentation.

CDC may be included in that milestone or the following one depending on correctness scope.

Domains continue to exact-pin released framework versions; they do not consume framework `main`.

## 18. Testing/certification strategy

Tests evolve from a flat suite into:

```text
unit
contract
integration
certification
real Fabric smoke
```

A production guarantee should have a discoverable owner and executable proof.

Required representative certifications are maintained in `PRODUCTION_REQUIREMENTS.md`, including FULL replacement guards, watermark correctness, snapshot delete guards, CDC offsets, quarantine/replay, schema evolution, recovery and multi-dataset failure isolation.

## 19. Fabric/current service details

Microsoft Fabric service features and limits change. Current implementation decisions such as Pipeline activity limits, high-concurrency behavior, Environment library modes, SJD monitoring and Variable Library integration must be re-verified against Microsoft Learn when concrete adapters are implemented.

Do not encode current service limits as timeless architecture constants unless the runtime must enforce them and the value is versioned/isolated.

## 20. Current roadmap

### Completed foundation

- Phase 0 canonical ownership/docs.
- Phase 1 typed contracts/control-plane/deployment foundation.
- Phase 2 WATERMARK -> Bronze -> DQ/quarantine -> SCD2 -> reconciliation/state vertical slice.
- Phase 3 enterprise delivery spine and immutable `v0.3.0` release proof.
- Phase 4 metadata-driven dispatcher/failure isolation merged to `main`.

### Current milestone — production framework hardening

1. Restructure package/tests by production ownership.
2. Add `ExecutionPlan` and execution-step contracts.
3. Split orchestration planner from execution backend.
4. Implement FULL -> REPLACE with staging/completeness/empty-source/reconciliation/publication guards.
5. Implement SNAPSHOT -> SNAPSHOT_DIFF including delete guards.
6. Implement retry/backfill/replay/attempt/unknown-outcome semantics.
7. Implement explicit delete/schema evolution/late-out-of-order policy contracts.
8. Add connector capability model.
9. Add Fabric Pipeline/SJD/Notebook/Copy/Environment adapter contracts.
10. Add real Fabric DEV integration only after the generic runtime contract is stable.
11. Add CDC/UPSERT and bootstrap-CDC correctness slice.
12. Add physical persistent control-plane adapter and operational queries.
13. Add lightweight streaming later.
14. Keep `fabric-infra` Terraform deferred until data-platform runtime is proven in the company Fabric estate.

## 21. Documentation obligation

Every coherent implementation slice updates `docs/CURRENT_STATUS.md`; architecture decisions update this blueprint/ADRs; newly discovered production requirements update `docs/PRODUCTION_REQUIREMENTS.md`.

Routine work inside accepted architecture should proceed without asking for approval after every file.