# Production Requirements — fabric-data-framework

Status: Canonical requirements baseline
Last updated: 2026-08-29

## 1. Product target and evidence levels

`fabric-data-framework` is intended to be a stable enterprise wheel. Routine datasets should be onboarded through semantic metadata, environment bindings, certified capability profiles and bounded domain extensions rather than framework forks.

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
- `EXTERNAL` — supplied/proven by platform/enterprise authority.

## 2. Architecture invariants

1. Capture semantics and apply semantics are independent.
2. Capture/movement executor and apply executor are independent.
3. Native Fabric features are capability-certified stage delegates, not semantic authorities by default.
4. One physical capture has one authoritative progress owner: FRAMEWORK, FABRIC_NATIVE or EXTERNAL.
5. Native/external capture hands off through immutable `CaptureReceipt` evidence.
6. Provider CDC coordinates are normalized before entering semantic CDC logic.
7. Provider/native source progress authority and framework downstream semantic application progress are distinct concepts.
8. Dataset is the default fault/retry boundary.
9. Runtime state/evidence is environment-local and never promoted DEV -> UAT -> PROD.
10. State progression occurs only after the required target mutation/reconciliation boundary is proven.
11. An uncertain target write must be reconciled before any retry.
12. Real Fabric/security/capacity evidence must not be fabricated by reference tests.

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
| Stable FULL snapshot evidence | IMPLEMENTED reference | snapshot identity/completeness; real Fabric capture pending |
| Stable SNAPSHOT evidence before delete inference | IMPLEMENTED reference | complete snapshot guard/delete protection |
| Composite WATERMARK | IMPLEMENTED | `(watermark, tie_breaker...)` ordering |
| WATERMARK overlap | IMPLEMENTED reference | bounded reread + idempotent apply foundations |
| CaptureReceipt | IMPLEMENTED contract | native/external run/landing/boundary/checkpoint evidence |
| Single physical capture progress authority | IMPLEMENTED contract | capability validation |
| Fabric capture adapter request/evidence boundary | IMPLEMENTED adapter contract | Copy Job/Copy Activity/Dataflow Gen2/Spark fake-transport certification |
| Framework-owned bounded Fabric source range verification | IMPLEMENTED adapter contract | observed lower/upper must equal requested range |
| Canonical ordered CDC envelope/events | IMPLEMENTED reference | `capture/cdc.py`, deterministic tests |
| CDC identity/dedupe/conflict/order validation | IMPLEMENTED reference | exact duplicate ignore; conflict/ambiguous order fail closed |
| Frozen CDC upper boundary + completeness evidence | IMPLEMENTED reference | bounded window certification |
| CDC checkpoint state commit gate | IMPLEMENTED reference | target/reconciliation gate + no regression |
| Durable CDC apply checkpoint | IMPLEMENTED schema/transaction reference | optimistic concurrency in control-plane IO |
| Snapshot/bootstrap -> CDC | IMPLEMENTED reference | no-gap/no-double-apply fenced handoff |
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
| UPSERT | IMPLEMENTED reference | composite merge key, ordered freshness tuple, latest candidate, idempotency, stale/equal-position handling; CDC I/U/D path implemented |
| SCD1 | IMPLEMENTED reference | ordered current-state correctness; CDC I/U/D path implemented |
| SCD2 | IMPLEMENTED reference | deterministic history, one-current-row invariant; CDC source-order/valid-time path implemented with retroactive correction fail-closed |
| SNAPSHOT_DIFF | IMPLEMENTED reference | complete snapshot -> deterministic I/U/D, delete/quarantine guards |

`CDC != SCD2`, `FULL != REPLACE`, and a native feature named `merge`/`SCD2`/`incremental refresh` is not automatically equivalent to these contracts.

## 5. Current-state correctness

SCD1 and UPSERT share `apply/current_state.py` for batch/current-state ordering and `apply/cdc.py` for CDC current-state execution.

Certified non-CDC scope:

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

Certified CDC scope:

- canonical source partition + integer position tuple;
- INSERT/UPDATE/DELETE/reinsert;
- stale event ignore;
- equal-position exact state no-op;
- equal-position conflicting state fail closed;
- explicit delete APPLY/IGNORE/ERROR policy;
- missing DELETE idempotent no-op;
- bootstrap row may enter CDC only when committed lower checkpoint proves event is newer;
- same key moving across partitions without an ordering proof fails closed.

