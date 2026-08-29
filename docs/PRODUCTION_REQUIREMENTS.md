# Production Requirements — fabric-data-framework

Status: Canonical requirements baseline
Last updated: 2026-08-29

## Product contract and evidence levels

`fabric-data-framework` is a reusable enterprise wheel. Routine datasets should onboard through source-controlled semantic metadata, environment bindings, certified capability profiles and bounded domain extensions rather than framework forks.

Evidence levels remain distinct: portable semantics, deterministic CI certification, real Fabric/provider execution, and external enterprise controls. Reference tests must never be described as real service evidence.

## Architecture invariants

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
12. Source order and event/valid time are independent clocks.
13. Real Fabric/provider/security/capacity evidence must not be fabricated by reference tests.

## Capture requirements

Canonical strategies:

```text
FULL | WATERMARK | CDC | SNAPSHOT | MIRROR | STREAM
```

Implemented reference guarantees include FULL/SNAPSHOT completeness evidence, composite WATERMARK + overlap, typed CaptureReceipt, canonical CDC order/dedupe/frozen windows, downstream CDC checkpoints, snapshot->CDC handoff, Debezium/Kafka normalization/resume planning, Fabric capture adapter contracts, immutable file manifests and frozen API windows/cursor chains.

Still required: real Fabric transports/polling, live Kafka consumer/seek/commit, real auth/network/gateway/capacity evidence and additional provider adapters only where supported scope requires them.

## Apply requirements

```text
APPEND | REPLACE | UPSERT | SCD1 | SCD2 | SNAPSHOT_DIFF
```

All six have framework-owned reference implementations. APPEND requires explicit `append_identity`, exact replay is a no-op, and conflicting identity/payload fails closed. REPLACE and SNAPSHOT_DIFF require isolated candidates/completeness guards. UPSERT/SCD1 share ordered current-state correctness. SCD2 preserves deterministic history.

`CDC != SCD2` and `FULL != REPLACE` remain invariants. Provider-native merge/SCD features are not automatically equivalent.

## Temporal requirements

Shared taxonomy is now IMPLEMENTED reference:

```text
source order: STALE | EQUAL | NEWER
event time:   EARLIER | EQUAL | LATER | UNKNOWN
```

Batch UPSERT/SCD1 and CDC current-state consume shared source-order comparison. CDC-SCD2 consumes the same source-order path plus shared event-time comparison.

A newer source event with an earlier valid/event time is classified as `LATE_EVENT_TIME` and `requires_history_rewrite=true`. Retroactive SCD2 history rewrite itself remains intentionally unsupported and must fail closed unless a future explicit policy certifies it.

## Schema requirements

Schema is a source-controlled semantic contract, not an engine auto-merge side effect.

Current compatibility policy:

```text
EXACT | ADDITIVE_ONLY | SAFE_EVOLUTION
```

SAFE_EVOLUTION only accepts explicitly certified widening/relaxation such as INT32->INT64, FLOAT32->FLOAT64, compatible STRING widening, DECIMAL precision widening at stable scale and required->nullable. Removal, narrowing, required additions, nullable->required, scale changes and uncertified cross-family conversions fail closed.

Deployment versions/materializes `dataset_contract`; runtime observations append environment-local `schema_change` evidence.

## File/API source requirements

File capture freezes provider listing/snapshot reference plus URI, stable version token, size, timezone-aware modification evidence and readiness into a deterministic complete manifest. Retry/replay must prove the same manifest.

API capture freezes lower/upper logical bounds and predicate identity before page 1, then proves contiguous cursor/page sequence, no cycle, explicit completeness, terminal cursor, bounded page/record count and row accounting. Retry/replay must use the same frozen window.

Provider SDK/HTTP/auth/retry-after details remain integration concerns.

## Execution/delegation requirements

Capture engines:

```text
FABRIC_COPY_JOB | FABRIC_COPY_ACTIVITY | DATAFLOW_GEN2 | SPARK |
FABRIC_MIRRORING | EXTERNAL_CDC | SQL | CUSTOM
```

Named profiles require explicit engines. Unsupported capture/apply/progress/order combinations fail before mutation. Capture capability does not imply apply capability. AUTO resolves before execution; silent switching is forbidden.

## Recovery/idempotency requirements

Canonical modes:

```text
NORMAL | RETRY | BACKFILL | REPLAY | FULL_REBUILD
```

Implemented reference behavior includes bounded retry, attempt lineage, reprocess lifecycle, unknown-outcome COMMITTED/NOT_COMMITTED/UNRESOLVED resolution, quarantine REPLAY and guarded FULL_REBUILD.

Still required: durable target-operation idempotency/operation journal with stable semantic operation keys; native/provider downstream-failure recovery; real Kafka cursor coordination.

## Control-plane/operator requirements

Current schema version: `3`.

Promotable definitions remain distinct from environment-local migrations, overrides, checkpoints, runs, receipts, reconciliation/quarantine/schema/reprocess/deployment evidence.

The read-only operator surface is IMPLEMENTED reference and must expose typed stable views rather than raw SQL rows. It currently answers latest run/lineage, latest capture correlation, WATERMARK/CDC progress, reconciliation, unreplayed quarantine backlog, latest schema observation and active reprocess requests. `fabric-framework control-plane-status` exposes the same information as JSON.

A production persistent store is still unselected/unproven. Operator mutation/approval workflows remain outside the current reference surface.

## DQ/reconciliation requirements

For bounded row flows:

```text
rows_read = rows_accepted + rows_quarantined + rows_intentionally_filtered
```

Required reconciliation can block publication/state advancement. Governed quarantine payload storage, privacy/retention and authenticated operator replay integration belong to production deployment.

## Orchestration requirements

Reference dispatcher/planner supports metadata selection/grouping, dependency/cycle validation, bounded concurrency, sibling isolation, dependent BLOCKED, unrelated continuation and criticality-aware aggregate status.

Real Fabric Pipeline backend and provider-specific cancellation/timeout/tuning remain required.

## CI/CD and supply chain

Implemented/proven: Python 3.11/3.13 PR CI, Ruff/compile/pip check/tests, wheel build, immutable v0.3.0 release/checksum workflow, release/environment binding separation, runtime-state exclusion from promotion and exact framework version pinning by domains.

Latest deterministic baseline:

```text
ae1eb99ab5fa9d7add5a62dda2d7448b6200d240
Actions 33225341709
268 passed
```

## Security/external controls

Framework metadata stores logical connection/secret refs, not credentials. External proof is required for Entra/workspace identity/RBAC, tenant settings, gateway/private networking, source CDC/retention, Kafka/database access, backup/restore, monitoring/on-call, privacy/retention and capacity policy.

## Current release blockers

Do **not** publish `v0.4.0` yet.

Material blockers now are:

1. durable target-operation idempotency and remaining provider/native recovery required by release scope;
2. real Fabric/Kafka transports and Fabric Pipeline backend;
3. approved DEV hybrid execution retaining real native/provider correlation;
4. selected/certified production control-plane store and concurrency/migration governance, or an explicitly bounded release promise;
5. final exact-head audit/docs/CI.

APPEND, schema evolution, file/API replay stability, shared temporal taxonomy and read-only operator diagnostics are no longer open placeholders.
