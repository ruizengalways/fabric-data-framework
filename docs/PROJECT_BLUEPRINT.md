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
4. `docs/EXECUTION_ENGINE_STRATEGY.md` — framework-first semantics, physical engine selection and hybrid execution.
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
4. Physical capture/movement engine is independent from apply semantics.
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
contracts       stable typed contracts / execution plan / capture receipt / errors
metadata        loading / validation / effective config / hashing / capabilities
capture         FULL / WATERMARK / SNAPSHOT / CDC / MIRROR / STREAM semantics
apply           APPEND / REPLACE / UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF
quality         DQ / quarantine / schema / reconciliation gates
data_plane      Bronze / staging / publication / row accounting
state           watermark / checkpoints / leases / idempotency / transitions
orchestration   selection / dependencies / concurrency / aggregation
execution       dataset/step runner + physical backends
recovery        retry / backfill / replay / rebuild / unknown outcome
control_plane   durable schema / repository / migrations / operator queries
observability   audit / events / metrics / status / error taxonomy
connectors      physical source/target capability contracts
adapters/fabric Pipeline / Copy / Dataflow / SJD / Environment / run context
delivery        release manifest / bindings / metadata materialization / CLI
testing         deterministic certification scenarios/utilities
```

See `docs/REPOSITORY_STRUCTURE.md` for the evolving tree. Do not create empty directories merely to imitate the target diagram.

## 5. Current unreleased baseline

The source version is `0.4.0` development. `v0.3.0` remains the latest immutable public release.

Latest fully green implementation evidence before final documentation-audit commits:

```text
commit 82bf3d97e6e08e9620bacdd1de25a14a2f7d489c
GitHub Actions 33172961692
build wheel      SUCCESS
Python 3.11      SUCCESS
Python 3.13      SUCCESS
91 tests passed
```

The current hardening branch proves at reference/portable level:

- typed dataset/effective config and safe runtime overrides;
- logical infrastructure bindings;
- composite watermark/overlap selection;
- Bronze lineage envelope;
- DQ/quarantine/row accounting;
- deterministic SCD2;
- ordered/idempotent SCD1;
- guarded FULL -> REPLACE;
- guarded SNAPSHOT -> SNAPSHOT_DIFF;
- metadata-driven dispatcher/failure isolation;
- provider-neutral `ExecutionPlan` with native-capture/framework-processing stage split;
- engine + named capability profiles;
- Dataflow Gen2 incremental bucket capture profile feeding framework SCD1;
- progress-owner contract;
- `CaptureReceipt`;
- bounded logical-name extension registry;
- additive relational control-plane schema v2;
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
capture/movement execution engine
progress owner
named capability profile
logical extension references
```

Runtime overrides remain allow-listed operational knobs only. Merge keys, strategies, engine/profile identity, extension identity and other semantic choices require source-controlled deployment.

Effective runtime semantics:

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
FULL
WATERMARK
SNAPSHOT
CDC
MIRROR
STREAM
```

Apply semantics:

```text
APPEND
REPLACE
UPSERT
SCD1
SCD2
SNAPSHOT_DIFF
```

Physical capture/movement engines:

```text
FABRIC_COPY_JOB
FABRIC_COPY_ACTIVITY
DATAFLOW_GEN2
SPARK
FABRIC_MIRRORING
EXTERNAL_CDC
SQL
CUSTOM
```

Representative compositions:

```text
FULL       + Copy/Spark             -> REPLACE
WATERMARK  + Dataflow Gen2          -> framework SCD1
WATERMARK  + Copy Activity/Spark    -> framework UPSERT/SCD2
CDC        + Copy Job/Debezium      -> framework normalization -> UPSERT/SCD1/SCD2
SNAPSHOT   + Copy/Spark             -> SNAPSHOT_DIFF
MIRROR     + Mirroring              -> canonicalization/current/history apply
```

No connector/product name becomes a new semantic strategy when an existing contract fits.

## 8. Framework-first fallback and native delegation

ADR 0009 is canonical.

Core rule:

```text
semantic contract
    -> framework portable implementation
    -> optional native stage delegation when capability-certified
