# Capture Pattern Catalog and New-Source Onboarding Playbook

Status: Canonical onboarding guide for mainstream Data Engineering source/capture patterns  
Last updated: 2026-08-29

## 1. Why this document exists

When a new source arrives, the first question is **not** “SCD1 or SCD2?” and it is not “Copy Job or Notebook?”.

The first question is:

> **What information does the source actually give us, with what ordering, delete visibility and replay identity?**

That answer puts a hard upper bound on what Silver history can truthfully represent.

The framework separates five independent decisions:

```text
source/capture pattern
    -> what facts the source exposes

change fidelity
    -> current state / net change / full row change / business event

delete visibility
    -> none / inferred / tombstone / explicit event / source-defined

Bronze storage
    -> overwrite / merge current state / append observations or events

Silver apply
    -> APPEND / REPLACE / UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF
```

Physical execution is another independent decision:

```text
Copy Job / Copy Activity / Dataflow Gen2 / Spark / Mirroring /
External CDC / SQL / controlled extension
```

A physical engine does not improve source fidelity. If the source only provides net changes, no Spark code can reconstruct intermediate changes that never arrived.

---

## 2. Golden rule: capture fidelity caps history fidelity

```text
source only gives current state
    -> framework can know current state
    -> recurring complete snapshots can infer snapshot-to-snapshot changes
    -> cannot know changes between snapshots

source gives watermark rows
    -> framework can know rows that crossed the watermark
    -> cannot infer hard deletes from absence
    -> SCD2 means "history of captured observations", not guaranteed full source history

source gives native net changes
    -> framework knows final change per key in the capture window
    -> intermediate changes inside that window are already lost

source gives every ordered I/U/D event
    -> framework can preserve full captured row-change history
    -> SCD2 can be full event-grain history, subject to ordering/retention/bootstrap correctness

source is a business event stream
    -> events are facts in their own right
    -> Bronze should normally be immutable APPEND
    -> relational delete semantics exist only if the event contract defines them
```

The framework uses `HistoryFidelity` to keep this claim explicit:

```text
NONE
OBSERVED_CHANGES
BATCH_GRAIN
FULL_EVENT
SNAPSHOT_GRAIN
SOURCE_DEFINED
```

---

## 3. Mainstream pattern matrix

| # | Capture pattern | What you actually receive | Delete visibility | Change fidelity | Bronze default | Bronze preserves | Retry/lookback dedupe identity | Silver SCD1 | Silver SCD2 truth |
|---:|---|---|---|---|---|---|---|---|---|
| 1 | `FULL_SNAPSHOT` | Whole current table | Inferred only by comparing complete snapshots | Current state | `OVERWRITE` | Current snapshot | `snapshot_id` | Yes | Snapshot-grain only; prefer `SNAPSHOT_DIFF` when history/delete inference matters |
| 2 | `WATERMARK_INCREMENTAL` | Rows where source ordering/watermark advanced | No hard delete | Current/net state observation | `MERGE` | Current state | PK + watermark + tie-breaker | Yes | Observed changes only |
| 3 | `WATERMARK_LOOKBACK` | Recent window intentionally re-read | No hard delete | Current/net state observation | `MERGE` | Current state | PK + timestamp/version | Yes | Observed changes only |
| 4 | `WATERMARK_TOMBSTONE` | Changed rows plus explicit soft-delete/tombstone | Tombstone | Net/current | `MERGE` or bounded `APPEND` | Current state or observations | PK + timestamp/version + delete marker | Yes | Observed changes, including captured deletes |
| 5 | `CDC_NET_CURRENT` | Final native CDC change/state per PK per capture window | Explicit | **Net change** | `MERGE` | Current state | CDC position + PK | Yes | Batch-grain; intermediate changes are gone |
| 6 | `CDC_NET_OBSERVATION` | Same net changes, retained per capture batch | Explicit | **Net change** | `APPEND` | Batch observations | batch/capture id + PK | Yes | Batch-grain, not full event history |
| 7 | `CDC_FULL` | Every ordered I/U/D row change | Explicit | **Full change** | `APPEND` | Change events | source position + event id | Yes | Full captured event history |
| 8 | `TRANSACTION_LOG_CDC` | Every row change from LSN/SCN/binlog/log position | Explicit | Usually full change | `APPEND` | Change events | log position + row sequence/event id | Yes | Full captured event history |
| 9 | `DEBEZIUM_KAFKA` | Ordered Debezium events consumed from Kafka | Explicit | Full change | `APPEND` | Change events | topic + partition + offset | Yes | Full captured event history |
| 10 | `DELTA_CDF` | Delta row changes with change type/commit version | Explicit | Full change | `APPEND` | Delta change events | commit version + row event identity | Yes | Full captured event history |
| 11 | `EVENT_SOURCE` | Domain/business events | Source-defined | Full event | `APPEND` | Immutable business events | event id or partition/offset | Usually | Full event history; SCD2 is a projection, not the source truth |
| 12 | `SNAPSHOT_DIFF` | Snapshot N compared with N-1 | Inferred from complete snapshots | Net change | `APPEND` diff or `MERGE` current | Diff events or current | snapshot id + PK | Yes | Snapshot-grain; cannot see multiple changes between snapshots |
| 13 | `API_CURSOR_INCREMENTAL` | API pages/changes inside a frozen cursor/window | API-defined | API-defined | Usually `MERGE`; `APPEND` if events | Current or events | frozen window + cursor chain + PK/event id | Yes | Depends on API contract |
| 14 | `FILE_INCREMENTAL` | New/changed immutable or versioned files | File contract-defined | File-content-defined | `APPEND` raw or `MERGE` current | Raw files/events/current | path + version token/checksum | Yes | Depends on file semantics |

