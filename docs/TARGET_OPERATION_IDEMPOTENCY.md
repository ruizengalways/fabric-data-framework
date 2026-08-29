# Target Operation Idempotency and Durable Mutation Journal

Status: Canonical recovery/idempotency design and implementation guide  
Last updated: 2026-08-29

## 1. Why this exists

A dataset retry is not automatically a safe target retry.

The dangerous production case is:

```text
framework sends target mutation
        |
        v
target may commit
        |
network / driver / Spark task fails before acknowledgement
        |
        v
framework sees exception
```

At this point there are two possible realities:

```text
A. target did not commit
B. target committed but acknowledgement was lost
```

Blindly running the same MERGE/REPLACE/SCD2 mutation again may duplicate work, corrupt history, close the wrong SCD2 version, repeat a destructive replacement or create inconsistent audit/state.

The framework therefore separates:

```text
dataset attempt identity
        !=
target operation identity
```

A retry creates a new `dataset_run_id`, but a retry of the **same frozen semantic mutation** must reuse one stable `operation_key`.

---

## 2. Core invariant

> **One frozen semantic target mutation has one durable operation key across attempts and process restarts.**

The operation key deliberately excludes:

```text
dataset_run_id
pipeline_run_id
attempt number
wall-clock retry time
worker/Spark session identity
```

Those identify execution attempts, not the mutation itself.

The key is derived from:

```text
target-operation-v1
+ dataset_id
+ run_mode
+ apply_strategy
+ target_reference
+ effective_config_hash
+ mutation_scope_hash
```

In code:

```python
spec = TargetOperationSpec(
    dataset_id="crm.customer",
    run_mode=RunMode.NORMAL,
    apply_strategy=ApplyStrategy.SCD1,
    target_reference="silver.crm_customer",
    effective_config_hash=effective.effective_config_hash,
    mutation_scope_hash=scope_hash,
)

operation_key = spec.operation_key
```

If any semantic component changes, the operation key changes.

---

## 3. The most important field: mutation_scope_hash

`mutation_scope_hash` answers:

> **Exactly which frozen input/evidence is this target mutation intended to apply?**

It is not a random request ID. It is a deterministic hash of the immutable mutation scope.

The owning executor must build it **before target mutation** from the source/candidate evidence that defines the target change.

Recommended rule:

```python
mutation_scope_hash = canonical_hash(frozen_mutation_scope)
```

The scope should include stable semantic evidence, not volatile execution details.

Bad scope:

```json
{
  "dataset_run_id": "new UUID every retry",
  "started_at": "current time"
}
```

That would generate a different operation key on every retry and defeat idempotency.

Good scope:

```json
{
  "capture": "WATERMARK",
  "lower": ["2026-08-29T00:00:00Z", "C100"],
  "upper": ["2026-08-29T01:00:00Z", "C900"],
  "candidate_hash": "..."
}
```

A new frozen source range produces a new operation key; a retry of the same range does not.

---

## 4. Lifecycle

Current durable states:

```text
PREPARED
IN_PROGRESS
COMMIT_UNKNOWN
COMMITTED
NOT_COMMITTED
FAILED
```

State machine:

```text
PREPARED
   |
   +--> IN_PROGRESS
   |       |
   |       +--> COMMITTED
   |       +--> COMMIT_UNKNOWN
   |       +--> NOT_COMMITTED
   |       +--> FAILED
   |
   +--> FAILED

COMMIT_UNKNOWN
   |
   +--> COMMITTED
   +--> NOT_COMMITTED

NOT_COMMITTED
   |
   +--> IN_PROGRESS
   +--> FAILED

COMMITTED  terminal
FAILED     terminal
```

The critical rule is:

> **Only `NOT_COMMITTED` is eligible for target re-execution.**

`COMMIT_UNKNOWN` is not retry permission.

---

## 5. What happens on each attempt

Before target mutation:

```text
1. compute stable TargetOperationSpec
2. reserve operation row
3. inspect current durable status
```

Then:

```text
PREPARED
  -> CAS to IN_PROGRESS
  -> execute mutation

COMMITTED
  -> return converged success
  -> DO NOT mutate target again

FAILED
  -> stop; terminal semantic failure

IN_PROGRESS from a previous attempt/process
  -> treat as uncertain outcome
  -> reconcile before any replay

COMMIT_UNKNOWN
  -> reconcile before any replay

NOT_COMMITTED
  -> CAS to IN_PROGRESS
  -> safe re-execution
```