Future physical target adapters still require transaction/unknown-outcome certification against real Lakehouse/Warehouse/SQL targets.

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

The immutable `ExecutionPlan` resolves both to concrete engines before execution. No hidden runtime switching is permitted.

Capability rules:

- named profile requires explicit engine;
- unsupported capture/apply/progress/order combination fails before mutation;
- capture certification does not imply apply certification;
- native apply requires explicit semantic-equivalence certification;
- generic native profiles do not claim arbitrary UPSERT/SCD1/SCD2 equivalence;
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

Deterministically certified:

- adapter engine and execution kind match compiled unit;
- pure capture adapter owns EXTRACT/STAGE, not downstream apply/state roles;
- FAILED/CANCELLED/UNKNOWN native status never yields success receipt;
- landing/source/snapshot evidence mismatches fail closed;
- FRAMEWORK-owned bounded movement proves exact requested source bounds;
- native run ID retained in `CaptureReceipt`;
- no implicit credentials/workspace/client construction in semantic adapter.

Still required:

- actual Fabric REST/SDK/CLI transports;
- real Copy/Dataflow/SJD polling/correlation;
- approved authentication/environment bindings;
- Fabric Pipeline backend;
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

Implemented:

- RETRYABLE / NON_RETRYABLE / UNKNOWN_OUTCOME classification;
- bounded retry/backoff;
- attempt-specific dataset run IDs;
- immutable root/previous attempt lineage;
- explicit retryable audit status;
- retry exhaustion signal;
- reprocess request lifecycle;
- process-control exceptions are not swallowed.

Proof exists for `attempt 1 FAILED -> attempt 2 SUCCEEDED`.

### 8.2 Unknown target mutation — IMPLEMENTED reference core