This matrix is encoded in `fabric_data_framework.capture.patterns`, so it can be validated in domain CI rather than existing only as prose.

---

## 4. New source decision tree

Use this order. Do not start with a preferred tool.

### Step 1 — Is the source an event stream or a table/state source?

If the records are immutable business events such as `OrderPlaced`, `PaymentCaptured`, `ShipmentDispatched`:

```text
EVENT_SOURCE
Bronze: APPEND immutable events
identity: event_id or partition/offset
```

Do not convert an event stream into a fake relational CDC table before Bronze unless there is a very specific reason.

If it is a table/current-state object, continue.

### Step 2 — Can the source provide every row-level change in deterministic order?

If yes:

- transaction-log CDC -> `TRANSACTION_LOG_CDC`;
- Debezium on Kafka -> `DEBEZIUM_KAFKA`;
- Delta Change Data Feed -> `DELTA_CDF`;
- generic full I/U/D feed -> `CDC_FULL`.

Default:

```text
Bronze = APPEND change events
Silver current = UPSERT/SCD1
Silver history = SCD2
```

This is the strongest common capture family for complete row-change history.

### Step 3 — Does native CDC expose only net/final changes per window?

If yes, choose one of two Bronze goals:

```text
need only current Bronze
    -> CDC_NET_CURRENT
    -> Bronze MERGE

need to retain what every ingestion batch observed
    -> CDC_NET_OBSERVATION
    -> Bronze APPEND observations
```

Neither is full event history. If a row changed A -> B -> C inside one native net-change window and the source only returns C, the framework cannot recover B.

### Step 4 — Is there a reliable updated/version watermark?

If yes:

```text
strict monotonic ordering + tie-breaker
    -> WATERMARK_INCREMENTAL

late commits / clock skew / source transaction delay possible
    -> WATERMARK_LOOKBACK
```

Prefer lookback when a small bounded re-read is cheaper than missing data.

If the source exposes a soft-delete flag or tombstone row:

```text
WATERMARK_TOMBSTONE
```

If not, hard deletes are invisible.

### Step 5 — Can you obtain complete authoritative snapshots?

If current state is all you need:

```text
FULL_SNAPSHOT
FULL -> REPLACE
```

If you need deletes or snapshot-grain SCD history:

```text
SNAPSHOT_DIFF
SNAPSHOT -> SNAPSHOT_DIFF
```

Do not claim event-grain history from daily snapshots.

### Step 6 — Is the source an API?

If the API gives a stable cursor or “changes since X” contract:

```text
API_CURSOR_INCREMENTAL
```

Before page 1, freeze:

- lower bound;
- upper bound where supported;
- filter/predicate identity;
- starting cursor.

Then prove:

- cursor continuity;
- no cycles;
- page count/record count limits;
- terminal completion;
- exact row accounting.

Whether the API supports deletes/full history is a separate source-contract question.

### Step 7 — Is the source delivered through files?

Use:

```text
FILE_INCREMENTAL
```

Freeze a manifest containing stable file version evidence before parsing. Do not identify a file only by a mutable path.

