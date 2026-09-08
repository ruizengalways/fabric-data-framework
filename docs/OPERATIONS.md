# Operations and recovery

This is the canonical runbook for **transient runtime operations and recovery** in normal business Pipelines: failure isolation, RETRY, REPLAY, BACKFILL, unknown/ambiguous commit, dependency recovery, and operational incident handling.

Data-correctness reconstruction is a separate lifecycle. For detailed `FULL_REBUILD` scopes, contaminated dependency impact, v1/v2 target versions, UAT, cutover, rollback, and old-version retention, use [`REPAIR_AND_REBUILD.md`](REPAIR_AND_REBUILD.md). Framework release certification is also separate; see [`TESTING_AND_CERTIFICATION.md`](TESTING_AND_CERTIFICATION.md).

## 1. Default parent Pipeline behavior

The normal failure policy is fail-at-end with dataset fault isolation:

```text
one dataset FAIL
-> persist dataset error
-> independent siblings continue
-> downstream dependents BLOCKED
-> all runnable work reaches terminal state
-> parent Pipeline FAILED
```

This avoids wasting the execution window while still refusing to report an incomplete batch as success.

Only use a different criticality policy when the business explicitly accepts partial completion.

## 2. Execution-group policy

Shared operational defaults belong in source-controlled execution-group policy rather than being copied into dozens of Fabric activities.

Typical policy includes:

```text
failure policy
max concurrency
DQ/quarantine defaults
per-dataset overrides
dependency graph
```

Policy content must participate in project/config identity. Runtime override is temporary operational control, not long-term configuration management.

## 3. Data quality and quarantine

Recommended production pattern:

```text
invalid rows
-> durable governed quarantine
-> compare row/fraction thresholds
-> threshold exceeded => dataset FAIL
-> no target/state/watermark commit
-> independent siblings may continue
```

Keep summary/lineage metadata in the Control Plane and detailed sensitive rows in governed data-plane storage.

```text
Fabric SQL Database
  quarantine batch metadata / references

Lakehouse / governed data store
  original rows
  Bronze lineage
  rule code/message
```

Do not disable DQ merely to make a Pipeline green.

## 4. Where to investigate a failure

Start with `pipeline_run`, then drill into `dataset_run` and related typed records.

Useful identities/state include:

```text
pipeline_run_id
status / error_code / error_message

dataset_run_id
dataset_id
attempt
rows_read / accepted / quarantined / inserted / updated / deleted
retryable

step_run
reconciliation_result
quarantine_batch
capture_receipt
dataset_attempt_lineage
target_operation / target_operation_event
```

Fabric UI status alone is not enough. A provider `Completed` result without the expected durable framework outcome is not semantic success.

## 5. Operational decision table

| Situation | Automatic retry? | Correct response |
|---|---:|---|
| Explicit transient provider failure with `retryable=true` | bounded only | `RETRY` with backoff and attempt lineage |
| `BLOCKED_DEPENDENCY` | no | recover upstream first, then only affected dependency chain |
| DQ failure / threshold exceeded | no | fix source/rule/config, then audited retry or replay |
| Reconciliation failure | no | investigate source/target/mapping before reprocess |
| Unknown/ambiguous target commit | never blind retry | reconcile target/marker first |
| Config/binding/schema contract error | no | fix in Git, validate/deploy, then rerun |
| Cancelled/unknown failure | no by default | prove partial-effect state first |
| Bounded source gap | controlled | `BACKFILL` exact range |
| Retained immutable payload needs reprocessing | controlled | `REPLAY` |
| Trusted Bronze is correct but target logic/data is wrong | controlled | `FULL_REBUILD + TARGET_ONLY`; continue in `REPAIR_AND_REBUILD.md` |
| Bronze/capture facts are wrong but progress kind is still valid | controlled | `FULL_REBUILD + CAPTURE_AND_TARGET`; continue in `REPAIR_AND_REBUILD.md` |
| Capture semantics/progress model itself is untrustworthy | controlled | `FULL_REBUILD + AUTHORITATIVE_RESET`; continue in `REPAIR_AND_REBUILD.md` |

Use the smallest safe operation. A failed nightly Pipeline is not by itself a reason to rebuild data.

## 6. RETRY

Retry is for the same logical work when retry safety has already been established.

Expected behavior:

```text
explicit retryable failure
-> bounded attempts
-> exponential/backoff policy
-> new attempt identity
-> immutable attempt lineage
-> idempotent/protected target mutation
```

Do not stack an unbounded Fabric-native retry around a separate framework retry loop.

## 7. Unknown or ambiguous commit

