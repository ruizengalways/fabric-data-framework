# Production Requirements — fabric-data-framework

Status: Canonical requirements baseline
Last updated: 2026-08-29

## 1. Product target and evidence levels

`fabric-data-framework` is intended to be a stable enterprise wheel. Routine datasets should be onboarded through semantic metadata, environment bindings and bounded domain extensions rather than framework forks.

Evidence levels remain separate:

1. **Portable semantics** — provider-neutral framework contract/algorithm.
2. **Deterministic certification** — executable unit/contract/reference proof.
3. **Real Fabric evidence** — approved Fabric item/API run with retained native correlation.
4. **External enterprise controls** — identity, RBAC, networking, secrets, retention, monitoring, capacity and governance.

Never infer level 3 or 4 from level 1 or 2.

Status vocabulary:

- `IMPLEMENTED` — portable owner + executable proof at stated scope.
- `PARTIAL` — useful core exists but material integration/strategy work remains.
- `PLANNED` — required, not implemented.
- `EXTERNAL` — must be supplied/proven by platform/enterprise authority.

## 2. Architecture invariants

1. Capture semantics and apply semantics are independent.
2. Capture/movement executor and apply executor are independent.
3. Native Fabric features are capability-certified stage delegates, not semantic authorities by default.
4. One physical capture has one authoritative progress owner: FRAMEWORK, FABRIC_NATIVE or EXTERNAL.
5. Native/external capture hands off through immutable `CaptureReceipt` evidence.
6. Dataset is the default fault/retry boundary.
7. Runtime state/evidence is environment-local and never promoted DEV -> UAT -> PROD.
8. State progression occurs only after the required mutation/reconciliation boundary is proven.
9. An uncertain target write must be reconciled before any retry.
10. Real Fabric/security/capacity evidence must not be fabricated by reference tests.

## 3. Capture strategy requirements

Canonical capture strategies:

```text
FULL
WATERMARK
SNAPSHOT
CDC
MIRROR
STREAM
```

| Requirement | Status | Current evidence / remaining work |
|---|---|---|
| Stable FULL snapshot evidence | IMPLEMENTED reference | explicit snapshot identity/completeness; real Fabric capture pending |
| Stable SNAPSHOT evidence before delete inference | IMPLEMENTED reference | complete snapshot guard/delete protection |
| Composite WATERMARK | IMPLEMENTED | `(watermark, tie_breaker...)` ordering |
| WATERMARK overlap | IMPLEMENTED reference | bounded reread; recovery/idempotent apply support exists |
| CaptureReceipt | IMPLEMENTED contract | native/external run/landing/boundary/checkpoint handoff |
| Single capture progress authority | IMPLEMENTED contract | capability validation |
| Fabric capture adapter request/evidence boundary | IMPLEMENTED adapter contract | Copy Job/Copy Activity/Dataflow Gen2/Spark fake-transport certification |
| Framework-owned bounded Fabric source range verification | IMPLEMENTED adapter contract | observed lower/upper must equal requested range |
| Ordered CDC envelope/events | PLANNED | next core implementation |
| CDC checkpoint commit gate | PLANNED | next core implementation |
| Snapshot/bootstrap -> CDC | PLANNED | no-gap/no-double-apply handoff required |
| File manifest freeze | PLANNED | immutable/readiness protocol |
| API pagination/window guardrails | PLANNED | cursor/max-page/retry-after/replay-stable window behavior |

Extraction failure must never masquerade as a legitimate empty business snapshot.

## 4. Apply strategy requirements

Canonical apply strategies:

```text
APPEND
REPLACE
UPSERT
SCD1
SCD2
SNAPSHOT_DIFF
```

| Strategy | Status | Required/certified semantics |
|---|---|---|
| APPEND | PLANNED | append-once identity; exact replay idempotency; conflicting identity fails closed |
| REPLACE | IMPLEMENTED reference | isolated candidate, completeness/empty/drop guards, reconciliation, safe publication boundary |
| UPSERT | IMPLEMENTED reference | composite merge key, ordered freshness tuple, latest candidate, idempotency, stale policy, equal-position conflict |
| SCD1 | IMPLEMENTED reference | same ordered current-state correctness under dimensional SCD1 semantic |
| SCD2 | IMPLEMENTED reference | deterministic history, one-current-row invariant, bounded conflict/late behavior |
| SNAPSHOT_DIFF | IMPLEMENTED reference | complete snapshot -> deterministic I/U/D, delete/quarantine guards |

`CDC != SCD2`, `FULL != REPLACE`, and a native feature named `merge`/`SCD2`/`incremental refresh` is not automatically equivalent to these contracts.

