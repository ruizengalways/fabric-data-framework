# Operations and recovery

This is the canonical runbook for **transient runtime operations and recovery** in normal business Pipelines: failure isolation, RETRY, REPLAY, BACKFILL, unknown/ambiguous commit, dependency recovery, quarantine review/remediation, and operational incident handling.

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

## 3. Data quality, quarantine, and human remediation

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
  append-only review transitions
  manual-correction reference + exact payload SHA256

Lakehouse / governed data store
  immutable original quarantine rows
  optional corrected payload written as a new object/version
  Bronze lineage
  rule code/message
```

### 3.1 Original evidence is not an editable staging table

Do not manually `UPDATE` quarantine payloads, delete reviewed evidence, or `INSERT` corrected values back into Bronze. Bronze remains the source-delivered fact and the original quarantine payload remains immutable evidence.

A quarantine case starts logically as `OPEN`. Human review uses explicit optimistic transitions:

```text
OPEN
  -> UNDER_REVIEW
      -> RESOLVED
      -> REJECTED
      -> WAIVED
```

`REPLAYED` is **not** an operator-set review state. It is derived only after the framework has proven replay target commit plus required reconciliation and written `replayed_by_dataset_run_id`.

Every review transition records:

```text
quarantine_id
from_status -> to_status
actor
reason
resolution when terminal
ticket/reference when available
correction_id when MANUAL_CORRECTION
```

Only one transition may claim a given `quarantine_id + from_status`. A stale or competing reviewer fails closed instead of silently overwriting another decision.

### 3.2 Preferred resolution order

Use the least invasive truthful remediation:

```text
1. source corrected
   -> normal ingest preferred

2. DQ rule / mapping was wrong
   -> fix in Git
   -> validate/deploy
   -> REPLAY retained immutable payload when needed

3. exceptional manual data correction is required
   -> begin governed review
   -> write corrected rows to a new governed correction object/version
   -> retain exact correction reference + SHA256 + actor + reason/ticket
   -> resolve case as MANUAL_CORRECTION
   -> REPLAY using that exact approved correction provenance
```

Manual correction never changes the original source reference. The correction reference must be distinct and its exact payload hash must be approved in the Control Plane before replay.

Typical terminal resolution classes are:

```text
RESOLVED + SOURCE_CORRECTED
RESOLVED + RULE_OR_MAPPING_FIXED
RESOLVED + MANUAL_CORRECTION
WAIVED   + ACCEPTED_EXCEPTION
REJECTED + REJECTED_AS_INVALID
```

Physical deletion is a retention/governance operation, not a review action. A resolved/replayed quarantine remains available until the configured retention policy explicitly expires it.

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
quarantine_review_event
quarantine_manual_correction
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
| Quarantined row requires human correction | no | governed review + immutable correction payload/reference/hash + audited `REPLAY` |
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

For a `DELTA_PROJECTION` dataset, inspect `dataset_lease` before retrying. The claim is
durable mutual exclusion around target mutation plus checkpoint commit; `expires_at` is
only a review deadline and never authorizes automatic takeover. If the claim remains
after a process failure, stop and prove the old executor and any provider-side work
cannot resume. Use the governed `recover_abandoned_dataset_lease(...)` operation only
after the review deadline, passing the exact lease owner/run/version plus operator, reason
and durable proof reference. Recovery appends immutable `dataset_lease_recovery_event`
evidence and removes only the exact abandoned claim in the same Control Plane
transaction. Never delete the row manually or treat timeout alone as proof of abandonment.

Current-projection physical mode changes are similarly explicit. Use
`FabricSparkProjectionTransitionCoordinator` rather than changing the source-controlled
mode and manually deleting checkpoints. The coordinator preserves the stable consumer
name, rebuilds from authoritative history, records transition evidence and performs an
exact checkpoint reset only when required.

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

Use replay when retained immutable payload can be reprocessed after fixing DQ/mapping/rule behavior, or when a governed manual correction has been approved.

Rule/mapping/source-compatible replay:

```text
retain original quarantine/replay evidence
-> fix source/rule/config in Git when applicable
-> deploy validated change
-> create audited REPLAY request
-> read exact retained original payload
-> transform/DQ/apply/reconcile again
-> record replay correlation
```

Manual-correction replay adds a stricter provenance gate:

```text
original quarantine source_reference stays immutable
+
approved correction_id
approved correction_reference
approved correction_payload_sha256
-> provider supplies corrected rows carrying that exact trio
-> framework verifies case is RESOLVED + MANUAL_CORRECTION
-> framework verifies correction identity/reference/hash
-> target/apply/reconciliation
-> only then record replay correlation
```

A resolved manual-correction case cannot replay the uncorrected original payload by omission. Exact correction provenance is mandatory.

Replay success must not erase the original evidence or correction evidence. `REPLAYED` is derived from the semantic replay marker; it is not manually written by an operator.

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
7. for quarantine, record governed review/resolution/correction evidence when needed
8. create audited RETRY / REPLAY / BACKFILL request when appropriate
9. if data correctness is wrong, hand off to REPAIR_AND_REBUILD.md
10. verify target + reconciliation + state/checkpoint
11. verify affected downstream operational dependencies
12. remove/commit any temporary runtime override
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

Also trend quarantine rate by dataset/rule over time; a rising rate may matter before a single batch crosses a hard threshold. Operational dashboards should also expose aged `OPEN`/`UNDER_REVIEW` quarantine cases so manual exceptions do not become a hidden backlog.

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

Do not duplicate watermark, retry, DQ, SCD, quarantine governance, and recovery logic across dozens of Notebook/Pipeline implementations.

For the exact reusable Pipeline child correlation contract, see [`reference/PIPELINE_CHILD_CONTRACT.md`](reference/PIPELINE_CHILD_CONTRACT.md).

## Runtime safety and retained evidence

Operational recovery must preserve the same fail-closed boundaries as normal execution:

- Watermark commits are monotonic and use expected-version CAS. A stale concurrent writer fails instead of overwriting a newer checkpoint.
- Ordinary pipeline/backend exceptions are terminalized as `FAILED` with `completed_at` whenever the Control Plane remains writable. If terminal audit persistence itself fails, both the original execution error and the finalization error are surfaced; a stored `RUNNING` row cannot be falsely claimed as finalized.
- Unknown target-commit outcomes are never retried blindly. Resolver failure or an invalid resolver value records `UNKNOWN_COMMIT_RESOLUTION_FAILED`; only explicit `NOT_COMMITTED` may enter the retry path.
- Provider error/failure payloads are recursively redacted and bounded before entering audit models or repositories. Secrets such as passwords, bearer tokens, authorization values, connection strings, and nested token/secret fields must not be retained.
- Detailed quarantine replay payloads use typed schema v2, validate exact dataset/quarantine identity and a content SHA256, and publish with create-if-absent semantics. Unsupported business value types fail closed instead of being stringified.

The filesystem atomicity tests are local/POSIX evidence only. OneLake/Lakehouse mount create-if-absent semantics remain part of real Fabric certification and must not be inferred from local tests.