The journal uses optimistic compare-and-swap through `version` so stale writers cannot silently overwrite newer operation state.

---

## 6. Exception classification around the target write

Once the operation is `IN_PROGRESS`, exceptions are interpreted conservatively.

### Explicit retryable / known not committed

```python
raise RetryableExecutionError(...)
```

means the target adapter/executor knows the operation did not commit.

Journal:

```text
IN_PROGRESS -> NOT_COMMITTED
```

The outer retry loop may retry the same operation key with a new dataset attempt.

Typical examples:

- source/preparation failure before target transaction begins;
- warehouse rejected transaction before commit;
- explicit target rollback confirmed;
- lock/deadlock failure with documented rollback semantics.

Do not classify a timeout after sending COMMIT as ordinary retryable unless the target API proves rollback.

### Explicit permanent / known failed

```python
raise PermanentExecutionError(...)
```

Journal:

```text
IN_PROGRESS -> FAILED
```

No automatic target retry.

Typical examples:

- incompatible schema contract;
- deterministic merge-key violation;
- invalid target constraint;
- unsupported mutation semantics.

### Unknown commit outcome

```python
raise UnknownCommitOutcomeError(...)
```

Journal:

```text
IN_PROGRESS -> COMMIT_UNKNOWN
```

The framework requires target-specific reconciliation.

Typical examples:

- driver timeout while commit response is lost;
- REST request timeout after server accepted mutation;
- Spark/warehouse client disconnect after mutation submission;
- target job ID exists but completion cannot be read.

### Unclassified exception after mutation starts

The framework also treats a generic unexpected exception as unknown:

```text
IN_PROGRESS -> COMMIT_UNKNOWN
```

This is intentionally conservative. A random socket reset is not evidence that the target rolled back.

---

## 7. Unknown-outcome reconciliation

Target-specific reconciliation returns:

```text
COMMITTED
NOT_COMMITTED
UNRESOLVED
```

with an optional `evidence_reference`.

Example:

```python
return TargetOperationReconciliation(
    resolution=UnknownOutcomeResolution.COMMITTED,
    evidence_reference="warehouse-transaction:7f8a...",
)
```

### COMMITTED

```text
COMMIT_UNKNOWN -> COMMITTED
```

The framework converges without target re-execution.

### NOT_COMMITTED

```text
COMMIT_UNKNOWN -> NOT_COMMITTED
```

Now and only now may the retry loop re-issue the same semantic mutation.

### UNRESOLVED

The framework stops.

```text
COMMIT_UNKNOWN remains uncertain
no state/checkpoint advance
no blind target replay
operator intervention / later reconciliation required
```

This fail-closed behavior is preferred to silent duplicate mutation.

---

# 8. How to calculate mutation_scope_hash by capture pattern

The exact payload is executor-specific, but the following patterns are the recommended semantic minimum.

## 8.1 WATERMARK -> UPSERT / SCD1 / SCD2

Suppose the frozen window is:

```text
lower = (2026-08-29T00:00:00Z, customer_id=C100)
upper = (2026-08-29T01:00:00Z, customer_id=C900)
overlap = 600 seconds
```

Recommended scope:

```python
scope_hash = canonical_hash(
    {
        "kind": "watermark-window-v1",
        "lower": {
            "value": "2026-08-29T00:00:00Z",
            "tie_breaker": ["C100"],
        },
        "upper": {
            "value": "2026-08-29T01:00:00Z",
            "tie_breaker": ["C900"],
        },
        "overlap_seconds": 600,
        "candidate_hash": candidate_hash,
    }
)
```

Retry attempt 2 must reuse this exact scope.

A later normal run with upper `02:00` gets a different scope and operation key.

Do not hash only the current watermark state; include the frozen upper boundary/candidate identity.

---

## 8.2 CDC / Debezium / Delta CDF -> UPSERT / SCD1 / SCD2

Recommended scope:

```python
scope_hash = canonical_hash(
    {
        "kind": "cdc-window-v1",
        "lower_checkpoint": lower_checkpoint.model_dump(mode="json"),
        "upper_checkpoint": upper_checkpoint.model_dump(mode="json"),
        "normalized_batch_hash": canonical_hash(
            [event.model_dump(mode="json") for event in normalized_batch.events]
        ),
    }
)
```

