# fabric-data-framework — Project Blueprint

Status: Canonical
Last updated: 2026-08-28

## 1. Goal

Build a production-grade reusable Microsoft Fabric Data Engineering runtime consumed by domain repositories through explicit immutable framework versions.

The framework standardizes mature cross-domain correctness and operational behavior. Domain repositories declare business semantics, mappings/rules and bounded extensions. The target is a Senior/Principal Data Engineering / Data Platform reference, not a collection of notebooks and not a BI demo.

Primary product test:

> After an enterprise installs a released framework wheel, ordinary new datasets should be onboarded through metadata, environment bindings and bounded domain extensions rather than edits to `fabric-data-framework`.

## 2. Canonical reading order

New conversations/contributors should read:

1. `docs/ECOSYSTEM_BLUEPRINT.md` — three-repository ownership.
2. `docs/PROJECT_BLUEPRINT.md` — architecture and roadmap.
3. `docs/PRODUCTION_REQUIREMENTS.md` — durable product requirement/backlog matrix.
4. `docs/EXECUTION_ENGINE_STRATEGY.md` — framework-first semantics and stage executors.
5. `docs/FABRIC_EXECUTION_MODEL.md` — Fabric Pipeline/SJD/Notebook/Copy execution boundaries.
6. `docs/REPOSITORY_STRUCTURE.md` — package/test ownership map.
7. `docs/CONTROL_PLANE_DESIGN.md` — metadata/state/evidence model.
8. `docs/CICD_DESIGN.md` — immutable delivery/promotion model.
9. `docs/PRODUCTION_READINESS_AUDIT.md` — evidence-level audit and release blockers.
10. `docs/GUARANTEE_COVERAGE.md` — guarantee -> code -> test map.
11. `docs/CURRENT_STATUS.md` — exact current branch evidence and next work.

GitHub documentation is project memory. If docs differ from code/tests, inspect implementation and repair docs before continuing.

## 3. Design principles

1. Share versioned code, not a cross-domain shared runtime.
2. Metadata drives stable reusable behavior; domain business semantics remain domain-owned.
3. Capture and apply are independent semantic axes.
4. Physical capture/movement executor and apply executor are independent decisions.
5. Core mature DE semantics have framework-owned portable fallback implementations.
6. Native Fabric features are capability-certified **stage delegates**, not the semantic foundation.
7. A physical capture has exactly one authoritative progress owner.
8. Native/external capture hands off through typed `CaptureReceipt` evidence.
9. Semantic config, deployed snapshots, runtime overrides and environment-local state are separate concerns.
10. Dataset is the default failure/isolation boundary.
11. Quarantine, reconciliation, audit and recovery are runtime semantics, not afterthoughts.
12. State advances only after the required target/reconciliation boundary succeeds.
13. DEV/UAT/PROD promote the same immutable release identity; runtime state stays environment-local.
14. Correctness is certified with small deterministic scenarios before scale claims.
15. Parent orchestration coordinates datasets; it does not duplicate capture/apply algorithms.
16. Fabric is an execution/deployment adapter; provider-neutral semantics remain testable outside Fabric.
17. Activity/notebook count is not a professionalism metric; ownership, invariants and evidence are.
18. A capability is not called production-ready merely because an interface or ADR exists.
19. Releases represent meaningful product milestones, not every internal commit.

## 4. Architecture ownership

Target ownership areas:

```text
contracts       typed contracts / execution plan / capture receipt / errors
metadata        loading / validation / effective config / hashing / capabilities
capture         FULL / WATERMARK / SNAPSHOT / CDC / MIRROR / STREAM
apply           APPEND / REPLACE / UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF
quality         DQ / quarantine / schema / reconciliation
data_plane      Bronze / staging / publication / row accounting
state           watermark / checkpoints / leases / idempotency / transitions
orchestration   selection / dependencies / concurrency / aggregation
execution       dataset/step runner + physical backends
recovery        retry / backfill / replay / rebuild / unknown outcome
control_plane   durable schema / repository / migrations / operator queries
observability   audit / events / metrics / status / errors
connectors      physical capability contracts
adapters/fabric Pipeline / Copy / Dataflow / SJD / Environment / run context
delivery        manifest / bindings / materialization / CLI
testing         deterministic certification scenarios/utilities
```

See `REPOSITORY_STRUCTURE.md` for the evolving tree. Do not create empty directories merely to imitate this ownership map.

## 5. Current unreleased baseline

The source version is `0.4.0` development. `v0.3.0` remains the latest immutable public release.

Latest coherent code/control-plane proof before the current documentation sync:

```text
commit 60d4d1362f504a51b3ecedfcb93c7c6ceb3d4578
GitHub Actions 33175724889
build wheel      SUCCESS
Python 3.11      SUCCESS
Python 3.13      SUCCESS
106 tests passed
```

The hardening branch now proves at reference/portable level:

- typed dataset/effective config and safe runtime overrides;
- logical infrastructure bindings;
- composite watermark/overlap selection;
- Bronze lineage envelope;
- DQ/quarantine/row accounting;
- deterministic SCD2;
- shared ordered current-state primitive;
- ordered/idempotent SCD1;
- ordered/idempotent UPSERT;
- guarded FULL -> REPLACE;
- guarded SNAPSHOT -> SNAPSHOT_DIFF;
- metadata-driven dispatcher/failure isolation;
- provider-neutral `ExecutionPlan`;
- independent capture and apply executor policies;
- engine + named capability profiles;
- Dataflow Gen2 incremental bucket capture feeding framework SCD1/UPSERT;
- progress-owner contract;
- `CaptureReceipt`;
- bounded logical-name extension registry;
- additive relational control-plane schema v2 including `apply_execution_policy`;
- metadata/release/deployment provenance and delivery CLI.

These reference guarantees do not yet equal a real enterprise Fabric production deployment. See `PRODUCTION_READINESS_AUDIT.md`.

## 6. Semantic metadata model

`DatasetConfig` currently declares or resolves:

```text
dataset/source/target identity
capture strategy
apply strategy
business + merge keys
watermark + tie-breaker + overlap
event time / version / sequence metadata
delete semantics
execution group / criticality / dependencies
DQ / reconciliation policy
capture/movement engine + profile
capture progress owner
apply engine + apply profile
logical extension references
```

Runtime overrides remain allow-listed operational knobs only. Keys, strategies, engine/profile identity, extension identity and other semantic choices require source-controlled deployment.

Effective semantics:

```text
DeployedDatasetDefinition
 + valid RuntimeOverride(s)
 + RunRequest/ReprocessRequest
 = immutable EffectiveDatasetConfig
```

The effective config receives a deterministic hash recorded in run evidence.

## 7. Capture, physical execution and apply are separate

Capture semantics:

```text
FULL | WATERMARK | SNAPSHOT | CDC | MIRROR | STREAM
```

Apply semantics:

```text
APPEND | REPLACE | UPSERT | SCD1 | SCD2 | SNAPSHOT_DIFF
```

Physical engines:

```text
FABRIC_COPY_JOB | FABRIC_COPY_ACTIVITY | DATAFLOW_GEN2 |
SPARK | FABRIC_MIRRORING | EXTERNAL_CDC | SQL | CUSTOM
```

Representative compositions:

```text
FULL       + Copy/Spark             -> REPLACE
WATERMARK  + Dataflow Gen2          -> framework SCD1/UPSERT
WATERMARK  + Copy Activity/Spark    -> framework UPSERT/SCD2
CDC        + Copy Job/Debezium      -> framework normalization -> UPSERT/SCD1/SCD2
SNAPSHOT   + Copy/Spark             -> SNAPSHOT_DIFF
MIRROR     + Mirroring              -> canonicalization/current/history apply
```

No connector/product name becomes a semantic strategy when an existing contract fits.

## 8. Framework-first fallback and native delegation

ADR 0009 is canonical:

```text
semantic contract
    -> framework portable implementation
    -> optional native stage delegation when capability-certified
```

Source-controlled execution policy explicitly separates:

```text
engine / capability_profile / progress_owner
    -> capture/movement

apply_engine / apply_capability_profile
    -> final-target apply
```

`AUTO` is allowed in policy but must resolve to concrete engines in the immutable `ExecutionPlan`.

Default apply resolution is SPARK/framework. Generic native/SQL profiles currently claim no final-target apply semantics. A future native apply delegate must explicitly list the requested `ApplyStrategy` in its capability profile.

## 9. Dataflow Gen2 hybrid pattern

Current named profile:

```text
DATAFLOW_GEN2 / dataflow_gen2_incremental_bucket_v1
```

certifies:

```text
WATERMARK capture/staging
FABRIC_NATIVE progress ownership
no composite-watermark guarantee
no native SCD1/UPSERT/SCD2 equivalence
```

Canonical hybrid:

```text
Dataflow Gen2 incremental
    -> landing/staging
    -> CaptureReceipt
    -> framework SCD1/UPSERT
    -> reconcile/state/audit
```

Dataflow bucket replacement is not mislabeled as generic SCD1. A capture profile cannot masquerade as an apply profile.

## 10. Current apply semantics

### REPLACE

`FULL -> REPLACE` uses complete-source evidence, isolated candidate, empty/drastic-drop guards, DQ/reconciliation and safe publication boundaries. Unexpected incomplete/empty source must not wipe a healthy target.

### SCD1 and UPSERT

Both use the shared ordered current-state primitive:

```text
composite merge key
(event_time?, version?, sequence?) ordering tuple
latest incoming candidate
exact rerun idempotency
stale IGNORE/ERROR
equal-position conflict fail-closed
unordered changed update fail-closed unless explicitly authorized
duplicate/superseded/stale evidence
```

SCD1 remains the dimensional current-state semantic name. UPSERT is the generic insert-or-update current-state semantic. They share hard correctness logic without collapsing their APIs.

### SCD2

SCD2 is an apply/history semantic, not an ingestion method. The current deterministic reference proves one-current-row and bounded conflict/late-arrival behavior. General late-history repair/restate remains future work.

### SNAPSHOT_DIFF

Absence becomes deletion only after complete-snapshot evidence. Current reference supports deterministic I/U/D, key validation, quarantine-aware delete blocking and delete-volume guards.