Then classify the **content**:

```text
one file = immutable transaction/event records
    -> Bronze APPEND

one file = current-state extract/partition replacement
    -> Bronze MERGE or snapshot logic

one delivery = authoritative full snapshot
    -> FULL_SNAPSHOT / SNAPSHOT_DIFF semantics
```

“File source” does not tell you the data semantics by itself.

---

## 5. Questions to ask a source owner before onboarding

Copy this checklist into a source onboarding ticket.

### Source facts

1. Is the object current state, a snapshot, change feed, transaction log or business event stream?
2. Can the source return a complete authoritative snapshot?
3. Can rows be physically hard-deleted?
4. If delete happens, how is it exposed: not at all, soft-delete flag, tombstone, explicit CDC delete, snapshot absence?
5. Is there a reliable primary/business key?
6. Can the key itself change?
7. What is the ordering coordinate: timestamp, version, sequence, LSN, SCN, binlog position, commit version, cursor, Kafka offset?
8. Can two rows share that coordinate? If yes, what is the deterministic tie-breaker?
9. Can events/updates arrive late or out of order?
10. Can the source provide before image, after image, both or only current state?

### Recovery facts

11. What identity makes a source record/event replay-safe?
12. What is the retention period for CDC/log/CDF/API cursors/files?
13. Can the framework safely re-read an overlap window?
14. Can a cursor/offset expire?
15. Is a historical bootstrap snapshot available?
16. Can CDC be retained/buffered while the bootstrap snapshot runs?

### Schema facts

17. How are columns added/removed/renamed?
18. Can source types widen/narrow?
19. Does schema change invalidate historical CDC/CDF reads?

### Operational facts

20. Expected row count/change rate/file count/page count?
21. Source concurrency/rate limits?
22. Required latency/SLA?
23. Gateway/private-network requirements?
24. Which Fabric/native connector is actually supported in the target tenant?

If the source owner cannot answer ordering/delete/recovery questions, treat the pattern conservatively. Do not infer stronger semantics because a tool has a button named “incremental”.

---

## 6. Framework usage: executable pattern assessment

The catalog is intentionally separate from `CaptureStrategy`.

Example domain CI check:

```python
from fabric_data_framework.capture import (
    CapturePattern,
    assess_dataset_capture_pattern,
)

assessment = assess_dataset_capture_pattern(
    dataset_config,
    CapturePattern.WATERMARK_LOOKBACK,
)

for warning in assessment.warnings:
    print(warning)
```

The validator checks the coarse semantic mapping and pattern-specific guardrails. Examples:

- `WATERMARK_LOOKBACK` with zero overlap -> fail;
- `DEBEZIUM_KAFKA` mapped to `FULL` -> fail;
- full CDC with Bronze `MERGE` -> fail because event fidelity would be discarded;
- SCD2 on net CDC -> allowed but explicitly classified `BATCH_GRAIN`;
- SCD2 on watermark -> allowed but explicitly classified `OBSERVED_CHANGES`.

The catalog does **not** prove that a provider transport is configured or reachable. Provider/runtime certification remains a separate evidence layer.

---

# 7. Concrete patterns and examples

## 7.1 Full snapshot — current-state reference table

### Example

An HR system exports every employee every night:

```text
employee_id,name,department,status,...
```

The file/table is complete and authoritative for that run. It does not contain change events.

### Use when

- source can reliably provide the whole object;
- size/cost is acceptable;
- current state is primary requirement.

### Bronze

```text
write mode: OVERWRITE
content: current complete snapshot
required evidence: snapshot_id + completeness
```

### Silver SCD1/current state

Use:

```yaml
load:
  capture_strategy: FULL
  apply_strategy: REPLACE
```

For a complete authoritative snapshot, `REPLACE` is often clearer than inventing row-level merge logic.

### Silver SCD2

If you need history from recurring snapshots, classify the ingestion as `SNAPSHOT_DIFF` and compare snapshot N to N-1. The maximum fidelity is the snapshot cadence.

If snapshots run daily:

```text
09:00 A
12:00 B
15:00 C
next snapshot 23:00 C
```

You can observe `A -> C` across snapshots. You cannot prove that B ever existed.

---

## 7.2 Incremental watermark — ordinary source table

### Example

ERP customer table:

```text
customer_id PK
name
status
updated_at
source_version
```

Source query:

