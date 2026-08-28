# Production Requirements — fabric-data-framework

Status: Canonical requirements baseline
Last updated: 2026-08-28

## 1. Purpose

This document is the durable production-requirements backlog for `fabric-data-framework`.

The framework is not considered production-grade merely because a Python algorithm exists or because a Fabric item can be created. A capability must be explicit about four separate evidence levels:

1. **portable semantics** — reusable correctness contracts implemented and tested independent of Fabric;
2. **Fabric adapter** — the semantics can be executed through supported Fabric items/APIs without duplicating business logic;
3. **Fabric integration evidence** — the adapter has executed against a real approved Fabric estate and retained run/deployment evidence;
4. **external enterprise control** — identity, networking, secrets, governance, retention, incident management, approvals and capacity policy supplied by the company/platform authority.

Do not collapse these levels into one `production-ready` label.

## 2. Status vocabulary

- `IMPLEMENTED` — canonical framework owner and executable proof exist at the stated scope.
- `PARTIAL` — useful behavior exists but one or more required correctness/operability paths are missing.
- `PLANNED` — required by the target architecture but not implemented yet.
- `EXTERNAL` — must integrate with an enterprise/Fabric authority rather than be invented by this repository.

## 3. Product boundary

The framework owns reusable Data Engineering behavior shared by domains. Domain repositories own business semantics and physical domain item definitions. `fabric-infra` or an existing enterprise platform owns Fabric estate provisioning and security primitives.

The framework must not become:

- a company-specific domain application;
- a home-grown identity/RBAC/secrets system;
- a fake enterprise incident-management system;
- a generic infrastructure factory for every cloud/Fabric topology;
- a visual-pipeline generator that encodes business logic in hundreds of activity definitions.

## 4. Source and extraction correctness

Required capabilities:

| Requirement | Status | Production expectation |
|---|---|---|
| Stable source boundary | PARTIAL | Every bounded run must know what source state/window it intended to read. |
| Complete snapshot evidence | PLANNED | FULL/SNAPSHOT must distinguish a complete authoritative snapshot from an extraction failure/partial result. |
| Composite watermark | IMPLEMENTED | `(watermark, tie_breaker...)` ordering prevents same-timestamp loss. |
| Watermark overlap | IMPLEMENTED contract; more integration needed | Bounded re-read must rely on idempotent apply and preserve committed progress on failure. |
| Ordered CDC offsets | PLANNED | Freeze upper offset, preserve event order/identity, support poison-event evidence and safe offset commit. |
| Bootstrap snapshot -> CDC | PLANNED | Define handoff coordinate so changes during bootstrap are neither lost nor applied twice. |
| Append-only identity | PLANNED | Exact replay succeeds; same identity with different payload fails closed. |
| File/object manifest freeze | PLANNED | Object ingestion should use an immutable/versioned manifest or readiness protocol, not an unreproducible mutable wildcard listing. |
| API pagination/window guardrails | PLANNED | Cursor loop detection, max pages, retry-after/backoff and replay-stable window semantics. |

Extraction failure must never masquerade as a valid empty business snapshot.

## 5. Capture strategy families

Canonical capture strategies remain independent from target apply strategies:

- `FULL` — complete authoritative state read.
- `WATERMARK` — bounded incremental read using a reliable ordered boundary.
- `SNAPSHOT` — complete versioned snapshot used for diff/history semantics.
- `CDC` — ordered bounded change-log consumption.
- `MIRROR` — Fabric/provider-managed replication when the source capability and governance model justify it.
- `STREAM` — streaming/event transport; secondary until the batch/control model is mature.

A physical connector does not define a new semantic strategy. SQL Server, PostgreSQL and SaaS systems may all implement the same capture family when they satisfy the same correctness contract.

## 6. Apply strategy families

Required target strategies:

- `APPEND` — append-once identity with duplicate/collision policy.
- `REPLACE` — staged, validated and safely published full replacement.
- `UPSERT` — freshness/ordering-aware merge with retry/idempotency semantics.
- `SCD1` — current-state dimensional update semantics.
- `SCD2` — temporal history with deterministic effective intervals.
- `SNAPSHOT_DIFF` — deterministic I/U/D derivation from complete snapshots with delete guards.

`CDC != SCD2`. `FULL != REPLACE`. Capture and apply are composed by metadata and validated for compatibility.

## 7. Full-refresh correctness

`FULL -> REPLACE` is a first-class production template, not just `truncate + insert`.

A production full refresh must support:

1. create run and freeze source intent;
2. extract into an isolated staging location/table/version;
3. validate schema and required contracts;
4. validate completeness and row-accounting guardrails;
5. run DQ/quarantine policy where applicable;
6. reconcile staged candidate against source/control expectations;
7. publish atomically or through an explicit swap/replace boundary;
8. retain enough previous-state/version evidence for recovery policy;
9. commit run/state only after successful publication and required reconciliation;
10. clean staging only when recovery/retention rules allow it.

An unexpected zero-row or dramatically incomplete source must not automatically wipe a healthy target. Guardrails must be policy-driven and auditable.

## 8. Snapshot-diff and delete correctness

`FULL/SNAPSHOT -> SNAPSHOT_DIFF` must prove snapshot completeness before interpreting absence as deletion.

Delete semantics are explicit metadata, not inferred ad hoc:

- no delete propagation;
- source tombstone -> soft delete;
- source tombstone -> hard delete where approved;
- snapshot absence -> delete only after completeness gate;
- SCD2 close-current semantics;
- downstream delete/restate policy.

Every delete-capable strategy requires delete counts in audit/reconciliation evidence and configurable delete-volume guardrails.

## 9. Stateful progress and concurrency

Required:

- environment-local committed state;
- proposed state separated from committed state;
- dataset lease or optimistic concurrency protection;
- target mutation + reconciliation + state-commit ordering;
- no state advancement after failed/uncertain completion;
- explicit handling of `target succeeded, state/audit outcome uncertain`;
- run/attempt lineage and idempotency keys;
- state reset/rebuild only through an audited recovery request.

State is operational data and must never be promoted from DEV to UAT/PROD.

## 10. Retry, recovery and reprocessing

Run modes are first-class:

- `NORMAL`
- `RETRY`
- `BACKFILL`
- `REPLAY`
- `FULL_REBUILD`

Required runtime behavior:

- classify failures as retryable/non-retryable/unknown;
- dataset-run attempts with stable parent lineage;
- bounded retry/backoff;
- exact source range/window retained for deterministic retry where possible;
- backfill range validation and overlap policy;
- quarantine replay preserving original and replay run lineage;
- operator reprocess requests with requester, reason, scope and approval reference where required;
- recovery from unknown commit outcome using idempotency/reconciliation rather than blind duplicate writes.

Code rollback, deployment rollback and data recovery remain distinct procedures.

## 11. Data quality and quarantine

Required:

- row-level rules with accepted/quarantined accounting;
- batch/contract rules that can block target/state;
- no connection/permission/code defect disguised as bad data;
- deterministic quarantine reason/rule/version;
- original run/source lineage;
- replay status and replay lineage;
- configurable progress policy after row quarantine;
- no silent loss:

```text
rows_read = rows_accepted + rows_quarantined + rows_intentionally_filtered
```

Sensitive quarantine access/retention is an external governance concern; the framework owns the lineage/control contract.

## 12. Reconciliation and completion gates

Reconciliation is part of success for stateful and critical loads.

Policy families should support:

- source/stage/target row counts;
- distinct/business key counts;
- accepted/quarantined balance;
- inserted/updated/deleted counts;
- hash/control totals where justified;
- snapshot completeness evidence;
- expected-versus-actual delete counts;
- SCD current-row uniqueness and temporal overlap checks;
- CDC offset/event accounting.

Policy determines `WARN`, `QUARANTINE`, `FAIL`, and whether state progression is allowed.

## 13. Schema contracts and evolution

Required:

- source schema fingerprint/version evidence;
- additive-compatible change policy;
- breaking-change classification;
- type widening/narrowing rules;
- missing/extra column policy;
- contract version binding to deployed metadata;
- schema-change audit;
- controlled dual-read/dual-write/cutover only when a concrete scenario requires it;
- rollback/rebuild implications documented before activation.

Do not silently auto-evolve every schema in production.

## 14. Late and out-of-order data

Required policies must distinguish:

- late but still inside accepted watermark overlap;
- stale update to mutable current-state data;
- out-of-order CDC event;
- late SCD2 historical observation;
- fact arriving before dimensional truth;
- exact duplicate replay;
- conflicting duplicate identity.

The framework must fail closed for unsupported temporal correction rather than produce plausible but wrong history.

## 15. Orchestration and dependency execution

The dataset remains the default fault boundary.

Required orchestration behavior:

- select deployed/effective metadata;
- enable/disable and execution-group filtering;
- dependency validation and cycle detection;
- bounded parallelism;
- source/capacity-aware concurrency policy;
- priority and criticality;
- sibling failure isolation;
- dependent `BLOCKED` outcomes;
- aggregate `SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`;
- timeout/cancellation propagation;
- pipeline/dataset/step correlation IDs;
- safe rerun of an execution group or bounded dataset set.

The framework should prefer explicit stages/execution groups and simple dependency rules before inventing a universal DAG scheduler.

## 16. Fabric execution model

Fabric is an execution/deployment adapter, not the owner of reusable correctness semantics.

The production reference must support these Fabric item roles:

- **Data Factory Pipeline** — trigger/schedule, control flow, fan-out, child-pipeline invocation, explicit activity-level visibility and failure routing.
- **Spark Job Definition (preferred headless batch entrypoint)** — packaged non-interactive Spark application that imports the released framework/domain wheels and executes one bounded job/request.
- **Notebook (supported thin interactive entrypoint)** — debugging, smoke tests, exploration and operator-assisted execution; may also be used as a pipeline activity when it is the justified runtime surface.
- **Copy Activity / Copy Job** — high-scale data movement when the scenario is movement-centric and supported connectors can satisfy the semantic boundary without custom Spark extraction.
- **SQL/Stored Procedure activities** — target-side SQL operations where the database engine is the appropriate execution owner.
- **Environment** — pinned runtime/compute/library snapshot for Spark workloads; production uses published stable library configuration.
- **Variable Library / environment binding** — non-secret environment-scoped values where supported; semantic dataset metadata remains source-controlled and versioned separately.

A Fabric pipeline with one Spark/Notebook activity is not automatically unprofessional. It is acceptable for a **thin child execution pipeline** if the reusable semantics live in the package and run/step evidence is durable. A domain-level production pipeline that is merely a single opaque notebook with no parameter, execution, failure, lineage or operational boundary is not the target architecture.

See `docs/FABRIC_EXECUTION_MODEL.md`.

## 17. Physical execution selection

The framework should compile effective dataset metadata into an execution plan independent of Fabric UI shape.

Representative execution kinds:

- `FABRIC_COPY`
- `SPARK_JOB_DEFINITION`
- `FABRIC_NOTEBOOK`
- `SQL_SCRIPT` / database-native execution
- future provider-managed replication adapter

Selection depends on source/target capabilities, transformation complexity, volume, security/network constraints, transaction semantics and cost — not on making the pipeline canvas visually busy.

## 18. Control plane

Logical entities include semantic/deployed metadata, operational state, run/evidence, recovery and deployment history.

Production requirements:

- schema migration lifecycle;
- immutable migration IDs/checksums;
- backward/forward compatibility rules for rolling deployment where needed;
- environment-local state isolation;
- durable repository adapter;
- transaction boundaries documented per state mutation;
- queryable operator/status surface;
- retention dependencies before destructive pruning;
- deployment/config provenance on every run.

The current SQLAlchemy/SQLite implementation is contract proof, not a claim that SQLite is the production Fabric control store.

## 19. Observability and operability

Every failed or delayed dataset must be explainable without reading notebook source code.

Required evidence includes:

- pipeline/dataset/step/attempt IDs;
- Fabric pipeline/activity/notebook/SJD run IDs when available;
- framework version, domain release/Git SHA and config hash;
- source boundary/window/offset;
- rows read/staged/accepted/quarantined/inserted/updated/deleted;
- watermark/state before and after;
- reconciliation results;
- schema version/change;
- duration by meaningful step;
- error category/code/message and retryability;
- blocked dependency reason;
- recovery/reprocess lineage.

Required operator capabilities eventually include `status`, `retry`, `backfill`, `replay`, `cancel/disable`, and bounded diagnostic views.

Logging text is not a substitute for durable operational state.

## 20. SLO and alerting hooks

Framework must expose enough structured state for domain/platform owners to define:

- freshness objective;
- runtime objective;
- consecutive-failure threshold;
- reconciliation objective;
- quarantine-rate threshold;
- dependency-block objective.

The actual monitoring/incident receiver and on-call roster are external by design.

## 21. Security and identity

Framework requirements:

- no credentials in semantic metadata;
- credential/connection references only;
- least-privilege execution assumptions documented;
- support Fabric Workspace Identity / service principal / approved organizational identity where the relevant API/activity supports it;
- never log secrets/tokens;
- quarantine and operator actions are auditable;
- physical identifiers resolved from environment bindings rather than baked into reusable semantic config.