## 5. Current-state correctness

SCD1 and UPSERT share `apply/current_state.py` so their hard ordering/idempotency behavior cannot drift.

Certified scope:

- composite merge key;
- event-time/version/sequence/LSN-like ordering tuple;
- latest candidate per incoming key;
- exact rerun no-op;
- stale IGNORE/ERROR policy;
- equal-position conflicting payload fails closed;
- null/non-comparable ordering fails;
- changed unordered update fails unless explicitly authorized;
- duplicate, superseded and stale observations are separately counted;
- incoming fields update existing state while target-only fields are retained.

Future target adapters still require transaction/unknown-outcome certification against real Lakehouse/Warehouse/SQL targets.

## 6. Execution engine/delegation requirements

Capture/movement engines:

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

`ExecutionPolicy` source-controlled inputs:

```text
engine + capability_profile + progress_owner
    -> capture/movement

apply_engine + apply_capability_profile
    -> final apply
```

The immutable `ExecutionPlan` must resolve both to concrete engines before execution. No hidden runtime switching is permitted.

Capability rules:

- named profile requires explicit engine;
- unsupported capture/apply/progress/order combination fails before mutation;
- capture certification does not imply apply certification;
- native apply requires explicit semantic-equivalence certification;
- generic native profiles currently do not claim arbitrary UPSERT/SCD1/SCD2 equivalence;
- default apply remains framework/Spark where no certified native apply profile exists.

## 7. Fabric capture adapter requirements

Current adapter-contract implementation covers:

```text
FabricCaptureRequest
FabricNativeRunEvidence
FabricCaptureTransport Protocol
FabricCaptureAdapter
CopyJobCaptureAdapter
CopyActivityCaptureAdapter
DataflowGen2CaptureAdapter
SparkJobCaptureAdapter
FabricAdapterRegistry
```

Required guarantees already certified with deterministic fake transports:

- adapter engine and execution kind must match compiled unit;
- pure capture adapter owns EXTRACT/STAGE, not downstream APPLY/PUBLISH/STATE roles;
- FAILED/CANCELLED/UNKNOWN native status never yields success receipt;
- landing, source/snapshot evidence mismatches fail closed;
- FRAMEWORK-owned bounded movement must prove exact requested source bounds;
- native run ID is retained in `CaptureReceipt`;
- no implicit credentials/workspace/client construction in the semantic adapter.

Still required:

- actual Fabric REST/SDK/CLI transport implementations;
- real Copy/Dataflow/SJD run-state polling/correlation;
- approved authentication and environment bindings;
- Fabric Pipeline orchestration backend;
- real DEV integration evidence.

## 8. Recovery and reprocessing requirements

Canonical run modes:

```text
NORMAL
RETRY
BACKFILL
REPLAY
FULL_REBUILD
```

### 8.1 Recovery core — IMPLEMENTED reference

The framework now provides:

- conservative failure classification: RETRYABLE / NON_RETRYABLE / UNKNOWN_OUTCOME;
- bounded retry count/backoff;
- attempt-specific dataset run IDs;
- immutable root/previous attempt lineage;
- explicit `retryable` audit status;
- retry exhaustion signal;
- audited reprocess request lifecycle;
- explicit non-normal run-mode linkage;
- process-control exceptions are not swallowed as dataset failures.

Required proof already exists for:

```text
attempt 1 FAILED retryable
attempt 2 SUCCEEDED
```

### 8.2 Unknown target mutation — IMPLEMENTED reference core

A timeout/lost acknowledgement after target mutation may be ambiguous.

Required behavior is implemented:

```text
UNKNOWN_OUTCOME
    -> reconciliation
       COMMITTED     -> mark success, do not write again
       NOT_COMMITTED -> retry may proceed
       UNRESOLVED    -> fail/stop, no blind retry
```

No reconciliation callback also fails closed.

### 8.3 Reprocess request contracts — IMPLEMENTED reference

- RETRY requires original dataset run ID.
- BACKFILL requires explicit lower/upper range.
- REPLAY requires original run or quarantine IDs.
- FULL_REBUILD requires explicit `authoritative_reset=true` intent.
- request semantic identity is immutable; lifecycle status may advance.

### 8.4 Strategy-specific recovery — PARTIAL

Still required:

- persist/freeze exact source ranges for every capture family;
- Copy/Dataflow/Mirroring native-progress replay/resume behavior;
- quarantine payload replay and `replayed_by_dataset_run_id` update end to end;
- actual FULL_REBUILD state/target reset and rebuild orchestration;
- durable idempotency keys for physical target adapters;
- persistent repository transaction/concurrency tests;
- operator CLI/API for status/retry/backfill/replay/rebuild.