```sql
WHERE (updated_at, customer_id) > (:last_updated_at, :last_customer_id)
  AND (updated_at, customer_id) <= (:frozen_upper_updated_at, :upper_customer_id)
ORDER BY updated_at, customer_id
```

### Recommended metadata

```yaml
load:
  capture_strategy: WATERMARK
  apply_strategy: SCD1
  business_key: [customer_id]
  merge_key: [customer_id]
  watermark:
    column: updated_at
    tie_breaker: [customer_id]
  event_time_column: updated_at
  version_column: source_version

execution:
  engine: FABRIC_COPY_ACTIVITY
  progress_owner: FRAMEWORK
  apply_engine: SPARK
```

### Bronze

```text
MERGE current state by customer_id
```

Retry identity:

```text
customer_id + updated_at + source_version
```

### Delete truth

If the source physically deletes customer `42`, no future row crosses the watermark. The framework cannot see that delete.

So:

```text
delete_policy=IGNORE
```

is truthful unless a separate delete feed exists.

### SCD2 truth

SCD2 is valid as **observed change history**, but it is not equivalent to full CDC history.

---

## 7.3 Watermark + lookback — safer timestamp ingestion

### Example

Source updates sometimes commit late relative to application timestamps. Use a 10-minute overlap:

```yaml
load:
  capture_strategy: WATERMARK
  apply_strategy: UPSERT
  merge_key: [order_id]
  watermark:
    column: modified_at
    tie_breaker: [order_id]
    overlap_window_seconds: 600
  event_time_column: modified_at
  version_column: row_version
```

Each run intentionally re-reads recent rows.

The framework requirement is not “never duplicate”. It is:

> duplicate reads are expected; target application must be idempotent and ordered.

Use the latest `(modified_at, row_version, order_id)` for each key and ignore exact/stale replays.

Do not advance state until target commit + required reconciliation succeed.

---

## 7.4 Watermark + tombstone / soft delete

### Example

CRM table never physically removes a contact. It sets:

```text
is_deleted = true
updated_at = now()
row_version += 1
```

This is materially stronger than ordinary watermark ingestion because deletes are observable.

Recommended model:

```yaml
load:
  capture_strategy: WATERMARK
  apply_strategy: SCD1
  merge_key: [contact_id]
  watermark:
    column: updated_at
    tie_breaker: [contact_id]
    overlap_window_seconds: 300
  event_time_column: updated_at
  version_column: row_version
  delete_policy: APPLY
```

The parser/transform must normalize the soft-delete flag into the framework's explicit delete semantic. Do not simply drop tombstone rows during transformation.

---

## 7.5 Native CDC — net changes into current Bronze

### Example

A native capture API returns at most one final change per customer per 15-minute window.

Within the source:

```text
10:01 A -> B
10:04 B -> C
10:10 C -> D
```

The 10:00-10:15 net feed returns only D.

Use:

```text
pattern: CDC_NET_CURRENT
Bronze: MERGE
Silver: UPSERT/SCD1
```

SCD2 can create a version for D, but it must be labelled `BATCH_GRAIN`. B and C never entered the framework.

This is not a bug. It is a source-fidelity boundary.

---

## 7.6 Native CDC — net changes retained as observations

Same source as above, but operational/audit requirements want to retain what each batch observed.

Use:

```text
pattern: CDC_NET_OBSERVATION
Bronze: APPEND
identity: capture_batch_id + primary_key
```

Example Bronze:

```text
capture_batch_id | customer_id | observed_state | source_position
b001             | 42          | D              | ...
b002             | 42          | E              | ...
```

This is useful history of **observations**. It is not every source mutation.

---

## 7.7 Native CDC — all/full changes

### Example

Source provides:

```text
LSN 100 row 1 UPDATE customer 42 A -> B
LSN 100 row 2 UPDATE customer 42 B -> C
LSN 101 row 1 DELETE customer 42
```

Bronze should preserve the events:

```text
APPEND
```

Do not MERGE them into a current-state Bronze table if full change history is a requirement. You can derive current state later.

Canonical normalization needs a unique row event order, not only an LSN if several row changes can share it.

Silver:

```text
UPSERT/SCD1 -> current projection
SCD2        -> history projection
```

---

## 7.8 Transaction-log CDC

Transaction-log CDC is a provider family of `CDC_FULL` when every relevant row mutation is retained.

Examples of provider coordinates:

```text
SQL Server LSN + sequence
Oracle SCN + row sequence
MySQL binlog file generation + position + row number
```

The provider adapter must normalize these into deterministic integer tuples. The semantic core must not compare arbitrary opaque strings and guess ordering.

Retention matters. If the next unapplied log position has already expired, recovery must fail with a gap rather than silently jump forward.

---

## 7.9 Debezium / Kafka CDC

Built-in reference profile:

```yaml
load:
  capture_strategy: CDC
  apply_strategy: SCD2
  business_key: [customer_id]
  merge_key: [customer_id]

execution:
  engine: EXTERNAL_CDC
  progress_owner: EXTERNAL
  capability_profile: debezium_kafka_v1
  apply_engine: SPARK
```

Canonical order:

```text
topic + partition + offset
```

Bronze:

```text
APPEND canonical/raw change events
```

Framework rules already include:

- Debezium `c/u/d` normalization;
- tombstone is provider cleanup, not a second business delete;
- snapshot `op=r` rejected by default unless intentionally authorized;
- Kafka record key required;
- retention-aware resume starts from framework-applied CDC progress, not a consumer-group cursor that may have advanced too far.

Current evidence level is adapter/reference only. Real broker authentication, polling and consumer offset commit are still integration work.

---

## 7.10 Delta Change Data Feed

Delta CDF is a first-class mainstream change source.

Current Delta CDF exposes change metadata such as:

```text
_change_type
  insert
  delete
  update_preimage
  update_postimage

_commit_version
_commit_timestamp
```

Recommended Bronze:

```text
APPEND CDF changes
```

Recommended canonical identity/order:

```text
commit_version + row event identity/sequence
```

Do not use commit timestamp alone as the canonical order if commit version exists.

For UPDATE:

```text
update_preimage  -> before image
update_postimage -> after image
```

Provider normalization should produce one canonical UPDATE event where deterministic pairing is possible, or otherwise preserve enough event identity/order to avoid ambiguity.

Silver:

```text
UPSERT/SCD1 -> current projection
SCD2        -> full captured CDF history
```

Recovery must respect CDF retention. If required historical CDF versions no longer exist, do not silently continue from a newer version.

Official references used for this design:

- Delta Lake Change Data Feed: https://docs.delta.io/delta-change-data-feed/
- Microsoft Fabric Change Data Feed: https://learn.microsoft.com/en-us/fabric/data-engineering/delta-lake-change-data-feed

The framework catalog exists now; a dedicated Delta CDF provider adapter/transport is a separate implementation item.

---

## 7.11 Business event source

### Example

Kafka/Eventstream topic:

```json
{"event_id":"e1","type":"OrderPlaced","order_id":1001,"event_time":"..."}
{"event_id":"e2","type":"PaymentCaptured","order_id":1001,"event_time":"..."}
{"event_id":"e3","type":"OrderCancelled","order_id":1001,"event_time":"..."}
```

Bronze source of truth:

```text
APPEND immutable events
```

Retry identity:

```text
event_id
```

or provider partition/offset if the event id is not trustworthy.

Silver can derive:

```text
current order state -> SCD1/UPSERT projection
state history       -> SCD2 projection
facts               -> event/fact models
```

Do not call `OrderCancelled` a relational DELETE unless the business projection explicitly defines that meaning.

---

## 7.12 Snapshot diff

### Example

A vendor provides one complete account export every day with no CDC.

Snapshots:

```text
D1: 1=A, 2=B, 3=C
D2: 1=A, 2=B2, 4=D
```

Framework diff:

```text
1 unchanged
2 updated B -> B2
3 deleted
4 inserted
```

Required safety:

- both snapshots are complete/authoritative;
- merge key is non-null/unique;
- quarantine does not silently convert rejected source rows into deletes;
- delete-all is blocked by default;
- suspicious delete fraction may be capped.

Silver SCD2 is legitimate, but its fidelity is daily snapshot grain.

---

## 7.13 API cursor / pagination incremental

### Example

API contract:

```text
GET /customers/changes?cursor=<token>&until=<frozen_upper>
response: rows + next_cursor
```

Before first request:

```python
window = freeze_api_window(
    window_id="customer-2026-08-29T00:00Z",
    lower_bound=previous_upper,
    upper_bound=frozen_upper,
    predicate={"status": ["ACTIVE", "DELETED"]},
)
```

Then validate page evidence:

```text
page 1 request_cursor=None -> next=c1
page 2 request_cursor=c1   -> next=c2
page 3 request_cursor=c2   -> next=None
```

Reject:

- changed retry window;
- cursor cycles;
- cursor discontinuity;
- non-terminal "complete" response;
- page/record safety-limit overflow;
- declared row count != sum(page counts).

If the API returns current customer records only:

```text
Bronze MERGE
SCD2 SOURCE_DEFINED / observed only
```

If it returns immutable change events:

```text
Bronze APPEND
full-history capability depends on documented API completeness/retention
```

Pagination itself does not create history fidelity.

---

## 7.14 File incremental

### Example A — immutable transaction files

```text
/orders/2026/08/29/part-0001.parquet
/orders/2026/08/29/part-0002.parquet
```

Each row is an immutable transaction/event.

Use:

```text
Bronze APPEND raw/event rows
identity = file_uri + version_token/checksum + row identity
```

### Example B — mutable current-state file

A partner overwrites:

```text
/customer/current.csv
```

Path alone is unsafe. Require a stable object version/etag/checksum.

If each file is a complete authoritative customer snapshot, classify the semantic as `FULL_SNAPSHOT` or `SNAPSHOT_DIFF`, not simply “file incremental”.

### Framework file-manifest guard

```python
manifest = freeze_file_manifest(
    source_snapshot_ref="listing-42",
    files=discovered_files,
    complete_discovery=True,
)
```

The framework rejects:

- duplicate URI;
- same URI discovered with multiple versions;
- non-ready/in-progress objects by default;
- incomplete discovery;
- excessive file count;
- retry/replay manifest drift.

---

# 8. Bronze design rules

## 8.1 Bronze is source-faithful, but source-faithful does not always mean APPEND

A common slogan is “Bronze must always be append-only”. That is too simplistic for a reusable enterprise framework.

The correct rule is:

> Bronze must preserve enough source evidence to support the claimed recovery/history contract.

Examples:

```text
full current snapshot
    -> OVERWRITE current snapshot is legitimate
    -> snapshot_id/completeness evidence is mandatory

watermark current rows
    -> MERGE current Bronze is legitimate
    -> source ordering/version evidence is mandatory

full CDC/CDF/events
    -> APPEND is required if full event history is claimed

net CDC observations
    -> MERGE if only current Bronze is desired
    -> APPEND if batch observations are useful
    -> neither can recreate intermediate source changes
```

If regulation/audit requires raw immutable landing for every source, keep an immutable landing/archive **in addition to** the normalized Bronze contract. Do not force one storage ideology onto every source family.

## 8.2 Bronze must retain framework/source evidence

At minimum, preserve the applicable identity/order fields:

```text
_framework_dataset_run_id
_framework_ingested_at
source snapshot/file/window/cursor reference
source event/log/commit position
delete/change operation
provider/native correlation
schema identity
```

Full CDC/event Bronze must not drop the source event order before Silver.

---

# 9. SCD1 selection guide

SCD1 means “current-state projection where the latest accepted source state wins”.

Good fits:

- watermark current-state changes;
- watermark lookback;
- watermark + tombstone;
- net CDC;
- full CDC projected to current state;
- Delta CDF projected to current state;
- API current-state changes;
- file current-state extracts;
- event stream projected to entity state.

Required correctness:

```text
stable merge key
+ deterministic freshness/order
+ exact replay idempotency
+ stale-event policy
+ equal-position conflict policy
```

If no ordering coordinate exists, changed updates should fail closed unless unordered updates are explicitly authorized.

---

# 10. SCD2 selection guide

Before choosing SCD2, ask:

> Do I need history of **every source change**, or history of **what the ingestion process observed**?

### Full event history required

Prefer:

```text
CDC_FULL
TRANSACTION_LOG_CDC
DEBEZIUM_KAFKA
DELTA_CDF
EVENT_SOURCE where events represent state transitions
```

### Snapshot-grain history acceptable

Use:

```text
SNAPSHOT_DIFF
```

### Observed-change history acceptable

Use:

```text
WATERMARK_INCREMENTAL
WATERMARK_LOOKBACK
WATERMARK_TOMBSTONE
```

Document that intermediate changes may be missing.

### Net/batch history acceptable

Use:

```text
CDC_NET_CURRENT
CDC_NET_OBSERVATION
```

Document that the source/native layer already collapsed changes within each capture window.

