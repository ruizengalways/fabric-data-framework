# Durable Target-Operation Idempotency

Status: canonical framework contract for unreleased `0.4.0`

## Why this exists

A data pipeline can receive an ambiguous response after a target write:

```text
framework submits MERGE/SCD2/REPLACE
        |
        v
target may commit successfully
        |
        x  connection timeout / driver crash / notebook termination
        |
        v
framework cannot prove whether the mutation committed
```

Blindly retrying the write can duplicate APPEND rows, repeat side effects, corrupt SCD2 history, or apply a batch twice. Advancing a watermark/checkpoint without proving the target commit can instead lose data.

The framework therefore gives every *semantic target mutation* a stable operation key and persists its lifecycle before the physical write is allowed to execute.

## Two identities: logical operation vs physical attempt

Do not use `dataset_run_id` as the idempotency key. A retry intentionally receives a new physical run ID.

`TargetOperationIntent` identifies the logical mutation with:

| Field | Meaning |
|---|---|
| `dataset_id` | Framework dataset identity |
| `operation_kind` | Apply semantic, e.g. `APPEND`, `UPSERT`, `SCD1`, `SCD2`, `REPLACE`, `SNAPSHOT_DIFF` |
| `target_reference` | Stable target object identity |
| `effective_config_hash` | Exact effective framework/domain config that defines the mutation |
| `input_fingerprint` | Stable fingerprint of the frozen source input/boundary |
| `semantic_version` | Version of the operation-key contract; default `1` |

The operation key is SHA-256 over a canonical JSON representation of those fields. Attempt number, `dataset_run_id`, current time, worker ID, Spark application ID and Fabric activity run ID are deliberately excluded.

### What should go into `input_fingerprint`

Use `fingerprint_semantic_payload(...)` over immutable evidence that reproduces the same logical target write.

| Capture pattern | Recommended fingerprint payload |
|---|---|
| Full snapshot | snapshot ID + frozen file/object manifest or source snapshot token |
| Watermark | lower bound + upper bound + tie-breaker boundary + overlap policy identity |
| CDC / Debezium | lower checkpoint + frozen upper checkpoint/offset map |
| Delta CDF | lower committed version + frozen upper Delta commit version |
| Incremental files | frozen manifest containing path + generation/etag/hash |
| API cursor | frozen request window + page/cursor evidence |
| Replay | original quarantine IDs + governed payload/source references |
| Full rebuild | authoritative reset request ID + frozen rebuild source scope |

Do **not** fingerprint runtime-local timestamps or retry IDs. Doing so would create a new operation key for every retry and defeat idempotency.

## Persistent control-plane model

Control-plane schema v4 adds two environment-local tables.

### `target_operation`

One current row per semantic operation key. It is the compare-and-swap state used to decide whether execution is permitted.

Important fields:

```text
operation_key PK
semantic identity fields
status
owner_dataset_run_id
attempt
version
outcome_reference
error_code / error_message
created_at / updated_at / completed_at
```

### `target_operation_event`

Append-only lifecycle evidence. Every successful create/transition writes an event in the same transaction as the current-state mutation.

This table answers questions such as:

- which physical attempt first claimed the write;
- why a retry was blocked;
- which reconciliation proved `NOT_COMMITTED`;
- which retry later executed;
- which target-native reference proved success.

## State machine

```text
               target write confirmed
           +---------------------------> SUCCEEDED
           |
           |
IN_PROGRESS+---- ambiguous response ----> UNKNOWN
           |                                  |
           |                                  | probe proves committed
           |                                  +-----------------> SUCCEEDED
           |                                  |
           |                                  | probe proves no commit
           |                                  v
           +---- proof no commit --------> NOT_COMMITTED
                                              |
                                              | next claim (CAS)
                                              v
                                         IN_PROGRESS
```

Allowed transitions are intentionally narrow:

| Before | Allowed after |
|---|---|
| `IN_PROGRESS` | `SUCCEEDED`, `UNKNOWN`, `NOT_COMMITTED` |
| `UNKNOWN` | `SUCCEEDED`, `UNKNOWN`, `NOT_COMMITTED` |
| `NOT_COMMITTED` | `IN_PROGRESS` |
| `SUCCEEDED` | none |

