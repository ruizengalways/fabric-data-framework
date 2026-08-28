# Production Requirements — fabric-data-framework

Status: Canonical requirements baseline
Last updated: 2026-08-28

## 1. Purpose

This document is the durable production-requirements backlog for `fabric-data-framework`.

The framework targets a stable enterprise wheel: routine datasets should be onboarded through metadata, environment bindings and bounded extensions, not framework forks.

A capability has four distinct evidence levels:

1. **portable semantics** — framework-owned reusable contract/algorithm;
2. **deterministic certification** — executable reference/unit/contract proof;
3. **Fabric integration evidence** — executed through real approved Fabric items/APIs with retained native correlation;
4. **external enterprise controls** — identity, networking, secrets, governance, retention, incident response, approval and capacity policy supplied by the enterprise/platform authority.

Do not collapse these levels into one `production-ready` label. See `PRODUCTION_READINESS_AUDIT.md` and `GUARANTEE_COVERAGE.md`.

## 2. Status vocabulary

- `IMPLEMENTED` — portable owner + executable proof exist at the stated scope.
- `PARTIAL` — useful behavior exists but material required paths are missing.
- `PLANNED` — required but not implemented.
- `EXTERNAL` — must be proven by Fabric/enterprise authority rather than invented by this repository.

## 3. Product and delegation boundary

The framework owns reusable DE semantics. Domain repositories own business mappings/rules and bounded domain extensions. `fabric-infra` or an existing company platform owns Fabric estate/security primitives.

Accepted ADR 0009 establishes:

```text
core semantic contract
    -> framework-owned portable fallback implementation
    -> optional native stage delegation only when capability-certified
```

Physical stage ownership is independent:

```text
capture / movement
    != normalize / transform
    != apply
    != reconcile / state
```

A native Fabric feature must not become the only implementation of a core mature semantic pattern.

## 4. Source and capture correctness

| Requirement | Status | Production expectation |
|---|---|---|
| Stable source boundary | PARTIAL | Every bounded run knows the intended source state/window. Framework WATERMARK/FULL/SNAPSHOT slices do; CDC/file/API families remain. |
| Complete FULL snapshot evidence | IMPLEMENTED reference | Completeness is explicit adapter evidence; successful iteration is insufficient. |
| Complete SNAPSHOT evidence | IMPLEMENTED reference | Required before absence may mean deletion. |
| Composite watermark | IMPLEMENTED | `(watermark, tie_breaker...)` prevents same-timestamp loss for framework-owned bounds. |
| Watermark overlap | IMPLEMENTED reference | Bounded reread supported; final safety depends on idempotent apply/recovery. |
| CaptureReceipt | IMPLEMENTED contract | Native/external movement hands off run/landing/boundary/checkpoint evidence. |
| Single capture progress authority | IMPLEMENTED contract | Exactly one of FRAMEWORK/FABRIC_NATIVE/EXTERNAL owns the physical checkpoint. |
| Ordered CDC offsets/events | PLANNED | Freeze upper offset; preserve event identity/order; safe checkpoint commit. |
| Bootstrap snapshot -> CDC | PLANNED | Handoff coordinate prevents gaps/double apply. |
| File/object manifest freeze | PLANNED | Immutable/versioned manifest/readiness protocol. |
| API pagination/window guardrails | PLANNED | Cursor-loop/max-page/retry-after/replay-stable window behavior. |

Extraction failure must never masquerade as a legitimate empty business snapshot.

## 5. Capture strategy families

Canonical capture semantics:

```text
FULL
WATERMARK
SNAPSHOT
CDC
MIRROR
STREAM
```

A physical connector/product does not define a new semantic strategy when one of these contracts fits.

## 6. Apply strategy families

| Apply strategy | Status | Required semantics |
|---|---|---|
| APPEND | PLANNED | append-once event/row identity; exact replay idempotency; conflicting duplicate fails closed |
| REPLACE | IMPLEMENTED reference | isolated candidate, destructive guards, reconciliation, safe publication boundary |
| UPSERT | P0 PLANNED | ordered/freshness-aware current-state merge; retry/idempotency/conflict rules |
| SCD1 | IMPLEMENTED reference | ordered current-state overwrite; stale/equal-position/duplicate semantics |
| SCD2 | IMPLEMENTED reference | deterministic temporal history for certified scope; one-current-row invariant |
| SNAPSHOT_DIFF | IMPLEMENTED reference | deterministic I/U/D from complete snapshots with delete guards |

`CDC != SCD2`. `FULL != REPLACE`. Capture and apply are composed independently.