Tenant settings, Entra policy, workspace RBAC, network/private-link design and secret authority are external/infrastructure-owned.

## 22. CI/CD and supply-chain requirements

Required:

- PR CI on supported Python versions;
- static checks and deterministic unit/contract tests;
- build-once immutable wheel;
- checksum/provenance evidence;
- exact framework version consumption by domains;
- release manifest with framework version, domain Git SHA, config hash and control-schema version;
- same artifact promoted through environments;
- no promotion of runtime state;
- Fabric item/environment definitions source controlled where supported;
- deployment adapter verifies item/environment binding after deployment;
- smoke/acceptance evidence before promotion.

A release is a milestone, not a mechanism for every small internal change. `main` may contain an unreleased development version while a larger production capability slice is being completed.

## 23. Performance, capacity and cost

Required framework design concerns:

- bounded dataset concurrency;
- source-specific throttling;
- Spark partition sizing and shuffle controls exposed through approved runtime policy rather than hard-coded globally;
- small-file/Delta maintenance strategy;
- session startup tradeoffs;
- high-concurrency/session-sharing only when workload isolation and monitoring remain acceptable;
- prefer Fabric-native Copy for movement-centric workloads when it is more appropriate than Spark;
- retain metrics needed to tune capacity from evidence.

Hard-coded production capacity/SKU/throughput targets are not owned by this repository without measured estate evidence.

## 24. Testing and certification

Test classes:

- unit — algorithms and pure contracts;
- contract — metadata/control-plane/adapter interfaces;
- strategy certification — each capture/apply guarantee and failure mode;
- integration — realistic storage/transaction/state behavior;
- recovery — retry/backfill/replay/unknown-outcome drills;
- orchestration — dependencies, partial failure, concurrency, cancellation;
- deployment — manifest/binding/schema migration/item definition;
- real Fabric smoke — only when approved Fabric estate is available.

A production guarantee should have a discoverable canonical owner and executable proof. Small deterministic data is preferred to benchmark-sized fixtures.

## 25. Representative certification matrix

The framework should eventually certify at least these bounded scenarios:

1. `FULL -> REPLACE`: normal refresh, empty-source guard, stage failure, publish failure, reconciliation failure, rerun.
2. `WATERMARK -> UPSERT/SCD2`: same-timestamp tie-breaker, overlap, stale row, duplicate rerun, failed state gate.
3. `SNAPSHOT -> SNAPSHOT_DIFF`: insert/update/delete, incomplete-snapshot delete guard, rerun.
4. `CDC -> UPSERT`: ordered I/U/D, duplicate event, poison event, offset/state uncertainty.
5. `BOOTSTRAP -> CDC`: snapshot/change-log handoff with no gap/double apply.
6. DQ/quarantine: row quarantine, batch quarantine, replay lineage.
7. schema evolution: additive accepted, breaking blocked/cutover-controlled.
8. recovery: retry attempt lineage, bounded backfill, replay, full rebuild.
9. multi-dataset orchestration: partial success, critical failure, dependency blocked, independent sibling continues.
10. Fabric adapter: pipeline -> SJD/notebook -> framework -> durable audit with Fabric run correlation.

## 26. Release threshold before next framework release

`v0.4.0` is intentionally **not** required immediately merely because `main` currently declares `0.4.0`.

Before the next public framework release, the target is to complete a materially broader product slice including at minimum:

- production-grade package/directory ownership structure;
- FULL -> REPLACE execution with guards/reconciliation;
- SNAPSHOT -> SNAPSHOT_DIFF representative execution;
- retry/backfill/replay attempt model;
- explicit delete and schema-evolution contracts;
- dispatcher integration with the new execution abstraction;
- Fabric execution contract with Pipeline + Spark Job Definition/Notebook roles documented and represented in code;
- updated production-readiness and guarantee coverage documentation.

CDC may land in the same milestone or the next one depending on correctness scope; do not rush a release to satisfy a version number.

## 27. Documentation obligation

New conversations must read this file together with:

- `docs/ECOSYSTEM_BLUEPRINT.md`
- `docs/PROJECT_BLUEPRINT.md`
- `docs/FABRIC_EXECUTION_MODEL.md`
- `docs/REPOSITORY_STRUCTURE.md`
- `docs/CONTROL_PLANE_DESIGN.md`
- `docs/CURRENT_STATUS.md`

When implementation contradicts documentation, inspect code/tests and repair canonical docs before continuing.