```

Native movement is strongly encouraged when it is the better connector/throughput/operational surface. But the framework must still be able to provide the reusable semantic behavior when a native feature does not cover the required target semantics.

Example:

```text
Dataflow Gen2 DateTime-bucket incremental refresh
    -> landing/staging
    -> CaptureReceipt
    -> framework SCD1
    -> reconcile/audit
```

Dataflow's destination bucket `replace` is not treated as generic SCD1. Likewise a Copy Job `merge`/`SCD2` feature is not assumed semantically equivalent without an explicit certified profile.

Progress ownership and apply ownership are independent. Example:

```text
capture progress owner = FABRIC_NATIVE
apply semantic owner   = framework SCD1
```

## 9. Named capability profiles

Physical services vary by connector/product/version/mode. Therefore capability registration is keyed by:

```text
(engine, profile_name)
```

rather than one optimistic capability per engine.

Default profiles are conservative. Specific profiles opt into additional certified capture behavior.

Current concrete example:

```text
DATAFLOW_GEN2 / dataflow_gen2_incremental_bucket_v1
```

certifies:

```text
WATERMARK capture/staging
FABRIC_NATIVE progress ownership
no composite-watermark guarantee
no claim that native target update is SCD1/UPSERT/SCD2
```

`AUTO` remains conservative and cannot silently select a named profile.

Future connector/version profiles must be backed by product documentation and eventually real adapter certification.

## 10. Production FULL refresh

`FULL -> REPLACE` is not `truncate + insert`.

Reference correctness:

```text
freeze complete snapshot evidence
  -> isolated candidate/stage
  -> DQ/accounting
  -> completeness + empty/drastic-drop guards
  -> reconciliation
  -> publish
  -> audit/state boundary
```

Unexpected zero/incomplete extraction must not wipe a healthy target.

## 11. SNAPSHOT_DIFF and deletes

Absence becomes deletion only after authoritative complete-snapshot evidence.

Current reference slice includes:

- complete snapshot requirement;
- null/duplicate key rejection;
- insert/update/delete derivation;
- delete disabled preservation;
- quarantine-aware delete blocking;
- delete-all/delete-fraction guards;
- reconciliation before publication.

General delete/tombstone/SCD2-close policies still need broader certification.

## 12. WATERMARK correctness

Framework-owned WATERMARK selection orders by:

```text
(watermark_column, tie_breaker...)
```

with optional overlap. Null/invalid ordering components are capture-contract failures.

Native engine profiles that cannot prove equivalent composite ordering are rejected for that metadata combination.

## 13. SCD1 current-state correctness

Current canonical reference SCD1 supports:

- composite merge key;
- ordered tuple from event time/version/sequence-like columns;
- newest event selection per incoming key;
- exact-rerun idempotency;
- stale update ignore/error policy;
- equal-position conflicting payload failure;
- changed unordered update fail-closed unless explicitly authorized;
- separate duplicate/superseded/stale evidence.

This is the required framework fallback behind native ingestion mechanisms.

UPSERT is the next P0 apply strategy and should share the same ordering/idempotency foundations without becoming an alias for SCD1 where semantics differ.

## 14. SCD2 correctness

SCD2 remains an apply/history semantic, not an ingestion architecture.

It may consume WATERMARK, CDC or snapshot-derived changes. The current deterministic reference implementation proves one-current-row and a bounded conflict/late-arrival scope. General late-history repair/restate remains future work.

## 15. Custom extensions

Finite reusable patterns belong in the framework. Genuine exceptions use bounded domain extensions.

Metadata stores stable logical names such as:

```yaml
extensions:
  parser: vendor_position_v2
  transform: weird_feed_v1
```

A domain wheel registers the implementation. Metadata must not become an arbitrary Python-code execution surface.

Extensions may handle custom capture/parsing/transform/DQ/specialized apply logic but may not bypass row accounting, reconciliation, publication/state boundaries, secrets/bindings or durable audit.

## 16. Orchestration

The reference dispatcher proves:

- deployed/effective metadata selection;
- execution-group/request filters;
- dependency and cycle validation;
- bounded parallel execution;
- dataset exception isolation;
- dependent `BLOCKED` outcome;
- unrelated sibling continuation;
- criticality-aware `SUCCESS/PARTIAL_SUCCESS/FAILED`.

`ThreadPoolExecutor` is a deterministic reference backend. Target architecture separates orchestration decisions from Fabric Pipeline execution.

```text
planner
  -> selection/dependencies/ready waves/aggregate policy
        +-> in-process reference backend
        +-> Fabric Pipeline backend