For Kafka/Debezium this ultimately reflects the frozen topic/partition/offset range.

For Delta CDF it reflects the bounded commit-version range plus canonical normalized events.

Why include the normalized batch hash as well as checkpoints?

Because provider evidence and normalization must agree. If the same nominal source range is re-read but produces conflicting content, the framework should not quietly treat it as the same target mutation.

---

## 8.3 FULL snapshot -> REPLACE

A destructive/current-state replacement must be anchored to the exact complete candidate.

Recommended scope:

```python
scope_hash = canonical_hash(
    {
        "kind": "full-replace-v1",
        "snapshot_id": snapshot_evidence.snapshot_id,
        "complete_snapshot": True,
        "candidate_hash": candidate_hash,
        "rows": candidate_row_count,
    }
)
```

Never use only:

```text
dataset_id + date
```

Two different full snapshots captured on the same date are not automatically the same mutation.

If the candidate changes, the operation key must change.

---

## 8.4 SNAPSHOT_DIFF

Recommended scope:

```python
scope_hash = canonical_hash(
    {
        "kind": "snapshot-diff-v1",
        "previous_snapshot_id": previous_snapshot_id,
        "current_snapshot_id": current_snapshot_id,
        "diff_hash": diff_hash,
        "complete_previous": True,
        "complete_current": True,
    }
)
```

This makes delete inference part of the mutation identity.

---

## 8.5 APPEND event batch

APPEND already has row/event identity semantics. The target operation key protects the **batch mutation transaction** around those identities.

Recommended scope:

```python
scope_hash = canonical_hash(
    {
        "kind": "append-batch-v1",
        "append_identity_columns": ["topic", "partition", "offset"],
        "batch_lower": {"partition": 0, "offset": 1000},
        "batch_upper": {"partition": 0, "offset": 1099},
        "event_identity_hash": event_identity_hash,
    }
)
```

The row-level append identity and operation-level idempotency solve different problems:

```text
append_identity
  -> prevents duplicate/conflicting logical rows

target operation key
  -> prevents blind re-issuing of an uncertain physical batch mutation
```

Keep both.

---

## 8.6 File incremental

For a file-based candidate, hash the frozen manifest rather than mutable paths alone:

```python
scope_hash = canonical_hash(
    {
        "kind": "file-manifest-v1",
        "manifest_hash": frozen_manifest.manifest_hash,
        "candidate_hash": candidate_hash,
    }
)
```

If `/landing/customer.csv` is overwritten with new bytes/version, it must become a new mutation scope.

---

## 8.7 API cursor incremental

Recommended scope:

```python
scope_hash = canonical_hash(
    {
        "kind": "api-window-v1",
        "frozen_window": api_window.model_dump(mode="json"),
        "cursor_chain_hash": cursor_chain_hash,
        "candidate_hash": candidate_hash,
    }
)
```

A retry must replay the same logical window/cursor evidence, not restart against “whatever the API returns now”.

---

## 8.8 Quarantine REPLAY

REPLAY should identify the exact quarantined evidence being re-applied.

Recommended scope:

```python
scope_hash = canonical_hash(
    {
        "kind": "quarantine-replay-v1",
        "reprocess_request_id": str(request.reprocess_request_id),
        "quarantine_ids": sorted(str(value) for value in quarantine_ids),
        "payload_hash": payload_hash,
        "replay_policy_version": replay_policy_version,
    }
)
```

A different quarantine selection is a different semantic operation.

---

## 8.9 BACKFILL

A backfill operation should freeze the requested source range/partitions plus the resulting candidate identity.

Example:

```python
scope_hash = canonical_hash(
    {
        "kind": "backfill-v1",
        "requested_range": {
            "from": "2026-07-01T00:00:00Z",
            "to": "2026-07-31T23:59:59Z",
        },
        "source_boundary_hash": source_boundary_hash,
        "candidate_hash": candidate_hash,
    }
)
```

Changing July to August is a new operation, even if it is the same dataset and apply strategy.

---

## 8.10 FULL_REBUILD

FULL_REBUILD is intentionally a distinct `RunMode`, so it cannot collide with NORMAL/RETRY.

Recommended scope:

```python
scope_hash = canonical_hash(
    {
        "kind": "full-rebuild-v1",
        "authoritative_candidate_hash": candidate_hash,
        "source_snapshot_or_fence": rebuild_source_evidence,
        "state_replacement_hash": state_replacement_hash,
    }
)
```

The operation identity must cover the candidate **and** the intended authoritative reset scope.

---

# 9. Complete WATERMARK retry example

Assume:

```text
dataset: crm.customer
capture: WATERMARK_LOOKBACK
apply:   SCD1
window:  00:00 -> 01:00
```

Attempt 1:

```text
dataset_run_id = R1
operation_key  = OP42

OP42 PREPARED
OP42 IN_PROGRESS
warehouse MERGE submitted
client timeout
OP42 COMMIT_UNKNOWN
```

The dataset retry creates:

```text
dataset_run_id = R2
operation_key  = OP42   # same frozen mutation
```

Before MERGE is called again:

```text
read OP42 -> COMMIT_UNKNOWN
reconcile target
```

If target proves the MERGE committed:

```text
OP42 COMMITTED
R2 converges without executing MERGE
watermark/state may proceed only after normal reconciliation gates
```

If target proves no commit:

```text
OP42 NOT_COMMITTED
OP42 IN_PROGRESS
execute MERGE again
OP42 COMMITTED
```

If target cannot prove either:

```text
OP42 COMMIT_UNKNOWN
R2 stops
no blind MERGE
no watermark advance
```

---

# 10. Complete CDC -> SCD2 example

Frozen CDC range:

```text
lower = partition p0 offset 1200
upper = partition p0 offset 1300
```

The normalized event hash + checkpoints create one scope.

Attempt 1 opens/closes SCD2 history rows but loses the target commit response.

A blind attempt 2 could close the already-new history version again or insert duplicate versions if the target adapter is not perfectly transaction-idempotent.

The journal prevents that:

```text
attempt 2 sees COMMIT_UNKNOWN
  -> target reconciliation first
  -> COMMITTED => no SCD2 replay
  -> NOT_COMMITTED => replay allowed
  -> UNRESOLVED => stop
```

The CDC downstream checkpoint remains separate:

```text
target operation journal
    = did this physical semantic target mutation commit?

cdc_checkpoint
    = through which source position has downstream semantic processing committed?
```

The CDC checkpoint must not advance merely because the operation row says COMMITTED; required dataset reconciliation/state gates still apply.

---

# 11. Control-plane persistence

Control-plane schema v4 adds environment-local:

```text
target_operation
```

Fields include:

```text
operation_key PK
dataset_id
run_mode
apply_strategy
target_reference
effective_config_hash
mutation_scope_hash
first_dataset_run_id
last_dataset_run_id
status
attempts_started
outcome_reference
last_error_code
last_error_message
version
committed_at
created_at
updated_at
```

This table is **not promotable** between DEV/UAT/PROD.

Why?

It is runtime truth about physical mutations in one environment. A PROD mutation cannot inherit a DEV operation state.

---

## 12. CAS and concurrency

Every lifecycle update includes an expected journal version:

```text
read version 5
attempt transition WHERE version = 5
write version 6
```

A stale writer that still believes version is 5 fails.

This prevents two workers from silently overwriting each other's lifecycle state.

Important limitation:

The current reference implementation proves CAS behavior with SQLAlchemy/SQLite tests. It does **not** certify final production-database isolation, locking or failover behavior. The selected production control-plane repository must re-certify transaction/concurrency semantics.

---

## 13. Operator visibility

`control-plane-status` includes `latest_target_operation` through the typed operator snapshot.

Useful fields for on-call:

```text
operation_key
status
apply_strategy
target_reference
attempts_started
first_dataset_run_id
last_dataset_run_id
outcome_reference
last_error_code
version
committed_at
```

A critical operational state is:

```text
status = COMMIT_UNKNOWN
```

That means:

> Do not manually press retry until target outcome has been reconciled or the recovery workflow explicitly transitions the operation to NOT_COMMITTED.

---

## 14. Relationship to other framework identities

Keep these separate:

```text
pipeline_run_id
  -> one orchestration invocation

dataset_run_id
  -> one dataset attempt

TargetOperation.operation_key
  -> one frozen semantic target mutation across retries

append_identity / CDC event_id
  -> one logical source/target row event identity

watermark / cdc_checkpoint
  -> committed semantic source progress

CaptureReceipt native/provider IDs
  -> physical capture correlation
```