`SUCCEEDED` is terminal. A completed logical mutation cannot be reopened under the same semantic operation key.

## Claim decision

`claim_target_operation(...)` is the gate before a physical target write.

| Existing durable state | Claim action | Meaning |
|---|---|---|
| no row | `EXECUTE` | create `IN_PROGRESS`; caller owns the first execution |
| `SUCCEEDED` | `SKIP_SUCCEEDED` | mutation is already proven complete; do not write again |
| `IN_PROGRESS` | `RECONCILE_REQUIRED` | previous process may have committed before dying; do not blindly retry |
| `UNKNOWN` | `RECONCILE_REQUIRED` | ambiguous outcome is explicit; probe target/provider evidence |
| `NOT_COMMITTED` | `EXECUTE` | CAS to a new `IN_PROGRESS` version; safe retry is allowed |

The important rule is that an old `IN_PROGRESS` is treated as uncertain, not as permission to steal the operation. Process death can occur after the physical commit and before the success journal update.

## Golden execution order

For every framework-owned target mutation:

```text
1. Freeze capture/source input
2. Compute TargetOperationIntent + operation_key
3. claim_target_operation()
4. Branch on claim.action
   EXECUTE
       -> perform physical target mutation
       -> persist SUCCEEDED, UNKNOWN, or NOT_COMMITTED
   SKIP_SUCCEEDED
       -> do not mutate target again
   RECONCILE_REQUIRED
       -> probe target/provider evidence
       -> persist reconciliation result
       -> only NOT_COMMITTED may later claim EXECUTE
5. Run required reconciliation/data-quality checks
6. Build StateCommitGate(target_committed=True, ...)
7. Advance framework watermark / CDC checkpoint / replay marker
```

The target-operation journal does not replace `StateCommitGate`. It supplies durable proof for the `target_committed` side of that gate.

## Framework API example

```python
from uuid import uuid4

from fabric_data_framework import (
    TargetOperationAction,
    TargetOperationIntent,
    claim_target_operation,
    fingerprint_semantic_payload,
    mark_target_operation_succeeded,
)

input_fingerprint = fingerprint_semantic_payload(
    {
        "lower": {"updated_at": "2026-08-28T00:00:00Z", "id": 100},
        "upper": {"updated_at": "2026-08-29T00:00:00Z", "id": 900},
        "capture_receipt": "receipt-42",
    }
)
intent = TargetOperationIntent(
    dataset_id="crm.customer",
    operation_kind="SCD1",
    target_reference="silver.customer",
    effective_config_hash=effective_config_hash,
    input_fingerprint=input_fingerprint,
)

claim = claim_target_operation(
    engine,
    intent=intent,
    dataset_run_id=dataset_run_id,
    attempt=attempt,
)

if claim.action is TargetOperationAction.EXECUTE:
    result = apply_to_target(...)
    record = mark_target_operation_succeeded(
        engine,
        operation_key=intent.operation_key,
        expected_version=claim.record.version,
        dataset_run_id=dataset_run_id,
        attempt=attempt,
        outcome_reference=result.native_commit_reference,
    )
elif claim.action is TargetOperationAction.SKIP_SUCCEEDED:
    record = claim.record
else:
    # Probe target-native evidence before doing another write.
    ...
```

## Unknown outcome and the existing recovery loop

The existing recovery contract already uses:

```text
COMMITTED
NOT_COMMITTED
UNRESOLVED
```

`reconcile_target_operation(...)` persists that decision before the recovery loop acts on it.

Example callback shape:

```python
def resolve_unknown_outcome(context, exc):
    current = read_target_operation(engine, operation_key)
    resolution, evidence_ref = probe_target_commit(operation_key, current)

    reconcile_target_operation(
        engine,
        operation_key=operation_key,
        expected_version=current.version,
        resolution=resolution,
        dataset_run_id=context.dataset_run_id,
        attempt=context.attempt,
        outcome_reference=evidence_ref,
        error_message=str(exc),
    )
    return resolution
```