## 7. FULL -> REPLACE correctness

Implemented reference behavior includes:

1. explicit complete source snapshot evidence;
2. isolated candidate/stage;
3. DQ/quarantine accounting;
4. source/candidate empty guards;
5. candidate row-drop guard;
6. reconciliation before publication;
7. live target remains unchanged when required guard/reconciliation fails;
8. durable run/step/reconciliation evidence in reference repository.

Still required before production claim:

- real Lakehouse/Warehouse publication/swap semantics;
- target-write failure/unknown outcome recovery on a persistent adapter;
- retention/rollback policy tied to the real estate.

## 8. SNAPSHOT_DIFF and delete correctness

Implemented reference scope:

- complete snapshot before absence can mean deletion;
- null/duplicate merge-key rejection;
- deterministic insert/update/delete derivation;
- delete-disabled preservation;
- quarantine-aware delete blocking;
- configurable delete-all/delete-fraction guards;
- reconciliation before publication.

Still required:

- generalized tombstone/hard-delete/soft-delete/SCD2-close semantics;
- downstream restatement/cascade policy;
- real Fabric target delete certification.

## 9. SCD1 current-state correctness

Implemented canonical framework fallback must remain independent from ingestion engine.

Certified reference scope:

- composite merge keys;
- source ordering tuple using event time/version/sequence/LSN-like columns;
- latest incoming version selected per key;
- exact rerun idempotency;
- stale row `IGNORE` or `ERROR` policy;
- equal source position + conflicting payload fails closed;
- null/noncomparable ordering fails;
- changed unordered update fails unless explicitly authorized for an authoritative source contract;
- duplicate, superseded and stale observations are separately counted.

A Dataflow/Copy/CDC capture may feed this framework SCD1 implementation.

## 10. UPSERT requirement

UPSERT is P0 because current-state non-dimensional tables are common and native `merge` semantics cannot be assumed equivalent across products.

Required:

- composite merge key;
- optional freshness/order tuple;
- insert/update/no-op counts;
- stale policy;
- equal-position conflict policy;
- exact rerun idempotency;
- delete/tombstone composition;
- retry/unknown-outcome safety;
- target-adapter transaction/publication contract.

UPSERT may share low-level ordering/dedup utilities with SCD1, but the semantic API remains distinct.

## 11. SCD2 correctness

Current reference implementation proves:

- deterministic business-key history;
- one current row per business key;
- tracked-column change detection;
- effective time intervals;
- duplicate unchanged row no-op;
- bounded late/conflict failure semantics.

Required future hardening:

- explicit source version/sequence ordering integration;
- late historical correction/restate policies;
- tombstone/delete close-current semantics;
- real target adapter certification.

## 12. Native Fabric delegation requirements

Native Fabric tools are stage executors, not semantic authorities by default.

### Capability profiles

Capabilities are keyed by `(engine, profile_name)` so connector/product/mode limitations do not leak into global assumptions.

Required resolver behavior:

- conservative default profiles;
- named profile requires explicit engine;
- unsupported strategy/progress/order combination fails before mutation;
- `AUTO` resolves to a concrete plan before execution and cannot silently switch later;
- capture certification does not imply apply certification;
- native apply delegation requires an explicit semantic-equivalence profile.

### Current Dataflow Gen2 profile

Implemented reference profile:

```text
DATAFLOW_GEN2 / dataflow_gen2_incremental_bucket_v1
```

Certifies only:

```text
WATERMARK-like incremental capture/staging using native DateTime buckets
FABRIC_NATIVE capture progress
no composite-watermark guarantee
no native SCD1/UPSERT/SCD2 equivalence claim
```

Required hybrid:

```text
Dataflow Gen2 incremental landing
  -> CaptureReceipt
  -> framework SCD1/UPSERT/SCD2
```

### Copy Job / Copy Activity / Mirroring / external CDC

Apply the same principle: use native movement when strong, but certify exact connector/mode limitations and keep the downstream framework semantic fallback available.

## 13. Progress and state correctness

Required:

- environment-local committed state;
- proposed state separated from committed state;
- one physical capture checkpoint authority;
- dataset lease/optimistic-concurrency protection;
- target mutation + reconciliation + state-commit ordering;
- no framework state advancement after failed/uncertain completion;
- run/attempt lineage and idempotency keys;
- audited reset/rebuild request;
- runtime state never promoted DEV -> UAT -> PROD.

Current state: watermark/state gates are implemented for existing reference slices; complete retry/unknown-outcome protocol remains P0.

## 14. Retry, recovery and reprocessing

Run modes:

```text
NORMAL
RETRY
BACKFILL
REPLAY
FULL_REBUILD
```

Required runtime behavior (P0 unless noted):

- failure classification retryable/non-retryable/unknown;
- dataset attempt lineage;
- bounded retry/backoff;
- exact retained source range/window for deterministic retry where possible;
- backfill range validation/overlap;
- quarantine replay lineage;
- reprocess request requester/reason/scope/approval reference where needed;
- unknown commit recovery using idempotency/reconciliation rather than blind duplicate write;
- rebuild state reset only through audited workflow.

Current state: vocabulary/schema foundations exist; end-to-end runtime is not certified.

## 15. Data quality and quarantine

Implemented reference foundations:

- row-level rules;
- accepted/quarantined accounting;
- row quarantine can allow accepted rows to continue when policy permits;
- contract/system errors are not mislabeled as bad data;
- run/reason lineage;
- reconciliation can block state/publication.

Invariant:

```text
rows_read = rows_accepted + rows_quarantined + rows_intentionally_filtered
```

Required future work:

- persistent quarantine storage adapter;
- replay lifecycle/status;
- sensitive-data access/retention integration (external governance).

## 16. Reconciliation and completion gates

Policy families must support as relevant:

- source/stage/target row counts;
- key counts/uniqueness;
- accepted/quarantined/filtered balance;
- inserted/updated/deleted counts;
- hash/control totals;
- complete-snapshot evidence;
- delete guards;
- SCD current-row/temporal invariants;
- CDC offset/event accounting.

Policy determines `WARN`, `QUARANTINE`, `FAIL`, and whether publication/state progression is permitted.

## 17. Schema contracts and evolution

P0 requirement, not yet complete:

- schema fingerprint/version evidence;
- expected schema contract binding;
- additive-compatible classification;
- breaking-change classification;
- type widening/narrowing policy;
- missing/extra column policy;
- schema-change audit;
- controlled cutover/rebuild implications.

Do not silently auto-evolve every production schema.

## 18. Late/out-of-order/duplicate behavior

The framework must distinguish:

- exact duplicate replay;
- conflicting duplicate identity;
- stale current-state update;
- late but overlap-eligible watermark record;
- out-of-order CDC event;
- late SCD2 historical observation;
- fact/dimension timing issue.

Current state: SCD1 and SCD2 have certified bounded policies; a common cross-strategy temporal/error taxonomy remains incomplete.

Unsupported correction must fail closed rather than produce plausible wrong history.

## 19. Orchestration and dependencies

Implemented reference behavior:

- effective/deployed metadata selection;
- enabled/execution-group/request filters;
- dependency validation and cycle detection;
- priority/criticality;
- bounded parallelism;
- sibling failure isolation;
- dependent `BLOCKED`;
- unrelated sibling continuation;
- aggregate `SUCCESS/PARTIAL_SUCCESS/FAILED`.

Still required:

- Fabric Pipeline execution backend;
- source/capacity-aware concurrency profiles on real workloads;
- cancellation/timeout propagation proof;
- reprocess/rerun orchestration integration.

## 20. Fabric execution model

Required roles:

- Data Factory Pipeline — trigger/schedule/control flow/fan-out/failure routing;
- Spark Job Definition — preferred generic headless framework Spark entrypoint;
- Notebook — thin interactive/smoke/diagnostic or justified production activity;
- Copy Activity / Copy Job — native movement stages where profile matches;
- Dataflow Gen2 — Power Query/native incremental/transformation stage where profile matches;
- Mirroring — provider-managed replication where supported;
- SQL/database-native activity — target-side work when database engine is appropriate;
- Environment — pinned Spark runtime/library configuration;
- environment bindings/Variable Library where appropriate for non-secret physical values.

A pipeline with one thin SJD/Notebook execution activity is acceptable. An opaque notebook owning the whole platform scheduler/control plane is not the target.

## 21. Control plane

Control-plane schema v2 reference includes promotable definitions:

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

and environment-local state/evidence:

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

Production requirements still include:

- supported persistent store/repository;
- real migration lifecycle/checksums/compatibility policy;
- transaction boundaries;
- operator queries/status API;
- retention/pruning dependencies.

SQLAlchemy/SQLite is contract proof only.

## 22. Extension model

Required policy:

- ordinary variation must be metadata, not framework fork;
- metadata uses stable logical extension names;
- domain package/entry-point registry resolves implementation;
- no arbitrary Python module/call expression in production metadata;
- extension may implement custom capture/parser/transform/DQ/specialized apply;
- extension cannot bypass accounting, reconciliation, publication/state authority, secrets/bindings or audit.

