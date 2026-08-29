# Production Requirements — fabric-data-framework

Status: Canonical requirements baseline
Last updated: 2026-08-29

## 1. Product contract

`fabric-data-framework` is a reusable enterprise wheel. Routine datasets should onboard through source-controlled semantic metadata, environment bindings, certified capability profiles and bounded domain extensions rather than framework forks.

Evidence levels remain distinct:

1. portable semantics;
2. deterministic CI certification;
3. real Fabric/provider execution;
4. external enterprise controls.

Reference tests must never be described as real service evidence.

## 2. Architecture invariants

1. Capture strategy and apply strategy are independent.
2. Capture/movement engine and apply engine are independent.
3. One physical capture has one source-progress authority: FRAMEWORK, FABRIC_NATIVE or EXTERNAL.
4. Native/provider capture hands off through immutable typed evidence.
5. Provider CDC coordinates normalize before canonical CDC logic.
6. Provider source progress and framework downstream semantic progress are distinct.
7. Dataset is the default failure/retry boundary.
8. Runtime state/evidence is environment-local and never promoted.
9. State advances only after required target/reconciliation evidence.
10. Unknown target writes are reconciled before retry.
11. Retry/replay must not silently change the source window/set.
12. Real Fabric/provider/security/capacity evidence must not be fabricated by reference tests.

## 3. Capture requirements

Canonical strategies:

```text
FULL | WATERMARK | CDC | SNAPSHOT | MIRROR | STREAM
```

Current implemented reference guarantees:

- FULL snapshot identity/completeness evidence;
- SNAPSHOT completeness evidence before delete inference;
- composite WATERMARK + overlap;
- typed CaptureReceipt;
- single physical capture progress authority;
- canonical CDC event/order/dedupe/window contracts;
- durable downstream CDC checkpointing;
- snapshot/bootstrap -> CDC fenced handoff;
- Debezium/Kafka normalization and retention-aware safe resume planning;
- Fabric Copy Job/Copy Activity/Dataflow Gen2/Spark capture adapter contracts;
- immutable file-manifest freeze/readiness/completeness/version guardrails;
- frozen API window + cursor-chain/page/record/completeness guardrails.

Still required/proven externally:

- real Fabric REST/SDK/CLI transport and polling;
- real Kafka consumer/seek/commit behavior;
- additional provider adapters only where supported scope requires them;
- real source/gateway/network/auth/capacity evidence.

## 4. Apply requirements

Canonical strategies:

```text
APPEND | REPLACE | UPSERT | SCD1 | SCD2 | SNAPSHOT_DIFF
```

| Strategy | Current requirement/evidence |
|---|---|
| APPEND | IMPLEMENTED reference — explicit `append_identity`, exact replay no-op, conflicting identity/payload fail closed |
| REPLACE | IMPLEMENTED reference — isolated candidate, completeness/empty/drop guards, reconciliation before publish |
| UPSERT | IMPLEMENTED reference — composite key, deterministic order/idempotency/stale/equal-position rules |
| SCD1 | IMPLEMENTED reference — ordered current-state semantics shared with UPSERT |
| SCD2 | IMPLEMENTED reference — deterministic history and CDC source-order/valid-time separation |
| SNAPSHOT_DIFF | IMPLEMENTED reference — complete snapshot + guarded I/U/D inference |

`CDC != SCD2`, `FULL != REPLACE`, and provider-native features are not automatically semantically equivalent.

## 5. APPEND requirements

APPEND must never mean blind duplicate insertion.

Source-controlled `append_identity` is required. The framework derives stable reserved identity/payload evidence from business payload, not attempt-specific lineage.

Required behavior:

- missing/null identity fails;
- exact duplicate within a batch is suppressed;
- same identity with different payload in one batch fails;
- exact target replay is a no-op;
- target identity collision with changed business payload fails;
- target mutation occurs only after validation/staging/reconciliation gates.

## 6. Current-state and temporal requirements

UPSERT/SCD1 must preserve deterministic ordering, exact rerun idempotency, stale behavior and equal-position conflict failure.

CDC current-state apply must support I/U/D/reinsert, explicit delete policy and row-level source-position evidence after CDC mutation.

CDC SCD2 keeps two clocks separate:

```text
source position -> event order
event_time      -> valid interval
```

Retroactive valid-time correction is currently fail-closed. A shared cross-strategy late/out-of-order taxonomy remains required so strategy-specific terms do not drift.

## 7. Schema requirements

Schema is a source-controlled semantic contract, not an engine auto-merge side effect.

Current typed contract supports:

```text
EXACT
ADDITIVE_ONLY
SAFE_EVOLUTION
```

Current SAFE_EVOLUTION examples:

- INT32 -> INT64;
- FLOAT32 -> FLOAT64;
- compatible STRING widening/unbounded relaxation;
- DECIMAL precision widening at unchanged scale;
- required -> nullable.

