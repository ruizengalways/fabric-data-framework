# fabric-data-framework — Project Blueprint

Status: Canonical
Last updated: 2026-08-28

## 1. Goal

Build a production-grade reusable Microsoft Fabric data-engineering runtime package consumed by domain repositories through explicit immutable versions.

The framework standardizes stable cross-domain behaviour while domain transformations and business rules remain explicit in domain repositories.

## 2. Design principles

1. Share versioned code, not a cross-domain shared runtime.
2. Metadata drives stable behaviour; business logic remains code.
3. Capture and apply strategies are independent axes.
4. Git semantic configuration, deployed snapshots, operational overrides and runtime state are separate concerns.
5. Dataset is the default failure/isolation boundary.
6. Quarantine, reconciliation, audit and recovery are execution semantics, not afterthoughts.
7. Stateful progress advances only after required target/reconciliation gates.
8. DEV/UAT/PROD promote the same immutable release identity while runtime state remains environment-local.
9. Correctness is proved with small deterministic scenarios before strategy breadth or infrastructure scale.
10. Parent orchestration selects and coordinates datasets; it does not duplicate capture/apply algorithms.

## 3. Implemented package shape

```text
src/fabric_data_framework/
  config.py            typed semantic metadata + operational overrides
  infrastructure.py    logical Fabric resource resolution contract
  runtime.py           run context, statuses and state/watermark gates
  operations.py        audit, row accounting, quarantine and reconciliation contracts
  control_plane.py     logical relational control-plane schema
  deployment.py        provider-neutral release/deployment provenance
  delivery.py          release/config materialization and delivery helpers
  repository.py        control-plane repository protocol + thread-safe in-memory adapter
  dispatcher.py        metadata selection, dependencies, bounded concurrency, failure isolation
  watermark.py         composite incremental selection
  bronze.py            normalized Bronze envelope
  quality.py           reusable row validation/quarantine primitives
  scd2.py              deterministic SCD2 reference engine + in-memory target
  reconciliation.py    SCD2/reference completion gates
  execution.py         reference WATERMARK -> Bronze -> DQ -> SCD2 executor
  cli.py               provider-neutral delivery/control-plane CLI
```

The in-memory adapters are deliberate test/reference implementations, not the chosen enterprise Fabric physical store.

## 4. Metadata contract

`DatasetConfig` declares source/target identity, capture/apply strategy, business/merge keys, WATERMARK semantics, event time, tracked columns, execution group/criticality/dependencies and DQ/reconciliation policies.

Runtime overrides remain allow-listed operational values only. Semantic changes such as merge keys or apply strategy require source-controlled deployment.

Before execution, the dispatcher resolves one immutable `EffectiveDatasetConfig` per selected dataset from the deployed definition plus active valid overrides.

## 5. WATERMARK semantics

For `WATERMARK`, the framework orders source records by:

```text
(watermark_column, tie_breaker...)
```

and selects positions strictly greater than the committed position. This prevents data loss when multiple records share the same timestamp.

An optional overlap window re-reads a bounded datetime range and relies on idempotent target behaviour. Null watermark or tie-breaker values are rejected before mutation because their source position is not safely orderable.

## 6. Bronze contract

Captured rows are wrapped with normalized metadata including pipeline/dataset run IDs, source identity, ingestion timestamp, source commit time/sequence, operation and schema version. Domain/provider-specific envelopes do not leak into downstream strategy code.

## 7. Data quality and quarantine

Reusable `RowRule` execution separates accepted and quarantined Bronze records. Row-level quarantine is a handled outcome that can still permit state advancement when reconciliation accounts for it and policy allows it.

Batch-level quarantine remains a state-commit blocker. System/permission/code failures are failures, not quarantine.

## 8. SCD2 invariants

The reference SCD2 engine enforces:

- business key required;
- tracked-column hash determines change/no-change;
- unchanged tracked attributes do not create a new version;
- changed attributes close the current version and open one new current version;
- at most one current row per business key;
- exact rerun of an already-applied version is idempotent;
- a conflicting different row at the exact current effective timestamp fails explicitly;
- late/out-of-order event earlier than the current version fails explicitly until a later policy is implemented.

Delete policy and general late-arrival correction are intentionally not solved yet.

## 9. Dataset execution and dispatcher boundary

The proven reference dataset executor remains:

```text
resolve deployed config
  -> read committed watermark
  -> composite WATERMARK selection
  -> normalized Bronze records
  -> domain-supplied DQ rules
  -> row quarantine + lineage
  -> domain mapper
  -> calculate proposed SCD2 state
  -> reconcile row accounting + SCD2 invariant
  -> commit target
  -> commit watermark/state
  -> durable dataset/step audit
```

The metadata-driven dispatcher sits above strategy executors:

```text
pipeline request
  -> list deployed datasets
  -> resolve effective configs
  -> filter enabled / execution group / explicit request
  -> validate dependencies and cycles
  -> bounded parallel ready-set execution
  -> dataset-level outcome/audit
  -> block dependents of failed prerequisites
  -> continue unrelated branches
  -> aggregate SUCCESS / PARTIAL_SUCCESS / FAILED
```