Current logical-name registry and validation are implemented/reference-tested.

## 23. Observability and operability

Every failed/delayed dataset should eventually be explainable without reading notebook source:

- pipeline/dataset/step/attempt IDs;
- native Fabric run IDs when available;
- framework version/domain release/Git SHA/config hash;
- concrete execution plan/profile;
- source boundary/window/offset;
- rows read/staged/accepted/quarantined/inserted/updated/deleted;
- duplicate/superseded/stale/conflict evidence where relevant;
- watermark/state before/after;
- reconciliation/schema evidence;
- error code/category/retryability;
- blocked dependency/recovery lineage.

Future operator commands: `status`, `retry`, `backfill`, `replay`, `disable/cancel`, bounded diagnostics.

## 24. Security and enterprise controls

Framework requirements:

- no credentials in semantic metadata;
- logical connection/secret references only;
- physical IDs from environment bindings;
- no secret/token logging;
- auditable operator/quarantine/reprocess actions;
- least-privilege compatible adapters.

External proof required for:

- Entra/service-principal/workspace identity;
- workspace/domain RBAC;
- tenant settings;
- networking/private links/gateways;
- secret/key authority;
- quarantine privacy/retention;
- monitoring receiver/on-call;
- production backup/restore;
- capacity/SKU policy.

## 25. CI/CD and supply chain

Implemented/proven baseline:

- GitHub-hosted PR CI on Python 3.11/3.13;
- static checks/compile/pip check/tests;
- wheel build;
- immutable v0.3.0 GitHub release/checksum workflow;
- release manifest/environment binding separation;
- semantic definition promotion separate from runtime state;
- exact released framework wheel consumption model for domains.

Still required for real Fabric promotion:

- Fabric item/environment deployment adapters;
- same-wheel DEV/UAT/PROD deployment proof;
- binding verification;
- smoke/acceptance evidence.

## 26. Performance/capacity/cost

Design requirements:

- bounded dataset concurrency;
- source/gateway-specific throttling;
- avoid defaulting every movement workload to Spark;
- Spark partition/shuffle/batch controls through approved runtime policy;
- small-file/Delta maintenance strategy;
- session startup/high-concurrency tradeoffs based on measured evidence;
- retain runtime/volume metrics for capacity tuning.

Hard-coded production throughput/SKU numbers are not framework guarantees without estate evidence.

## 27. Certification matrix

Required representative scenarios:

1. `FULL -> REPLACE`: normal, empty/incomplete/drastic drop, reconciliation fail, rerun/unknown outcome.
2. `WATERMARK -> SCD1`: composite/simple boundary, native Dataflow/Copy landing, stale/equal-position/duplicate rerun.
3. `WATERMARK -> UPSERT`: same ordering/idempotency plus merge/delete semantics.
4. `WATERMARK -> SCD2`: tie-breaker/overlap/history conflict/state failure.
5. `SNAPSHOT -> SNAPSHOT_DIFF`: I/U/D, incomplete delete guard, quarantine/delete guard, rerun.
6. `CDC -> UPSERT/SCD1/SCD2`: ordered I/U/D, duplicate/conflict/poison event, checkpoint uncertainty.
7. `BOOTSTRAP -> CDC`: no handoff gap/double apply.
8. APPEND: exact replay vs conflicting duplicate identity.
9. DQ/quarantine: row/batch quarantine and replay lineage.
10. Schema evolution: additive allowed, breaking blocked/cutover-controlled.
11. Recovery: retry attempts, backfill, replay, rebuild, unknown commit.
12. Multi-dataset orchestration: partial success, critical failure, dependency blocked, unrelated sibling continues.
13. Fabric hybrid adapter: native capture -> `CaptureReceipt` -> framework apply -> durable audit/native run correlation.

## 28. Current release threshold

Do **not** publish `v0.4.0` yet.

P0 blockers before release decision:

1. framework UPSERT;
2. explicit apply executor/native-apply delegation contract;
3. recovery attempt lineage and unknown-outcome behavior;
4. CDC normalization/checkpoint/bootstrap correctness;
5. general schema-evolution policy;
6. APPEND identity semantics or explicit deferral justified by release scope;
7. concrete Fabric adapter contracts;
8. persistent control-plane/operator path or explicit bounded release scope;
9. at least one real hybrid Fabric DEV proof;
10. clean `PRODUCTION_READINESS_AUDIT` / `GUARANTEE_COVERAGE` / `CURRENT_STATUS` against release head.

The next version number is selected only after the product slice is coherent; current source version `0.4.0` does not itself authorize publication.