Then pass the callback to `execute_with_retry(...)` as `resolve_unknown_outcome`.

This preserves the existing fail-closed behavior while making the reconciliation decision durable across process restarts.

## Target adapter requirement

The framework can provide semantic idempotency, but a real adapter must still define how a target outcome is proven.

An apply adapter/profile that may return an ambiguous commit result should be able to provide one or more of:

- a target-native transaction/statement/job ID;
- a Delta commit/version reference;
- a deterministic audit marker written atomically with the business mutation;
- a provider API capable of looking up the submitted operation;
- a target query that can prove the exact semantic batch was or was not applied.

If the adapter cannot distinguish committed from not committed, reconciliation returns `UNRESOLVED`; the framework remains blocked rather than performing a blind retry.

## Examples by apply strategy

### APPEND

APPEND already requires row-level `append_identity`. The operation journal adds batch/operation-level protection. Both are useful:

```text
operation journal: prevents replaying the whole append batch after ambiguous submit
append_identity:   prevents duplicate logical rows within/replayed across batches
```

### UPSERT / SCD1

Even if a MERGE is logically idempotent for current values, repeated execution can still produce incorrect audit timestamps, mutation counts, downstream CDF events, or side effects. Journal the logical batch.

### SCD2

This is the highest-risk retry case. Reapplying the same change after an ambiguous commit can create duplicate versions or close the wrong interval. Never blind-retry SCD2 after `IN_PROGRESS`/`UNKNOWN`.

### REPLACE / full snapshot

Fingerprint the exact authoritative snapshot. A retry with the same frozen snapshot uses the same operation key. A genuinely newer snapshot receives a different key.

### SNAPSHOT_DIFF

Fingerprint both the authoritative new snapshot and the baseline identity/state version used to compute the diff. If the baseline changes, it is a different semantic operation.

## Concurrency behavior

Every current-state update includes the expected operation `version` in the SQL predicate. A stale writer receives `TargetOperationVersionConflict` and must reread state; it cannot overwrite a newer reconciliation or success result.

A concurrent first claim is also fail-closed through the primary key on `operation_key`. One writer wins; the other must reread the durable state.

## Operational investigation

For one operation key, inspect current state first and then ordered events:

```sql
SELECT *
FROM target_operation
WHERE operation_key = :operation_key;

SELECT *
FROM target_operation_event
WHERE operation_key = :operation_key
ORDER BY version, occurred_at;
```

A normal ambiguous-then-safe-retry lifecycle looks like:

```text
v1 IN_PROGRESS      run A attempt 1
v2 UNKNOWN          run A attempt 1
v3 NOT_COMMITTED    run B attempt 2   provider probe evidence retained
v4 IN_PROGRESS      run B attempt 2
v5 SUCCEEDED        run B attempt 2   target commit reference retained
```

If the current state is `UNKNOWN`, operator automation should investigate/reconcile; it should not reset the row manually to `NOT_COMMITTED` without evidence.

## Failure-safety invariants

The implementation is designed to preserve these invariants:

1. one semantic input + config + target + apply meaning -> one stable operation key;
2. physical retry IDs do not change that key;
3. `SUCCEEDED` never executes again;
4. `IN_PROGRESS` after process re-entry is treated as uncertain;
5. `UNKNOWN` never executes again without reconciliation;
6. only durable `NOT_COMMITTED` evidence reopens execution;
7. stale writers cannot overwrite newer state because every mutation is CAS-versioned;
8. every successful state mutation leaves append-only event evidence;
9. framework watermark/checkpoint advancement remains separately gated by target commit + reconciliation.

## Evidence boundary

The deterministic framework tests can prove key stability, state-machine behavior, CAS conflict handling, retry blocking and persistence semantics against the relational reference store.

They do **not** prove that a Fabric Warehouse, Lakehouse Delta write, Spark job, Kafka sink or other real provider exposes enough native evidence to resolve an ambiguous commit. That remains provider/profile integration evidence and must be retained separately before production claims are made.