```text
UNKNOWN_OUTCOME
    -> reconciliation
       COMMITTED     -> mark success; do not write again
       NOT_COMMITTED -> retry may proceed
       UNRESOLVED    -> fail/stop; no blind retry
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

- freeze/reuse exact source windows for every capture family;
- Copy/Dataflow/Mirroring/native CDC resume behavior;
- provider-specific CDC source-offset commit/resume after downstream failure;
- quarantine payload replay + `replayed_by_dataset_run_id` end to end;
- FULL_REBUILD target/state reset + rebuild orchestration;
- durable idempotency keys for physical target adapters;
- supported operator CLI/API.

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

`cdc_checkpoint` stores downstream framework CDC application positions, committing dataset run and optimistic-concurrency version. For FABRIC_NATIVE/EXTERNAL source progress, native/external authority remains in provider evidence/`CaptureReceipt` and is not replaced by this table.

Current SQLAlchemy/SQLite proof certifies schema/materialization/transaction boundaries only. A production persistent repository remains required.

## 10. Data quality/reconciliation

Required invariant:

```text
rows_read = rows_accepted + rows_quarantined + rows_intentionally_filtered
```

Implemented foundations:

- row-level DQ;
- explicit quarantine;
- batch/system errors distinct from bad rows;
- row accounting;
- reconciliation results;
- reconciliation may block publication/state progression;
- snapshot delete inference is quarantine-aware.

Still required: persistent quarantine store, privacy/retention integration, CDC poison-event policy and complete replay lifecycle.

## 11. CDC requirements — IMPLEMENTED portable core, provider integration PARTIAL

Canonical design: `docs/CDC_DESIGN.md`.

Implemented minimum:

- INSERT / UPDATE / DELETE;
- event identity;
- canonical business/merge key;
- source partition + ordered integer position tuple;
- before/after payload;
- timezone-aware event time and transaction/source metadata;
- frozen upper checkpoint + completeness evidence;
- exact duplicate idempotency;
- conflicting duplicate failure;
- ambiguous same-position failure;
- ambiguous same-key cross-partition failure;
- overlap at/below committed checkpoint ignore;
- target checkpoint advancement only after required downstream mutation/reconciliation;
- durable optimistic checkpoint state;
- CDC -> UPSERT/SCD1;
- CDC -> SCD2 with separate source-order and valid-time clocks;
- snapshot/bootstrap -> CDC fenced handoff with no gap/double apply for certified partition model.

Current fail-closed boundaries:

- provider must normalize opaque native coordinates before semantic core;
- repartition/key movement without ordering proof is not accepted;
- bootstrap partition changes are not certified;
- retroactive SCD2 valid-time rewrite is not certified;
- provider transaction atomicity beyond row-order contract is not yet generalized.

Still required:

- selected built-in provider envelope adapters/capability profiles;
- native/external offset resume/commit integration;
- poison-event quarantine/replay;
- real CDC source/Fabric evidence.

## 12. Snapshot/bootstrap -> CDC requirements — IMPLEMENTED reference

Safe handoff contract:

```text
start/retain CDC at S
S <= snapshot consistency checkpoint B
complete snapshot consistent through B
publish/apply snapshot
CDC <= B -> ignore as snapshot-covered overlap
CDC >  B -> apply
```

Must fail if snapshot is incomplete/not fenced, CDC retention starts after B, partition set changes during bootstrap, or first upper checkpoint regresses below B.

## 13. SCD2 temporal correctness

For CDC SCD2:

```text
canonical CDC position -> source order
event_time             -> validity interval
```

Equal event time with different source positions is legal. A newer source event whose event time is earlier than current `valid_from` currently fails closed as retroactive history correction.

General cross-strategy temporal taxonomy remains PARTIAL.

## 14. Schema evolution

General schema evolution remains PLANNED:

- fingerprint/version evidence;
- additive-compatible vs breaking classification;
- widening/narrowing rules;
- missing/extra column rules;
- controlled rebuild/cutover implications;
- schema-change audit.

## 15. Orchestration requirements

Implemented reference:

- metadata selection/grouping;
- dependency/cycle validation;
- bounded concurrency;
- sibling failure isolation;
- dependent BLOCKED;
- unrelated continuation;
- criticality-aware pipeline status.

Still required:

- real Fabric Pipeline backend;
- cancellation/timeout propagation proof;
- capacity/source/gateway-aware real tuning;
- operator-triggered reprocess orchestration wiring.

## 16. CI/CD and supply chain

Implemented/proven:

- GitHub PR CI Python 3.11/3.13;
- Ruff/compile/pip check/tests;
- wheel build;
- immutable v0.3.0 GitHub Release/checksum workflow;
- release manifest/environment binding separation;
- runtime state excluded from promotion;
- exact released framework wheel pinning by domains.

Latest CDC evidence:

```text
ccf0fc8950efb1f4d338cadcaf83aac5fd49a7b9  / 33215409341 / 153 passed
ed6c13d4fcabe165ef86be2e547d794e15e5375c  / 33215708004 / 159 passed
c41fbd00bb3d3c6bc71e20f958c4ec14106ac33c  / 33216133811 / 165 passed
465a2c1e9ddf25b0ace2293f578c2c5bb3a653ae  / 33216281126 / 171 passed
```

Still required for next release: real Fabric artifact/environment deployment and smoke evidence.

## 17. Security/external controls

Framework requirements:

- no credentials in semantic metadata;
- logical connection/secret refs only;
- physical IDs via environment bindings;
- no token/secret logging;
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

## 18. Release blockers from current head

Do **not** publish `v0.4.0` yet.

CDC canonical correctness and bootstrap are no longer release-gap placeholders. Current material blockers are:

1. selected provider CDC envelope/capability integrations and source-offset recovery semantics;
2. strategy-specific recovery completion: replay/rebuild/native-progress recovery;
3. APPEND identity semantics or explicit milestone deferral;
4. general schema evolution policy;
5. file/API capture guardrails for broader source coverage;
6. supported persistent control-plane/operator surface or a clearly bounded release scope;
7. real Fabric transport/backend implementation;
8. at least one approved DEV hybrid execution retaining native run correlation;
9. final audit/docs/CI against exact candidate head.

Framework UPSERT, capture/apply executor separation, Fabric capture adapter contracts, recovery core, canonical CDC, durable CDC checkpointing and snapshot->CDC handoff are implemented reference capabilities.