The dangerous case is:

```text
server may have committed
client timed out / connection dropped
```

The framework uses target-operation identity, journal state, and target-side proof to classify:

```text
COMMITTED
  -> converge to success; no second mutation

NOT_COMMITTED
  -> bounded retry may be safe

UNRESOLVED
  -> stop; operator/provider evidence required
```

Stop condition:

```text
UNRESOLVED -> no automatic recovery
```

A blind retry after ambiguous commit can duplicate APPEND rows or corrupt merge/history semantics.

## 8. REPLAY

Use replay when retained immutable payload can be reprocessed after fixing DQ/mapping/rule behavior.

```text
retain original quarantine/replay evidence
-> fix source/rule/config in Git
-> deploy validated change
-> create audited REPLAY request
-> read exact retained payload
-> transform/DQ/apply/reconcile again
-> record replay correlation
```

Replay success must not erase the original evidence.

`REPLAY` is not the generic name for rebuilding retained Bronze history. When authoritative target or capture data must be reconstructed, use `FULL_REBUILD` and follow [`REPAIR_AND_REBUILD.md`](REPAIR_AND_REBUILD.md).

## 9. BACKFILL

Use backfill for a bounded known gap such as a missed watermark interval or partition.

```text
run_mode = BACKFILL
lower    = explicit boundary
upper    = explicit boundary
```

Backfill still follows normal capture fidelity, DQ, apply, reconciliation, idempotency, and state-commit contracts.

Do not use a full rebuild to repair a small bounded gap.

## 10. FULL_REBUILD: decision and redirect

`FULL_REBUILD` is for data-correctness reconstruction, not ordinary transient recovery. The framework has exactly three scopes:

```text
TARGET_ONLY
CAPTURE_AND_TARGET
AUTHORITATIVE_RESET
```

At the operational triage layer, select the first untrustworthy point and stop there:

```text
target logic/data only        -> TARGET_ONLY
capture/Bronze facts          -> CAPTURE_AND_TARGET
capture semantics/progress    -> AUTHORITATIVE_RESET
```

Do **not** execute a rebuild from this summary alone. The canonical procedure, scope/state gates, dependency-aware impact planning, v1/v2 strategy, UAT/cutover, rollback, and manual cleanup boundary live in [`REPAIR_AND_REBUILD.md`](REPAIR_AND_REBUILD.md).

`FULL_REBUILD` is not purge. Permanent hard deletion remains an explicit manual operator/governance action.

## 11. Dependency recovery

Example:

```text
A master     FAIL
B dimension  BLOCKED (depends on A)
C orders     PASS (independent)
parent       FAILED
```

Operational recovery order:

```text
recover A
-> prove A semantic success/state
-> run B dependency chain
```

Do not blindly rerun independent successful datasets.

If the upstream problem is **data correctness** rather than a transient failure, switch to the dependency-aware repair process in [`REPAIR_AND_REBUILD.md`](REPAIR_AND_REBUILD.md); contaminated descendants and rebuild waves are a repair concern, not ordinary retry scheduling.

## 12. Operator incident flow

```text
1. capture pipeline_run_id
2. identify FAILED/BLOCKED dataset runs
3. inspect first failing step + provider correlation
4. classify transient / DQ / reconciliation / dependency / unknown commit / config / data correctness
5. prove retry safety before RETRY
6. fix the actual cause
7. create audited RETRY / REPLAY / BACKFILL request when appropriate
8. if data correctness is wrong, hand off to REPAIR_AND_REBUILD.md
9. verify target + reconciliation + state/checkpoint
10. verify affected downstream operational dependencies
11. remove/commit any temporary runtime override
```

## 13. Alerts

At minimum alert on:

```text
parent Pipeline FAILED
retry exhausted
unknown commit unresolved
DQ quarantine threshold exceeded
reconciliation failed
BLOCKED dependency count > 0
SLA breach
repeated failures for the same dataset
```

Also trend quarantine rate by dataset/rule over time; a rising rate may matter before a single batch crosses a hard threshold.

## 14. Keep Fabric Pipelines thin

Preferred shape:

```text
select dataset work
-> bounded parallel dispatch / reusable child
-> pass exact framework run identity
-> framework persists semantic outcome
-> aggregate terminal outcomes
-> final parent status reflects aggregate result
```

Do not duplicate watermark, retry, DQ, SCD, and recovery logic across dozens of Notebook/Pipeline implementations.

For the exact reusable Pipeline child correlation contract, see [`reference/PIPELINE_CHILD_CONTRACT.md`](reference/PIPELINE_CHILD_CONTRACT.md).