### Source-defined

For:

```text
API_CURSOR_INCREMENTAL
FILE_INCREMENTAL
```

read the source contract first. Do not select SCD2 merely because `updated_at` exists.

---

# 11. Delete selection guide

## No delete signal

Examples:

```text
ordinary watermark current table
API returning active records only
```

Truthful behavior:

```text
hard delete cannot be detected
```

Options:

1. accept `delete_policy=IGNORE`;
2. obtain a separate tombstone/delete feed;
3. periodically reconcile against an authoritative full snapshot;
4. switch to CDC/snapshot-diff if delete correctness is required.

## Tombstone/soft delete

Normalize it as an explicit ordered change. Do not filter it out in DQ/transformation.

## Explicit CDC delete

Preserve operation + source position in Bronze and apply through explicit delete policy.

## Snapshot-inferred delete

Require complete snapshot evidence. Missing row is not a delete if the snapshot may be partial.

## Event source

Delete is source/business-defined. Absence of an event is never a delete.

---

# 12. Recovery and retry identities by family

| Family | Minimum replay identity |
|---|---|
| Full snapshot | immutable `snapshot_id` + completeness evidence |
| Watermark | PK + ordered timestamp/version/tie-breaker |
| Lookback watermark | same as watermark; overlap is expected |
| Tombstone watermark | PK + source order + delete marker |
| Net CDC | CDC window/source position + PK |
| Full CDC/log | unique source position + row sequence/event id |
| Debezium/Kafka | topic + partition + offset |
| Delta CDF | commit version + deterministic row event identity |
| Business event | event id or partition/offset |
| Snapshot diff | snapshot id + PK |
| API | frozen window + cursor chain + PK/event id |
| File | URI + stable version token/checksum + row identity where needed |

Never use only ingestion timestamp as replay identity.

---

# 13. Physical engine mapping examples

These are recommendations, not semantic guarantees.

## Watermark from SQL source

```text
Capture semantics: WATERMARK / WATERMARK_LOOKBACK
Possible engine: Copy Activity or Spark
Progress owner: FRAMEWORK when framework freezes source bounds
Apply: Spark framework UPSERT/SCD1/SCD2
```

## Fabric-native incremental/CDC

```text
Capture: Copy Job/Dataflow/Mirroring only under a certified capability profile
Progress owner: FABRIC_NATIVE
Handoff: CaptureReceipt
Apply: independently selected; framework Spark by default
```

A native capture being successful does not prove SCD1/SCD2 semantics.

## Debezium/Kafka

```text
engine: EXTERNAL_CDC
profile: debezium_kafka_v1
progress owner: EXTERNAL
canonical downstream apply checkpoint: framework-owned
```

## Delta CDF

Recommended initial framework implementation path:

```text
Spark reads bounded Delta CDF versions
    -> normalize to canonical CDCEvent
    -> Bronze APPEND
    -> framework UPSERT/SCD1/SCD2
    -> reconciliation
    -> commit downstream checkpoint
```

A dedicated provider adapter/profile should be added rather than treating CDF as arbitrary custom code.

## API

```text
provider/domain adapter fetches frozen window/pages
    -> APICaptureEvidence
    -> parser/normalizer
    -> framework apply
```

## Files

```text
provider/domain adapter discovers stable versions
    -> FrozenFileManifest
    -> parser
    -> framework apply according to file content semantics
```

---

# 14. What the framework currently implements vs what remains integration work

## Implemented/reference-certified

- FULL completeness and guarded REPLACE;
- WATERMARK composite ordering/overlap state semantics;
- SNAPSHOT completeness + guarded SNAPSHOT_DIFF;
- canonical CDC I/U/D/order/dedupe/checkpoint semantics;
- CDC -> UPSERT/SCD1/SCD2;
- Debezium/Kafka envelope adapter/reference resume planning;
- replay-stable API frozen-window/pagination guards;
- replay-stable file manifest/readiness/version guards;
- APPEND/REPLACE/UPSERT/SCD1/SCD2/SNAPSHOT_DIFF apply semantics;
- source-order vs event-time temporal taxonomy;
- executable 14-pattern onboarding catalog in this branch.

## Adapter/transport work still required

- dedicated Delta CDF adapter/profile and real Fabric execution;
- real API client transports and source-specific cursor semantics;
- real file-store discovery adapters for each governed storage mechanism;
- additional database-native log CDC adapters;
- actual Kafka client commit coordination;
- real Fabric Copy/Dataflow/SJD/Pipeline transports and retained DEV run evidence.