They answer different questions and must not be substituted for each other.

---

## 15. Integration responsibilities for real target adapters

A real Fabric/Lakehouse/Warehouse/SQL adapter must supply three things correctly.

### 15.1 Frozen mutation scope

The adapter/executor must build a stable scope from already-frozen source/candidate evidence.

### 15.2 Precise exception classification

If the target definitively rolled back, it may signal known `NOT_COMMITTED` through a retryable failure.

If commit may have happened, it must signal unknown outcome or allow the framework's conservative generic-exception path to do so.

### 15.3 Reconciliation function

Where possible, the target integration should query durable target-side evidence such as:

- transaction/job ID;
- target version/commit ID;
- target operation marker;
- Delta table commit metadata;
- warehouse request/query history;
- row/version reconciliation tied to the operation scope.

The `outcome_reference` should retain a stable reference to that evidence without storing credentials or huge payloads.

---

## 16. Anti-patterns

### Attempt ID as idempotency key

```text
attempt 1 -> key A
attempt 2 -> key B
```

This makes every retry look like a new mutation and defeats durable idempotency.

### “MERGE is idempotent, so journal is unnecessary”

Not universally true. SCD2, REPLACE, delete logic, external side effects, nondeterministic candidate data and target-specific merge behavior can make re-execution unsafe.

Even when logical MERGE is idempotent, a journal gives explicit unknown-outcome convergence and operator evidence.

### “Any timeout means retry”

A timeout often means **unknown**, not **not committed**.

### Recomputing source window during RETRY

If attempt 2 reads a different upper watermark or new API pages, it is not the same target operation. Freeze input first.

### Advancing source state from the journal alone

`COMMITTED` proves the target operation outcome, not the whole dataset success contract. Required DQ/reconciliation/state gates still apply.

### Promoting journal rows across environments

Never promote runtime operation state.

### Reusing operation key after semantic config change

`effective_config_hash` is part of the key so changed merge/history logic creates a new semantic operation identity.

---

## 17. What is implemented now

Reference/CI-proven:

- stable semantic `operation_key`;
- immutable typed operation contract;
- v4 environment-local journal table;
- optimistic `version` CAS;
- exact reserve idempotency;
- `PREPARED/IN_PROGRESS/COMMIT_UNKNOWN/COMMITTED/NOT_COMMITTED/FAILED` lifecycle;
- persisted `IN_PROGRESS` treated as uncertain;
- COMMITTED convergence without re-execution;
- only NOT_COMMITTED may retry;
- integration with dataset retry/attempt lineage;
- unknown/unclassified mutation exceptions fail closed;
- typed operator visibility through `latest_target_operation`.

Current deterministic proof baseline before final docs audit:

```text
dd148a0c8e329c19809986fa9a32ed7edbe5dbfb
GitHub Actions 33239441546
323 tests passed
Python 3.11 / 3.13 / static / wheel SUCCESS
```

---

## 18. What remains

This slice does **not** yet prove:

1. real Fabric Warehouse/Lakehouse/SQL target transaction IDs or commit reconciliation;
2. real Delta target commit metadata integration;
3. production control-plane database concurrency/isolation/failover;
4. append-only history of every journal state transition — current table stores durable current lifecycle state;
5. automatic target-side operation marker injection for every adapter;
6. real-provider mutation-scope generation in Fabric execution backends;
7. operator mutation/approval UI/API.

These are integration/operability extensions, not reasons to remove the portable stable-operation contract.

---

## 19. New target adapter checklist

Before certifying a new physical target adapter, answer:

```text
[ ] What exact frozen input defines mutation_scope_hash?
[ ] Can retry reproduce that exact input?
[ ] When can the adapter prove NOT_COMMITTED?
[ ] Which failures are COMMIT_UNKNOWN?
[ ] How does reconciliation prove COMMITTED?
[ ] What stable outcome_reference is retained?
[ ] Does the target expose transaction/job/version metadata?
[ ] Does the mutation remain deterministic under retry?
[ ] Are CAS/journal writes durable in the production control-plane store?
[ ] Does source progress advance only after target + reconciliation gates?
```

If these questions cannot be answered, the adapter is not yet certified for automatic target retry after an uncertain mutation.