Must fail closed on removal, narrowing, required column addition, nullable -> required, DECIMAL scale change and uncertified cross-family conversion.

Deployment must version/materialize `dataset_contract`. Runtime observations must append environment-local `schema_change` evidence.

## 8. File capture requirements

A file capture used for retry/replay safety must freeze:

- provider listing/snapshot reference;
- source URI;
- stable version token;
- size and timezone-aware last-modified evidence;
- readiness;
- complete-discovery proof;
- deterministic manifest fingerprint.

Default behavior rejects incomplete discovery, empty manifest, non-ready objects, duplicate path, same path with multiple versions and policy volume breaches. Retry/replay must prove the same manifest fingerprint.

## 9. API capture requirements

API capture must freeze logical lower/upper bounds and predicate/filter identity before page 1.

Pagination must prove:

- contiguous page numbers;
- exact request/next-cursor chain;
- no cursor cycles/repeated next cursors;
- explicit completeness;
- terminal cursor when required;
- bounded page/record counts;
- page-count row accounting equals declared total;
- empty result only under explicit policy;
- retry/replay uses the same frozen window fingerprint.

Provider HTTP/auth/retry-after/client behavior remains adapter/domain integration work.

## 10. Execution engine requirements

Capture engines:

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

Named profile requires explicit engine. Unsupported engine/capture/apply/progress/order combinations fail before mutation. Capture capability does not imply apply capability. AUTO resolves before execution; silent runtime switching is forbidden.

## 11. Recovery requirements

Canonical modes:

```text
NORMAL | RETRY | BACKFILL | REPLAY | FULL_REBUILD
```

Implemented reference core:

```text
RETRYABLE       -> bounded retry
NON_RETRYABLE   -> stop
UNKNOWN_OUTCOME -> reconcile first
```

Unknown target outcome:

```text
COMMITTED     -> converge success
NOT_COMMITTED -> retry may proceed
UNRESOLVED    -> stop
```

Quarantine REPLAY requires immutable original evidence, governed external payload retrieval, identity/row-count validation and replay marker advancement only after target/reconciliation gate.

FULL_REBUILD requires explicit `authoritative_reset=true`, stable destructive-operation identity and optimistic capture-aware state cutover after authoritative rebuild completion.

Remaining recovery scope: native Fabric/provider downstream-failure resume, durable physical-target idempotency and live source-cursor coordination.

## 12. Control-plane requirements

Current reference schema version: `3`.

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

Migration history must correspond to actual successful schema change. v3 proves real additive migration of `append_identity` for an existing v2 store.

SQLite/in-memory are reference proof only. A supported persistent repository/query surface remains required.

## 13. DQ/reconciliation requirements

For bounded row flows:

```text
rows_read = rows_accepted + rows_quarantined + rows_intentionally_filtered
```

Required reconciliation can block publication/state advancement. Governed quarantine payload storage, privacy/retention and operator replay integration must be supplied by production deployment.

## 14. Orchestration requirements

Reference dispatcher/planner must support metadata selection/grouping, dependency/cycle validation, bounded concurrency, sibling failure isolation, dependent BLOCKED state, unrelated continuation and criticality-aware aggregate status.

Real Fabric Pipeline backend, cancellation/timeout propagation and provider-specific operational tuning remain required.

## 15. CI/CD and supply chain

Implemented/proven:

- GitHub PR CI on Python 3.11 and 3.13;
- Ruff/compile/pip check/tests;
- wheel build;
- immutable v0.3.0 release/checksum workflow;
- environment binding separated from immutable release identity;
- runtime state excluded from promotion;
- domain exact pinning of released framework wheel.

Latest deterministic baseline:

```text
c326f062ad4e6be5185f17b9e6830946967361ab
Actions 33224558393
252 passed
```

## 16. Security/external controls

Framework metadata contains logical connection/secret refs, not credentials. Physical IDs come from environment bindings. Secrets/tokens must not be logged.

External proof is required for Entra/workspace identity/RBAC, tenant settings, gateway/private networking, source CDC configuration/retention, Kafka/database access, backup/restore, monitoring/on-call, retention/privacy and capacity policy.

## 17. Release blockers from current head

Do **not** publish `v0.4.0` yet.

Material blockers now are:

1. real Fabric/Kafka transports and Fabric Pipeline backend;
2. at least one approved DEV hybrid execution retaining native/provider correlation;
3. supported persistent control-plane/operator surface or explicitly bounded release promise;
4. shared late/out-of-order taxonomy and remaining provider/native recovery/idempotency hardening as required by release scope;
5. final exact-head audit/docs/CI.

APPEND, general schema compatibility, file-manifest and API-window guardrails are no longer open placeholders.