The catalog tells the framework **what must be true**. Provider adapters prove **how a specific technology satisfies it**.

---

# 15. Recommended onboarding record for every new dataset

For every dataset, record the following in the domain repository/review:

```text
dataset_id
capture_pattern
source owner
business/merge key
change fidelity
delete visibility
source ordering coordinate
retry identity
bootstrap method
retention/recovery window
Bronze write mode
Bronze content semantics
Silver apply strategy
SCD2 history fidelity claim
physical capture engine/profile
progress owner
known limitations
```

Example review record:

```yaml
dataset_id: crm.customer
capture_pattern: WATERMARK_LOOKBACK
change_fidelity: CURRENT_STATE
delete_visibility: NONE
source_order: [updated_at, source_version, customer_id]
retry_identity: [customer_id, updated_at, source_version]
lookback: 10m
bronze:
  write_mode: MERGE
  content: CURRENT_STATE
silver:
  apply: SCD1
  history_claim: CURRENT_STATE_ONLY
execution:
  capture_engine: FABRIC_COPY_ACTIVITY
  progress_owner: FRAMEWORK
  apply_engine: SPARK
known_limitations:
  - hard deletes are not visible
  - full source history is not available
```

This makes architectural truth reviewable before production incidents expose it.

---

# 16. Anti-patterns

Do not do these:

### “We use SCD2, therefore we have full history”

False. SCD2 cannot reconstruct changes the capture layer never saw.

### “The tool says incremental, therefore deletes are handled”

False. Incremental watermark commonly has no hard-delete signal.

### “CDC means full changes”

False. Many products expose net changes only.

### “Kafka offset means database transaction order”

Not necessarily. The consumed Kafka order is topic/partition/offset; database coordinates may be additional metadata.

### “A daily snapshot tells us when a row changed”

It tells you only that state differs between two observation points.

### “File path is a stable identity”

Not when files can be overwritten. Require version/etag/checksum evidence.

### “API pagination is a checkpoint”

Only if the API contract makes the cursor durable/replayable. Freeze the logical source window separately.

### “Bronze must always MERGE” / “Bronze must always APPEND”

Both are oversimplifications. Choose based on source fidelity and recovery/history requirements.

---

# 17. Practical default recommendations

If requirements are ordinary and no stronger source is available:

```text
current-state SQL table with reliable updated_at
    -> WATERMARK_LOOKBACK + Bronze MERGE + SCD1

same table, history needed but no CDC
    -> WATERMARK_LOOKBACK + SCD2
    -> explicitly claim OBSERVED_CHANGES only

hard deletes required, no CDC
    -> recurring complete SNAPSHOT_DIFF

native net CDC
    -> CDC_NET_CURRENT for current state
    -> CDC_NET_OBSERVATION if batch audit matters

full log/CDC available
    -> APPEND Bronze events + SCD1 current projection + SCD2 if history required

Debezium/Kafka
    -> DEBEZIUM_KAFKA

Delta source with CDF enabled and retention adequate
    -> DELTA_CDF

business event stream
    -> EVENT_SOURCE

incremental API
    -> API_CURSOR_INCREMENTAL + frozen-window/cursor evidence

incremental files
    -> FILE_INCREMENTAL + immutable manifest
    -> then classify file content as event/current/snapshot
```

When two patterns are possible, choose the one whose fidelity matches the business requirement without paying unnecessary operational cost.

---

# 18. Framework code references

```text
src/fabric_data_framework/capture/patterns.py
    executable pattern catalog and semantic assessment

src/fabric_data_framework/capture/api.py
    frozen API window + pagination evidence

src/fabric_data_framework/capture/files.py
    immutable file manifest/readiness evidence

src/fabric_data_framework/capture/cdc.py
    canonical CDC event/order/window/checkpoint

src/fabric_data_framework/capture/bootstrap_cdc.py
    snapshot -> CDC no-gap handoff

src/fabric_data_framework/watermark.py
    watermark planning/state semantics

src/fabric_data_framework/apply/
    APPEND/REPLACE/UPSERT/SCD1/CDC/SNAPSHOT_DIFF semantics
```

Every future provider adapter should map to one of these canonical source-fidelity contracts rather than creating a new target apply algorithm for each technology.