## 9. Control-plane requirements

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

Current SQLAlchemy/SQLite proof certifies schema/materialization/evidence boundaries only. A production persistent repository remains required.

`reprocess_request` is mutable only in lifecycle status/timestamp; request semantic identity is immutable. `dataset_attempt_lineage` is append-only evidence.

## 10. Data quality/reconciliation

Required invariant:

```text
rows_read = rows_accepted + rows_quarantined + rows_intentionally_filtered
```

Implemented reference foundations:

- row-level DQ;
- explicit quarantine;
- batch/system errors distinguished from bad rows;
- row accounting;
- reconciliation results;
- reconciliation may block publication/state progression;
- snapshot delete inference is quarantine-aware.

Still required: persistent quarantine store, privacy/retention integration and complete replay lifecycle.

## 11. CDC requirements — next P0 implementation

CDC must provide a canonical provider-neutral event contract, independent of Debezium/Copy Job/database-specific envelopes.

Required minimum:

- operation: INSERT / UPDATE / DELETE;
- event identity;
- business/merge key;
- source position/order tuple;
- before/after payload where available;
- transaction/source metadata where useful;
- source checkpoint reference;
- duplicate-event idempotency;
- conflicting duplicate failure;
- out-of-order/stale policy;
- poison/invalid event quarantine/failure policy;
- bounded checkpoint upper coordinate;
- checkpoint advancement only after required downstream mutation + reconciliation;
- target apply remains independently selected (`UPSERT`, `SCD1`, `SCD2`, etc.).

Snapshot/bootstrap -> CDC must prove no source gap and no double apply at the handoff coordinate.

## 12. Schema and temporal correctness

General schema evolution remains PLANNED:

- fingerprint/version evidence;
- additive-compatible vs breaking classification;
- widening/narrowing rules;
- missing/extra column rules;
- controlled rebuild/cutover implications;
- schema-change audit.

Cross-strategy temporal taxonomy remains PARTIAL. SCD1/UPSERT/SCD2 have bounded policies; CDC/general late correction still require a shared model.

## 13. Orchestration requirements

Implemented reference:

- metadata selection/grouping;
- dependency and cycle validation;
- bounded concurrency;
- sibling failure isolation;
- dependent BLOCKED;
- unrelated continuation;
- criticality-aware SUCCESS/PARTIAL_SUCCESS/FAILED.

Still required:

- real Fabric Pipeline backend;
- cancellation/timeout propagation proof;
- source/gateway/capacity-aware concurrency from real measurements;
- operator-triggered reprocess orchestration wiring.

## 14. CI/CD and supply chain

Implemented/proven:

- GitHub PR CI on Python 3.11/3.13;
- Ruff/compile/pip check/tests;
- wheel build;
- immutable v0.3.0 GitHub release + checksum workflow;
- release manifest and environment binding separation;
- same semantic definitions promoted without runtime state;
- domains consume exact released framework wheel versions.

Latest hardening evidence:

```text
commit a5da06294dfba0c5ae756dcc1d8814931feebec7
run 33179754372
139 tests passed
```

Still required for next release: real Fabric artifact/environment deployment and smoke evidence.

## 15. Security/external controls

Framework requirements:

- no credentials in semantic metadata;
- logical connection/secret refs only;
- physical IDs via environment bindings;
- no secret/token logging;
- auditable reprocess/quarantine/operator intent;
- least-privilege-compatible adapters.

External evidence required:

- Entra/service principal/workspace identity;
- workspace/domain RBAC;
- tenant settings;
- gateway/private networking;
- secret authority;
- source CDC enablement/retention;
- production backup/restore;
- monitoring/on-call;
- data retention/privacy;
- capacity/SKU policy.

## 16. Release blockers from current head

Do **not** publish `v0.4.0` yet.

Current material blockers are now:

1. CDC normalization/order/checkpoint correctness.
2. Snapshot/bootstrap -> CDC handoff.
3. Strategy-specific recovery completion (replay/rebuild/native-progress recovery).
4. APPEND identity semantics or an explicit milestone deferral.
5. General schema evolution policy.
6. Supported persistent control-plane/operator surface or a clearly bounded release scope.
7. Real Fabric transport/backend implementations.
8. At least one approved DEV hybrid execution retaining native run correlation.
9. Final audit/docs/CI against the exact release head.

Framework UPSERT, capture/apply executor separation, Fabric capture adapter contracts and the generic retry/unknown-outcome recovery core are no longer release-gap placeholders; they are implemented reference capabilities.
