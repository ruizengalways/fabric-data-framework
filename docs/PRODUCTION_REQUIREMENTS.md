# Production Requirements — fabric-data-framework

Status: Canonical requirements baseline
Last updated: 2026-08-28

## 1. Purpose and evidence levels

`fabric-data-framework` targets a stable enterprise wheel: ordinary datasets should be onboarded through metadata, environment bindings and bounded extensions rather than framework forks.

A capability has four distinct evidence levels:

1. **portable semantics** — framework-owned reusable contract/algorithm;
2. **deterministic certification** — executable unit/contract/reference proof;
3. **Fabric integration evidence** — executed through a real approved Fabric estate with retained native correlation;
4. **external enterprise controls** — identity, networking, secrets, governance, retention, incident response, approval and capacity policy supplied by the enterprise/platform authority.

Do not collapse these into one `production-ready` label. `PRODUCTION_READINESS_AUDIT.md` and `GUARANTEE_COVERAGE.md` are the evidence maps.

Status vocabulary:

- `IMPLEMENTED` — portable owner + executable proof exist at stated scope;
- `PARTIAL` — useful behavior exists but material required paths remain;
- `PLANNED` — required but not implemented;
- `EXTERNAL` — must be supplied/proven by Fabric or enterprise authority.

## 2. Product and delegation boundary

The framework owns reusable DE semantics. Domain repositories own business mappings/rules and bounded domain extensions. `fabric-infra` or the existing enterprise platform owns Fabric estate/security primitives.

ADR 0009 establishes:

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

Current source-controlled policy and immutable planning now represent capture and apply executors independently. A native capture feature must never be interpreted as implicit native apply ownership.

## 3. Source and capture correctness

| Requirement | Status | Production expectation |
|---|---|---|
| Stable source boundary | PARTIAL | WATERMARK/FULL/SNAPSHOT reference slices freeze/represent intended source state; CDC/file/API families remain. |
| Complete FULL snapshot evidence | IMPLEMENTED reference | Completeness is explicit evidence; successful iteration alone is insufficient. |
| Complete SNAPSHOT evidence | IMPLEMENTED reference | Required before absence may mean deletion. |
| Composite watermark | IMPLEMENTED | `(watermark, tie_breaker...)` prevents same-timestamp loss for framework-owned bounds. |
| Watermark overlap | IMPLEMENTED reference | Bounded reread supported; end-to-end recovery still required. |
| `CaptureReceipt` | IMPLEMENTED contract | Native/external movement hands off run/landing/boundary/checkpoint evidence. |
| Single capture progress authority | IMPLEMENTED contract | Exactly one of FRAMEWORK/FABRIC_NATIVE/EXTERNAL owns the physical checkpoint. |
| Ordered CDC offsets/events | PLANNED | Freeze upper offset; preserve event identity/order; safe checkpoint commit. |
| Bootstrap snapshot -> CDC | PLANNED | Handoff coordinate prevents gaps/double apply. |
| File/object manifest freeze | PLANNED | Immutable/versioned manifest/readiness protocol. |
| API pagination/window guardrails | PLANNED | Cursor-loop/max-page/retry-after/replay-stable window behavior. |

Extraction failure must never masquerade as a legitimate empty business snapshot.

Canonical capture semantics remain:

```text
FULL | WATERMARK | SNAPSHOT | CDC | MIRROR | STREAM
```

A physical connector/product does not define a new semantic strategy when one of these contracts fits.

## 4. Apply strategy requirements and current status

| Apply strategy | Status | Certified/reference scope and remaining requirement |
|---|---|---|
| APPEND | PLANNED | append-once identity; exact replay idempotency; conflicting duplicate fails closed |
| REPLACE | IMPLEMENTED reference | isolated candidate, destructive guards, reconciliation, safe publication boundary; real Fabric target publication/recovery still required |
| UPSERT | IMPLEMENTED reference | ordered current-state insert/update, composite key, idempotency, stale/conflict policy, target-only field preservation; delete/recovery/real target adapter remain |
| SCD1 | IMPLEMENTED reference | ordered current-state dimensional overwrite, composite key, idempotency, stale/conflict policy |
| SCD2 | IMPLEMENTED reference | deterministic temporal history for certified scope, one-current-row invariant; broader late-history/delete repair remains |
| SNAPSHOT_DIFF | IMPLEMENTED reference | deterministic I/U/D from complete snapshots with delete guards; real target delete certification remains |

`CDC != SCD2`. `FULL != REPLACE`. Capture and apply are composed independently.

### Shared SCD1/UPSERT current-state foundation