### APPEND

APPEND identity/collision semantics remain a required gap.

## 11. Named capability profiles

Capability registration is keyed by:

```text
(engine, profile_name)
```

Default profiles are conservative. Capture and apply are validated independently. Unsupported combinations fail before mutation. There is no hidden runtime fallback to a semantically weaker engine.

Future connector/product/version profiles must be backed by current documentation and then real adapter evidence before a Fabric-specific guarantee is claimed.

## 12. Orchestration and many-table topology

The reference dispatcher proves metadata selection, dependency/cycle validation, bounded parallelism, sibling failure isolation, dependent `BLOCKED`, unrelated sibling continuation and criticality-aware aggregate status.

`ThreadPoolExecutor` is a deterministic reference backend; Fabric Pipeline will be another execution backend for the same provider-neutral decisions.

For many-table sources use a small number of metadata-selected execution groups based on source/gateway limits, capture engine/profile, SLA, volume, criticality, dependency stage, network boundary and capacity. Do not require one bespoke pipeline per table or one giant opaque pipeline.

## 13. Control plane

Schema v2 promotable definitions include:

```text
dataset
dataset_contract
load_policy
ordering_policy
execution_policy            # capture/movement
apply_execution_policy      # apply
orchestration_policy
data_quality_policy
reconciliation_policy
```

Environment-local state/evidence includes:

```text
runtime_override
watermark
dataset_state
dataset_lease
pipeline_run
dataset_run
step_run
capture_receipt
reconciliation_result
quarantine_batch
schema_change
reprocess_request
deployment_history
```

Runtime state is never promoted across environments. SQLAlchemy/SQLite is contract proof, not the final production store.

## 14. Stateful execution and recovery

Canonical framework-owned state sequence:

```text
read committed state
  -> acquire lease
  -> freeze source range
  -> execute idempotent candidate/mutation
  -> reconcile
  -> publish/commit target
  -> commit framework state
  -> finalize audit
  -> release lease
```

Recovery modes are first-class vocabulary:

```text
NORMAL | RETRY | BACKFILL | REPLAY | FULL_REBUILD
```

Attempt lineage/backfill/replay/unknown-commit recovery is not yet certified end to end and remains P0.

## 15. Extensions

Finite reusable patterns belong in the framework. Genuine exceptions use bounded logical-name domain extensions for custom capture/parser/transform/DQ/specialized apply.

Extensions may not bypass row accounting, reconciliation, publication/state authority, secrets/bindings or durable audit. Metadata is not an arbitrary Python execution surface.

## 16. Fabric execution boundary

Fabric Data Factory Pipeline owns coarse trigger/orchestration/control flow. Spark Job Definition is the preferred generic headless framework Spark entrypoint once the adapter exists. Notebook remains a thin interactive/smoke/diagnostic or justified production surface. Copy Job/Copy Activity/Dataflow Gen2/SQL/Mirroring are valid stage executors only where their profiles fit.

A one-activity child pipeline can be professional if the activity is a thin bounded adapter and durable framework evidence exists. An opaque notebook owning the whole platform scheduler is not the target.

## 17. Release and delivery

- `v0.3.0` is the latest immutable public release.
- `0.4.0` is unreleased development source.
- domains exact-pin released framework versions;
- same immutable artifact is promoted DEV -> UAT -> PROD;
- environment bindings differ, semantic release identity does not;
- runtime state is never promoted.

Do not publish v0.4.0 merely because its version string exists.

## 18. Evidence and testing

Testing layers:

```text
unit
contract
reference integration
strategy certification
recovery certification
deployment certification
real Fabric smoke/integration
```

`GUARANTEE_COVERAGE.md` maps code/test owners. `PRODUCTION_READINESS_AUDIT.md` separates portable proof from real Fabric/enterprise evidence.

Latest coherent code/control-plane slice before docs sync:

```text
GitHub Actions 33175724889
106 tests passed
```

## 19. P0 roadmap from current head

UPSERT and explicit capture/apply executor separation are now **complete at reference level** and removed from the remaining roadmap.

Next:

1. Fabric Copy Job/Copy Activity/Dataflow/Spark adapter contracts + `CaptureReceipt`/native-run correlation;
2. retry/backfill/replay/full-rebuild attempt lineage and unknown-outcome recovery;
3. CDC normalization/order/event identity/delete/checkpoint + bootstrap handoff;
4. APPEND identity/collision semantics;
5. schema evolution and broader temporal correction policies;
6. supported persistent control-plane repository/operator query surface;
7. first real Fabric hybrid DEV proof: native capture -> framework SCD1/UPSERT;
8. re-audit and only then select next release scope/version.

`fabric-infra` remains secondary while the framework product boundary is being proven; a company-provisioned Fabric estate can support the first adapter integration.

## 20. Documentation obligation

Every coherent implementation slice updates `CURRENT_STATUS.md`. Architecture changes update this blueprint and an ADR. Requirements change `PRODUCTION_REQUIREMENTS.md`. Evidence changes update both audit documents.

Routine work inside accepted architecture proceeds without approval after every file.
