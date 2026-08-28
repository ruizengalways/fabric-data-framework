# Production Requirements — fabric-data-framework

Status: Canonical requirements baseline
Last updated: 2026-08-29

## 1. Product target and evidence levels

`fabric-data-framework` is intended to be a stable enterprise wheel. Routine datasets should be onboarded through semantic metadata, environment bindings, certified capability profiles and bounded domain extensions rather than framework forks.

Evidence levels remain separate:

1. **Portable semantics** — provider-neutral framework contract/algorithm.
2. **Deterministic certification** — executable unit/contract/reference proof.
3. **Real service/Fabric evidence** — approved real provider/Fabric execution with retained correlation.
4. **External enterprise controls** — identity, RBAC, networking, secrets, retention, monitoring, capacity and governance.

Never infer level 3 or 4 from level 1 or 2.

Status vocabulary:

- `IMPLEMENTED` — portable/adapter owner + executable proof at stated scope.
- `PARTIAL` — useful core exists but material integration/strategy work remains.
- `PLANNED` — required, not implemented.
- `EXTERNAL` — supplied/proven by platform/enterprise authority.

## 2. Architecture invariants

1. Capture semantics and apply semantics are independent.
2. Capture/movement executor and apply executor are independent.
3. Native/provider features are capability-certified stage delegates, not semantic authorities by default.
4. One physical capture has one authoritative source progress owner: FRAMEWORK, FABRIC_NATIVE or EXTERNAL.
5. Native/external capture hands off through immutable typed evidence.
6. Provider CDC coordinates are normalized before entering semantic CDC logic.
7. Provider/native source progress authority and framework downstream semantic application progress are distinct.
8. Dataset is the default fault/retry boundary.
9. Runtime state/evidence is environment-local and never promoted DEV -> UAT -> PROD.
10. State progression occurs only after required target mutation/reconciliation evidence.
11. An uncertain target write is reconciled before retry.
12. Real Fabric/provider/security/capacity evidence must not be fabricated by reference tests.

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
| Stable FULL snapshot evidence | IMPLEMENTED reference | snapshot identity/completeness; real target/service proof pending |
| Stable SNAPSHOT evidence before delete inference | IMPLEMENTED reference | complete snapshot guard/delete protection |
| Composite WATERMARK | IMPLEMENTED | `(watermark, tie_breaker...)` ordering |
| WATERMARK overlap | IMPLEMENTED reference | bounded reread + idempotent apply foundations |
| CaptureReceipt | IMPLEMENTED contract | native/external run/landing/boundary/checkpoint evidence |
| Single physical capture progress authority | IMPLEMENTED contract | capability validation |
| Fabric capture adapter request/evidence boundary | IMPLEMENTED adapter contract | Copy Job/Copy Activity/Dataflow Gen2/Spark fake-transport certification |
| Framework-owned bounded Fabric source range verification | IMPLEMENTED adapter contract | observed lower/upper must equal requested range |
| Canonical ordered CDC envelope/events | IMPLEMENTED reference | `capture/cdc.py` |
| CDC identity/dedupe/conflict/order validation | IMPLEMENTED reference | deterministic certification |
| Frozen CDC upper boundary + completeness evidence | IMPLEMENTED reference | bounded-window certification |
| CDC checkpoint state commit gate | IMPLEMENTED reference | target/reconciliation gate + no regression |
| Durable CDC apply checkpoint | IMPLEMENTED schema/transaction reference | optimistic concurrency |
| Snapshot/bootstrap -> CDC | IMPLEMENTED reference | no-gap/no-double-apply fenced handoff |
| Debezium/Kafka provider envelope | IMPLEMENTED adapter contract | `EXTERNAL_CDC/debezium_kafka_v1` |
| Debezium/Kafka retention-aware resume range | IMPLEMENTED reference | next-required offset derived from framework apply checkpoint |
| Real Kafka consumer/connector transport + cursor commit | PLANNED | live Kafka/Debezium proof |
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
| UPSERT | IMPLEMENTED reference | composite merge key, ordering/idempotency/stale/equal-position behavior; CDC I/U/D path implemented |
| SCD1 | IMPLEMENTED reference | ordered current-state correctness; CDC I/U/D path implemented |
| SCD2 | IMPLEMENTED reference | deterministic history; CDC source-order/valid-time path; retroactive correction fail-closed |
| SNAPSHOT_DIFF | IMPLEMENTED reference | complete snapshot -> deterministic I/U/D, delete/quarantine guards |

`CDC != SCD2`, `FULL != REPLACE`, and a native feature named `merge`/`SCD2`/`incremental refresh` is not automatically equivalent to these contracts.

## 5. Current-state and temporal correctness

SCD1 and UPSERT share `apply/current_state.py`; CDC current-state execution is in `apply/cdc.py`.