SCD1 and UPSERT use a shared ordered current-state primitive with distinct semantic APIs.

Certified behavior:

```text
composite merge key
ordering tuple = event time / version / sequence / LSN-like values
latest candidate per key within one incoming batch
exact rerun no-op
stale IGNORE or ERROR
equal-position conflicting payload -> fail closed
unordered changed update -> fail closed unless explicitly authorized
duplicate / superseded / stale evidence
```

For an existing key, incoming fields merge over the current target record while target-only fields are preserved.

A Dataflow/Copy/CDC landing may feed these semantics; ingestion engine does not redefine apply correctness.

## 5. FULL, snapshot and delete correctness

### FULL -> REPLACE — implemented reference scope

- explicit complete source snapshot evidence;
- isolated candidate/stage;
- DQ/quarantine accounting;
- source/candidate empty guards;
- drastic row-drop guard;
- reconciliation before publication;
- live target remains unchanged on required guard/reconciliation failure.

Still required: real Lakehouse/Warehouse publication semantics, persistent unknown-outcome recovery, retention/rollback policy.

### SNAPSHOT -> SNAPSHOT_DIFF — implemented reference scope

- complete snapshot before absence can mean deletion;
- null/duplicate merge-key rejection;
- deterministic insert/update/delete derivation;
- delete-disabled preservation;
- quarantine-aware delete blocking;
- delete-all/delete-fraction guards;
- reconciliation before publication.

Still required: generalized tombstone/hard-delete/soft-delete/SCD2-close semantics, downstream restatement policy and real Fabric target delete proof.

## 6. Capture and apply executor capability requirements

Capabilities are keyed by `(engine, profile_name)` because behavior varies by product feature, connector, source configuration, target and service version.

Required resolver/compiler behavior is now reference-implemented:

- conservative default profiles;
- named profile requires explicit engine;
- capture and apply are validated independently;
- unsupported strategy/progress/order combination fails before mutation;
- `AUTO` resolves to concrete engines before immutable plan execution;
- capture certification does not imply apply certification;
- native apply requires explicit semantic-equivalence certification;
- no hidden runtime switch to a weaker engine.

Current policy fields:

```text
execution.engine / capability_profile / progress_owner
    -> capture/movement

execution.apply_engine / apply_capability_profile
    -> apply
```

Current default apply resolution:

```text
AUTO -> SPARK/framework
```

Generic native/SQL profiles intentionally certify no final-target apply strategy. `CUSTOM` apply requires a controlled `extensions.apply` reference.

### Dataflow Gen2 incremental profile

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

Required/validated hybrid contract:

```text
Dataflow Gen2 incremental landing
  -> CaptureReceipt
  -> framework SCD1 / UPSERT / SCD2
```

The capture profile cannot be reused as a fake native SCD1 apply profile.

## 7. Progress, state and recovery

Required state guarantees:

- environment-local committed state;
- proposed state separated from committed state;
- one physical capture checkpoint authority;
- dataset lease/optimistic-concurrency protection;
- target mutation + reconciliation + state-commit ordering;
- no framework state advancement after failed/uncertain completion;
- run/attempt lineage and idempotency keys;
- audited reset/rebuild request;
- runtime state never promoted DEV -> UAT -> PROD.

Current state: watermark/state gates are implemented for existing reference slices; complete recovery/unknown-outcome protocol remains P0.

Run modes:

```text
NORMAL | RETRY | BACKFILL | REPLAY | FULL_REBUILD
```

Still required:

- retryable/non-retryable/unknown failure classification;
- dataset attempt lineage;
- bounded retry/backoff;
- retained source range for deterministic retry where possible;
- validated backfill range/overlap;
- quarantine replay lineage;
- explicit reprocess requester/reason/scope/approval reference where needed;
- unknown target commit recovery via idempotency/reconciliation;
- audited rebuild state reset.

## 8. CDC and bootstrap requirements

CDC is not complete until the framework can certify:

- canonical I/U/D envelope;
- event identity;
- total/partition ordering contract;
- duplicate event no-op;
- conflicting duplicate failure;
- tombstone/delete semantics;
- poison-event evidence;
- bounded source offset/window;
- checkpoint commit only after required downstream gates;
- retry/replay without silent offset loss;
- snapshot/bootstrap -> CDC handoff with no gap/double apply.

CDC normalization should feed the same UPSERT/SCD1/SCD2 apply implementations rather than duplicate target semantics.

## 9. Data quality, quarantine and reconciliation

Implemented reference foundations:

- row-level rules;
- accepted/quarantined accounting;
- row quarantine may allow accepted rows to continue when policy permits;
- contract/system errors are not mislabeled as bad data;
- run/reason lineage;
- reconciliation can block publication/state progression.

Invariant:

```text
rows_read = rows_accepted + rows_quarantined + rows_intentionally_filtered
```

Reconciliation policy families must support as relevant:

- source/stage/target row counts;
- key counts/uniqueness;
- accepted/quarantined/filtered balance;
- inserted/updated/deleted;
- hash/control totals;
- complete-snapshot evidence;
- delete guards;
- SCD invariants;
- future CDC event/offset accounting.

Still required: persistent quarantine adapter, replay lifecycle and external sensitive-data retention/access controls.

## 10. Schema evolution and temporal correctness

General schema evolution is still P0/PLANNED:

- schema fingerprint/version evidence;
- expected contract binding;
- additive-compatible classification;
- breaking-change classification;
- type widening/narrowing policy;
- missing/extra column policy;
- schema-change audit;
- cutover/rebuild implications.

Do not silently auto-evolve every production schema.

Temporal/error taxonomy must distinguish:

- exact duplicate replay;
- conflicting duplicate identity;
- stale current-state update;
- overlap-eligible late watermark record;
- out-of-order CDC event;
- late SCD2 historical observation;
- fact/dimension timing issue.

Current state: SCD1/UPSERT/SCD2 have bounded certified policies; a common cross-strategy taxonomy/correction framework remains incomplete.

Unsupported temporal correction must fail closed.

## 11. Orchestration and dependency execution

Implemented reference behavior:

- effective/deployed metadata selection;
- enabled/execution-group/request filters;
- dependency validation/cycle detection;
- priority/criticality;
- bounded parallelism;
- sibling failure isolation;
- dependent `BLOCKED`;
- unrelated sibling continuation;
- aggregate `SUCCESS/PARTIAL_SUCCESS/FAILED`.

Still required:

- Fabric Pipeline execution backend;
- source/capacity-aware real concurrency profiles;
- cancellation/timeout propagation proof;
- recovery/reprocess orchestration integration.

The framework should prefer explicit execution groups/stages before inventing a universal workflow engine.

## 12. Fabric execution and adapter requirements

Required Fabric roles:

- Data Factory Pipeline — trigger/schedule/control flow/fan-out/failure routing;
- Spark Job Definition — preferred generic headless framework Spark entrypoint;
- Notebook — thin interactive/smoke/diagnostic or justified production activity;
- Copy Activity / Copy Job — native movement stages where profile matches;
- Dataflow Gen2 — Power Query/native incremental/transformation stage where profile matches;
- Mirroring — provider-managed replication where supported;
- SQL/database-native activity — target-side stage only when its profile certifies semantics;
- Environment — pinned Spark runtime/library configuration;
- environment bindings/Variable Library for appropriate non-secret physical values.

Concrete adapters must:

- execute the immutable plan rather than recreate semantic logic;
- emit/correlate native run IDs;
- produce/retain `CaptureReceipt` where capture is external/native;
- preserve framework reconciliation/state boundaries;
- fail closed on unsupported profile/identity/API combinations;
- distinguish modeled support from real Fabric-proven support.

A Pipeline with one thin SJD/Notebook activity may be professional. An opaque notebook owning the whole domain scheduler/control plane is not the target.

## 13. Control-plane requirements

Current reference schema v2 promotable definitions:

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

Implemented reference guarantees:

- promotable vs environment-local separation;
- capture/apply execution-policy separation;
- idempotent semantic materialization;
- runtime state preservation during materialization;
- baseline schema/CLI creates `apply_execution_policy`;
- `CaptureReceipt` remains environment-local.

Still required:

- supported persistent production repository;
- migration checksums/compatibility/rollback policy;
- real transaction/concurrency behavior;
- operator queries/status API;
- retention/pruning/backup/restore.

SQLAlchemy/SQLite is contract proof only.

## 14. Extension requirements

Ordinary variation belongs in metadata, not framework forks.

Metadata uses stable logical extension names; domain packages register implementations. Arbitrary Python module/call expressions are forbidden in production metadata.

Allowed bounded extension classes include custom capture/parser/transform/DQ/specialized apply, but extensions may not bypass accounting, reconciliation, publication/state authority, secrets/bindings or audit.

The logical-name registry/validation is implemented/reference-tested.

## 15. Observability and operability

Every failed/delayed dataset should eventually be explainable without reading notebook source:

- pipeline/dataset/step/attempt IDs;
- native Fabric run IDs when available;
- framework/domain/config/deployment identity;
- concrete capture/apply engines/profiles;
- source boundary/window/offset;
- landing reference;
- rows read/staged/accepted/quarantined/inserted/updated/deleted;
- duplicate/superseded/stale/conflict evidence;
- watermark/state before/after;
- reconciliation/schema evidence;
- error category/code/retryability;
- blocked dependency/recovery lineage.

Future operator surface: `status`, `retry`, `backfill`, `replay`, `disable/cancel`, bounded diagnostics.

## 16. Security and external enterprise controls

Framework requirements:

- no credentials in semantic metadata;
- logical connection/secret references only;
- physical IDs from environment bindings;
- no secret/token logging;
- auditable operator/quarantine/reprocess actions;
- least-privilege-compatible adapters.

External evidence is required for Entra identities, workspace/domain RBAC, tenant settings, networking/private links/gateways, secret authority, quarantine retention/privacy, alert receivers/on-call, backup/restore and capacity/SKU policy.

## 17. CI/CD and supply chain

Implemented/proven baseline:

- GitHub-hosted PR CI on Python 3.11/3.13;
- static checks/compile/pip check/tests;
- wheel build;
- immutable v0.3.0 GitHub release/checksum path;
- release manifest/environment binding separation;
- semantic definition promotion separate from runtime state;
- exact released framework wheel consumption model for domains.

Still required for real Fabric promotion:

- Fabric item/environment deployment adapters;
- same-wheel DEV/UAT/PROD proof;
- binding verification;
- smoke/acceptance evidence.

## 18. Performance, capacity and cost

Design requirements:

- bounded dataset concurrency;
- source/gateway-specific throttling;
- do not default every movement workload to Spark;
- Spark partition/shuffle/batch controls through approved runtime policy;
- small-file/Delta maintenance strategy;
- session startup/high-concurrency choices based on measured evidence;
- retain volume/runtime metrics for capacity tuning.

Hard-coded production throughput/SKU values are not framework guarantees without estate evidence.

## 19. Representative certification matrix

Required scenarios include:

1. `FULL -> REPLACE`: normal, empty/incomplete/drastic drop, reconciliation fail, rerun/unknown outcome.
2. `WATERMARK -> SCD1`: composite/simple boundary, native landing, stale/equal-position/duplicate rerun.
3. `WATERMARK -> UPSERT`: ordered insert/update/no-op, stale/conflict, target-only preservation, native landing.
4. `WATERMARK -> SCD2`: tie-breaker/overlap/history conflict/state failure.
5. `SNAPSHOT -> SNAPSHOT_DIFF`: I/U/D, incomplete delete guard, quarantine/delete guard, rerun.
6. `CDC -> UPSERT/SCD1/SCD2`: ordered I/U/D, duplicate/conflict/poison event, checkpoint uncertainty.
7. `BOOTSTRAP -> CDC`: no handoff gap/double apply.
8. APPEND: exact replay vs conflicting duplicate identity.
9. DQ/quarantine: row/batch quarantine and replay lineage.
10. schema evolution: additive allowed, breaking blocked/cutover-controlled.
11. recovery: retry attempts, backfill, replay, rebuild, unknown commit.
12. multi-dataset orchestration: partial success, critical failure, dependency blocked, unrelated sibling continues.
13. Fabric hybrid adapter: native capture -> `CaptureReceipt` -> framework apply -> durable audit/native run correlation.

Current deterministic suite before this documentation sync: **106 tests passed** in GitHub Actions run `33175724889`.

## 20. Current release threshold

Do **not** publish `v0.4.0` yet.

The two earlier blockers below are now complete at reference level and are no longer release blockers by themselves:

```text
framework UPSERT
explicit capture/apply executor separation
```

Remaining P0 blockers before a release decision:

1. recovery attempt lineage and unknown-outcome behavior;
2. CDC normalization/checkpoint/bootstrap correctness;
3. general schema-evolution policy;
4. APPEND identity semantics or explicit deferral justified by release scope;
5. concrete Fabric adapter contracts;
6. supported persistent control-plane/operator path or explicitly bounded release scope;
7. at least one real hybrid Fabric DEV proof;
8. clean `PRODUCTION_READINESS_AUDIT` / `GUARANTEE_COVERAGE` / `CURRENT_STATUS` against the release head.

Native final-target apply certification is not required for the first coherent release if framework apply remains the documented default, but any native apply claim must have explicit equivalence evidence.

The next version number is selected only after the product slice is coherent; current source version `0.4.0` does not itself authorize publication.