The dispatcher passes a small immutable `DatasetDispatchRequest` to an executor resolved from metadata. It does not know WATERMARK/SCD2 internals. Future SNAPSHOT and CDC strategy executors plug into the same boundary.

HIGH and CRITICAL datasets are required by the current default aggregate policy. A non-success terminal outcome for one of those datasets causes final `FAILED`; failures isolated to lower criticalities produce `PARTIAL_SUCCESS` after eligible work finishes. This default is explicit and can later be policy-driven without changing executor algorithms.

If a prerequisite fails, only its dependent branch becomes `BLOCKED`; unrelated datasets remain eligible. Cycles and references to undeployed dependencies are orchestration-integrity errors and are rejected before unsafe execution.

## 10. Control-plane and environment model

The logical 19-table control-plane schema remains canonical. Repository contracts include dataset listing and pipeline-run recording required by the dispatcher. The reference in-memory adapter is lock-protected so bounded concurrency is tested against intentional shared-state semantics.

Each environment has independent state. CI/CD promotes schema/semantic definitions, never DEV watermarks/run history/overrides/quarantine state into UAT/PROD.

The current physical relational schema has not yet been expanded with every dispatcher aggregate count/error-summary field described in `CONTROL_PLANE_DESIGN.md`. That expansion belongs with a schema migration and real persistent repository adapter; the framework must not claim physical persistence that has only been proved in an in-memory result object.

## 11. Testing strategy and current evidence

Framework unit/contract/integration tests cover:

- Phase 1 metadata/override/control-plane/deployment contracts;
- duplicate timestamp/tie-breaker WATERMARK selection;
- no-new-row watermark preservation;
- SCD2 insert/change/unchanged/idempotent rerun;
- explicit late-arrival rejection;
- row-level quarantine with watermark advancement after accounting/reconciliation;
- reconciliation failure preserving target and committed watermark;
- non-critical dataset failure with sibling continuation and `PARTIAL_SUCCESS`;
- critical dataset failure with sibling continuation and final `FAILED`;
- dependency blocking without unrelated cancellation;
- executor exception isolation;
- bounded dispatcher concurrency;
- execution-group filtering;
- dependency-cycle rejection before execution.

Customer repository adds cross-package domain integration scenarios. The next domain proof is a tiny Customer multi-dataset graph consuming the released/merged dispatcher version.

## 12. Versioning and delivery

`0.1.0` established framework contracts. `0.2.0` added the first executable capture/Bronze/DQ/SCD2/reconciliation vertical slice. `0.3.0` established the enterprise delivery spine and is now frozen as immutable GitHub Release `v0.3.0` with wheel and portable checksum assets.

The 0.3.0 release path has been proven end to end: GitHub Actions UI initiation, release-candidate validation, wheel build, checksum verification, annotated tag creation, GitHub Release publication, and downstream Customer released-wheel integration.

Phase 4 dispatcher work is versioned as `0.4.0`. It is rebased on the released 0.3.0 baseline before merge so the immutable older release cannot absorb newer runtime semantics.

The delivery model remains:

```text
feature -> PR -> CI -> main -> immutable version/tag/artifact -> DEV -> UAT -> PROD
```

Domains exact-pin framework versions and upgrade explicitly.

## 13. Roadmap status

### Phase 0 — COMPLETE
Architecture, ownership and recoverable docs.

### Phase 1 — COMPLETE
Typed metadata/control-plane/runtime/deployment foundations.

### Phase 2 — COMPLETE
Reusable primitives required for one `crm.customer` WATERMARK -> Bronze -> validation/quarantine -> SCD2 -> reconciliation -> state-commit vertical slice.

### Phase 3 — COMPLETE AND RELEASED AS v0.3.0
Provider-neutral delivery spine, GitHub-hosted CI/release workflows, immutable release identity, metadata materialization, environment bindings and deployment-history contracts. Customer exact released-wheel integration has passed against the published framework artifact.

### Phase 4 — CURRENT
Metadata-driven multi-dataset dispatcher and failure isolation:

- effective metadata selection;
- execution groups and priorities;
- dependency validation/cycle detection;
- bounded parallel ready-set execution;
- dataset fault boundaries;
- dependent blocking;
- criticality-aware aggregate outcomes;
- pipeline/dataset lineage contracts.

After framework 0.4.0 CI/merge, add the smallest Customer multi-dataset scenario that proves this generic behaviour.

### Next runtime phases

1. retry/backfill/replay orchestration and attempt lineage;
2. FULL/SNAPSHOT -> SNAPSHOT_DIFF representative executor;
3. CDC normalization -> UPSERT representative executor;
4. delete, schema-evolution and late/out-of-order policies;
5. expanded persistent control-plane repository/migrations and operational query surface;
6. first real Fabric Environment + Notebook + Pipeline deployment/smoke adapter;
7. lightweight streaming slice after the batch/control-plane model is solid;
8. Terraform/infrastructure automation later in `fabric-infra`.

## 14. Documentation obligation

Every coherent implementation slice updates `docs/CURRENT_STATUS.md`; architecture changes update this blueprint/ADRs. Routine work inside accepted architecture does not stop for approval after every small file.