Certified current-state behavior includes composite keys, ordered freshness, latest candidate, exact rerun, stale IGNORE/ERROR, equal-position conflict failure, changed unordered update fail-closed, and target-only field preservation.

Certified CDC behavior includes INSERT/UPDATE/DELETE/reinsert, explicit delete policy, stale/equal-position handling, bootstrap lower-checkpoint proof and same-key cross-partition ambiguity failure.

CDC SCD2 keeps separate clocks:

```text
canonical source position -> event order
event_time                -> valid interval
```

A newer source event whose event time predates current history is currently rejected rather than silently rewriting history.

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

The immutable `ExecutionPlan` resolves both before execution. No hidden runtime switching is permitted.

Capability rules:

- named profile requires explicit engine;
- unsupported capture/apply/progress/order combination fails before mutation;
- capture certification does not imply apply certification;
- native apply requires explicit semantic-equivalence certification;
- generic native profiles do not claim arbitrary UPSERT/SCD1/SCD2 equivalence;
- default apply remains framework/Spark where no certified native apply profile exists.

Current named profiles include:

```text
DATAFLOW_GEN2 / dataflow_gen2_incremental_bucket_v1
EXTERNAL_CDC  / debezium_kafka_v1
```

## 7. Fabric capture adapter requirements

Current adapter-contract implementation covers `FabricCaptureRequest`, `FabricNativeRunEvidence`, `FabricCaptureTransport`, capture adapters for Copy Job/Copy Activity/Dataflow Gen2/Spark and explicit `FabricAdapterRegistry`.

Deterministically certified:

- engine/execution-kind/role matching;
- capture adapter cannot silently own apply/state roles;
- FAILED/CANCELLED/UNKNOWN native status never yields success receipt;
- landing/source/snapshot mismatch fails closed;
- FRAMEWORK-owned bounded movement proves exact requested source bounds;
- native run ID retained;
- semantic adapter does not construct credentials/workspace clients.

Still required: actual Fabric REST/SDK/CLI transports, real run polling/correlation, approved authentication/environment bindings, Pipeline backend and real DEV evidence.

## 8. Debezium/Kafka provider requirements

Built-in adapter/profile:

```text
EXTERNAL_CDC / debezium_kafka_v1
```

Implemented adapter contract:

- Kafka `topic + partition + offset` is canonical physical order;
- DB LSN/binlog/source values remain provider metadata;
- `c/u/d` map to INSERT/UPDATE/DELETE;
- Kafka tombstone is transport cleanup, not duplicate DELETE;
- Debezium snapshot `op=r` is rejected by default and may only map to INSERT by explicit policy;
- Kafka record key is required explicitly;
- mixed topics, missing upper partition and record beyond frozen upper fail closed;
- provider adapter registry resolves explicitly by `(engine, profile)`.

Implemented safe resume planning:

```text
next_required = framework_committed_apply_offset + 1
```

The planner checks Kafka earliest-retained/latest-available evidence and fails if retention no longer covers the next unapplied event. External consumer-group progress is not accepted as downstream-success evidence.

Not yet implemented/proven:

- real Kafka client/consumer transport;
- consumer-group seek/commit coordination;
- connector/broker authentication/networking;
- rebalance/source-epoch semantics beyond fail-closed partition policy;
- real Debezium/Kafka end-to-end execution.

## 9. Recovery and reprocessing requirements

Canonical run modes:

```text
NORMAL
RETRY
BACKFILL
REPLAY
FULL_REBUILD
```

### 9.1 Recovery core — IMPLEMENTED reference

Implemented:

- RETRYABLE / NON_RETRYABLE / UNKNOWN_OUTCOME classification;
- bounded retry/backoff;
- attempt-specific dataset run IDs;
- immutable root/previous attempt lineage;
- retryability audit;
- retry exhaustion;
- reprocess request lifecycle;
- process-control exceptions not swallowed.

### 9.2 Unknown target mutation — IMPLEMENTED reference

```text
UNKNOWN_OUTCOME
    -> reconciliation
       COMMITTED     -> success; no rewrite
       NOT_COMMITTED -> retry may proceed
       UNRESOLVED    -> stop; no blind retry
```

### 9.3 Reprocess request contracts — IMPLEMENTED reference

- RETRY requires original dataset run ID.
- BACKFILL requires explicit lower/upper range.
- REPLAY requires original run or quarantine IDs.
- FULL_REBUILD requires explicit `authoritative_reset=true` intent.
- request semantic identity is immutable; lifecycle status may advance.

### 9.4 Strategy-specific recovery — PARTIAL

Implemented provider-specific piece:

- Debezium/Kafka safe retention-aware reread planning from framework CDC apply checkpoint.

Still required:

- quarantine payload REPLAY + `replayed_by_dataset_run_id` end to end;
- FULL_REBUILD target/state reset + rebuild orchestration;
- Copy/Dataflow/Mirroring/native-provider downstream-failure resume proofs;
- real Debezium/Kafka source-cursor commit coordination;
- freeze/reuse exact source windows for remaining capture families;
- durable target idempotency keys;
- supported operator CLI/API.

## 10. Control-plane requirements

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

`cdc_checkpoint` stores downstream framework CDC application positions, committing dataset run and optimistic-concurrency version. For FABRIC_NATIVE/EXTERNAL source progress, provider authority remains provider-owned.

Current SQLAlchemy/SQLite proof certifies schema/materialization/reference transaction boundaries only. A production persistent repository remains required.

## 11. Data quality/reconciliation

Required invariant:

```text
rows_read = rows_accepted + rows_quarantined + rows_intentionally_filtered
```

Implemented foundations include row DQ, explicit quarantine, row accounting, reconciliation results, publication/state gates and snapshot delete quarantine awareness.

Still required: persistent governed quarantine payload store integration, privacy/retention integration, poison-event policy and complete replay lifecycle.

## 12. CDC requirements — portable core IMPLEMENTED, provider integration PARTIAL

Canonical design: `docs/CDC_DESIGN.md`.

Implemented:

- provider-neutral I/U/D event/checkpoint contract;
- identity/dedupe/conflict/order proof;
- frozen complete upper window;
- CDC -> UPSERT/SCD1/SCD2;
- durable optimistic downstream checkpoint;
- snapshot/bootstrap fenced handoff;
- Debezium/Kafka provider normalization/profile/registry;
- Debezium/Kafka retention-aware safe reread planning.

Still required:

- real Kafka/Debezium transport and source-cursor commit evidence;
- additional provider adapters only where supported product scope requires them;
- provider transaction atomicity where required;
- poison-event quarantine/replay;
- real CDC source/Fabric evidence.

## 13. Schema and broader temporal correctness

General schema evolution remains PLANNED:

- fingerprint/version evidence;
- additive-compatible vs breaking classification;
- widening/narrowing rules;
- missing/extra column rules;
- controlled rebuild/cutover implications;
- schema-change audit.

General cross-strategy late/out-of-order taxonomy remains PARTIAL.

## 14. Orchestration requirements

Implemented reference: metadata selection/grouping, dependency/cycle validation, bounded concurrency, sibling failure isolation, dependent BLOCKED, unrelated continuation and criticality-aware pipeline status.

Still required: real Fabric Pipeline backend, cancellation/timeout propagation proof, real source/gateway/capacity tuning and operator-triggered reprocess wiring.

## 15. CI/CD and supply chain

Implemented/proven:

- GitHub PR CI Python 3.11/3.13;
- Ruff/compile/pip check/tests;
- wheel build;
- immutable v0.3.0 GitHub Release/checksum workflow;
- release manifest/environment binding separation;
- runtime state excluded from promotion;
- exact released framework wheel pinning by domains.

Latest provider CDC evidence:

```text
1087ab9231b9cb638a87bc2f78ef0c1b1fe32beb / 33219601375 / 179 passed
ecdca38099a4f21c6f40701dc14889b464c20608 / 33219783325 / 183 passed
```

Still required for next release: real Fabric/provider artifact/environment execution and smoke evidence.

## 16. Security/external controls

Framework requirements:

- no credentials in semantic metadata;
- logical connection/secret refs only;
- physical IDs via environment bindings;
- no token/secret logging;
- auditable reprocess/quarantine/operator intent;
- least-privilege-compatible adapters.

External evidence required includes Entra/service principals/workspace identity/RBAC, tenant settings, gateway/private networking, secret authority, source CDC enablement/retention, broker/database access, production backup/restore, monitoring/on-call, data retention/privacy and capacity policy.

## 17. Release blockers from current head

Do **not** publish `v0.4.0` yet.

CDC canonical correctness, bootstrap and one Debezium/Kafka reference provider adapter are no longer release-gap placeholders. Current material blockers are:

1. strategy-specific recovery completion: quarantine REPLAY, FULL_REBUILD and remaining native-progress recovery;
2. real Debezium/Kafka source-cursor/transport integration and real Fabric transports;
3. APPEND identity semantics or explicit milestone deferral;
4. general schema evolution policy;
5. file/API capture guardrails for broader source coverage;
6. supported persistent control-plane/operator surface or clearly bounded release scope;
7. real Fabric Pipeline/backend implementation;
8. at least one approved DEV hybrid execution retaining native/provider correlation;
9. final audit/docs/CI against exact candidate head.

Framework UPSERT, capture/apply executor separation, Fabric capture adapter contracts, recovery core, canonical CDC, durable CDC checkpointing, snapshot->CDC handoff and Debezium/Kafka reference normalization/resume planning are implemented reference capabilities.