```

## 17. Many-table topology

Do not encode one pipeline per table or one giant source pipeline as a framework requirement.

For a source with many tables, use a small number of metadata-selected execution groups based on real operational boundaries:

```text
source/gateway/concurrency
capture engine
schedule/SLA
volume/runtime class
criticality/blast radius
dependency stage
capacity/network boundary
```

Example:

```text
pl_erp_daily
  +-- erp_full_reference
  +-- erp_incremental_current
  +-- erp_incremental_history
  +-- erp_cdc_transactional
  +-- erp_custom_complex
```

## 18. Control plane

Control-plane schema v2 distinguishes promotable semantic definitions from environment-local runtime evidence.

Promotable definition families include:

```text
dataset
dataset_contract
load_policy
ordering_policy
execution_policy
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

Current SQLAlchemy/SQLite proof establishes schema/materialization contracts, not the final production Fabric control store.

## 19. Stateful execution and recovery

Canonical sequence:

```text
read committed state
  -> acquire lease/concurrency guard
  -> freeze source range/boundary
  -> execute idempotent candidate/mutation
  -> reconcile
  -> publish/commit target
  -> commit framework-owned state if applicable
  -> finalize audit
  -> release lease
```

Recovery modes are first-class vocabulary:

```text
NORMAL
RETRY
BACKFILL
REPLAY
FULL_REBUILD
```

But attempt lineage/backfill/replay/unknown-commit recovery is not yet certified end to end and is a P0 release gap.

## 20. Fabric execution boundary

Fabric Data Factory Pipeline owns coarse orchestration/trigger/control flow/fan-out/failure routing.

Spark Job Definition is the preferred generic headless Spark entrypoint once the adapter exists. Notebook remains a supported thin interactive/smoke/diagnostic execution surface. Copy Job/Copy Activity/Dataflow Gen2/SQL/Mirroring are valid stage executors where their capability profile matches the requested contract.

A child pipeline containing one SJD/Notebook activity can be professional if it is a thin bounded execution adapter with durable framework evidence. A single opaque notebook containing the whole platform scheduler is not the target.

## 21. Release/delivery model

- `v0.3.0` is the current immutable released baseline.
- `0.4.0` is unreleased development source.
- Domains exact-pin released framework versions; they do not consume framework `main` in formal delivery.
- Same immutable artifact is promoted DEV -> UAT -> PROD.
- Environment-specific physical bindings are resolved per environment.
- Runtime state is never promoted.

Do not publish `v0.4.0` until the production-readiness audit supports the chosen milestone.

## 22. Evidence and testing

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

`docs/GUARANTEE_COVERAGE.md` maps implemented guarantees to code/tests. `docs/PRODUCTION_READINESS_AUDIT.md` separates portable proof from real Fabric/enterprise evidence.

## 23. P0 roadmap from current head

1. ordered/idempotent framework UPSERT;
2. explicit apply executor/native-apply delegation decision separate from capture engine;
3. Fabric Copy Job/Copy Activity/Dataflow/Spark adapter contracts + `CaptureReceipt` correlation;
4. retry/backfill/replay/full-rebuild attempt lineage and unknown-outcome recovery;
5. CDC normalization/order/event identity/checkpoint + bootstrap handoff;
6. schema evolution and broader temporal conflict policies;
7. APPEND identity/collision semantics;
8. supported persistent control-plane repository/operator query surface;
9. first real Fabric hybrid DEV proof: native capture -> framework SCD1/UPSERT;
10. re-audit and only then select next release scope/version.

`fabric-infra` remains secondary while the data-framework product boundary is being proven; a company-provisioned Fabric estate can be used for the first adapter integration.

## 24. Documentation obligation

Every coherent implementation slice updates `CURRENT_STATUS.md`. Architecture changes update this blueprint and an ADR. Newly discovered requirements update `PRODUCTION_REQUIREMENTS.md`. Evidence changes update both audit documents.

Routine work within accepted architecture proceeds without approval after every file.
