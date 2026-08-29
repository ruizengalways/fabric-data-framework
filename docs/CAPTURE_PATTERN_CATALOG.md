# Capture Pattern Catalog and New-Source Onboarding Playbook

Status: Canonical onboarding guide  
Last updated: 2026-08-29

## 1. Purpose

When a new source arrives, do **not** start with “SCD1 or SCD2?”, “Copy Job or Notebook?”, or “MERGE or APPEND?”. Start with:

> **What facts does the source actually expose, with what ordering, delete visibility, completeness and replay identity?**

That source contract puts a hard upper bound on what Bronze and Silver can truthfully represent.

The framework deliberately separates:

```text
source/capture pattern
    -> what facts exist

change fidelity
    -> current state / net changes / full row changes / business events

delete visibility
    -> none / snapshot-inferred / tombstone / explicit event / source-defined

Bronze policy
    -> OVERWRITE / MERGE / APPEND

Silver apply
    -> APPEND / REPLACE / UPSERT / SCD1 / SCD2 / SNAPSHOT_DIFF

physical execution
    -> Copy Job / Copy Activity / Dataflow Gen2 / Spark /
       Mirroring / External CDC / SQL / controlled extension
```

A physical engine cannot improve source fidelity. If a source returns only net changes, no Spark code can reconstruct intermediate changes that never arrived.

---

## 2. Golden rule: capture fidelity caps history fidelity

The framework uses explicit `HistoryFidelity` values:

```text
NONE
OBSERVED_CHANGES
BATCH_GRAIN
FULL_EVENT
SNAPSHOT_GRAIN
SOURCE_DEFINED
```

Interpret them literally:

```text
current-state snapshot
  -> current truth at observation time
  -> recurring complete snapshots can infer snapshot-to-snapshot changes
  -> changes between snapshots are unknowable

watermark/current-state incremental
  -> rows that crossed the source ordering boundary
  -> hard deletes usually invisible
  -> SCD2 = history of captured observations

native net CDC
  -> final change/state per key per capture window
  -> intermediate changes already collapsed upstream
  -> SCD2 = batch-grain history

full ordered CDC/CDF/log
  -> every captured I/U/D row event in deterministic order
  -> full captured event history is possible

business event source
  -> events are the source facts themselves
  -> relational current state/SCD2 are downstream projections
```

An SCD2 target does **not** prove full source history.

---

## 3. Mainstream pattern matrix

| # | `CapturePattern` | What actually arrives | Delete visibility | Change fidelity | Bronze default | Retry/replay identity | SCD1 | SCD2/history truth |
|---:|---|---|---|---|---|---|---|---|
| 1 | `FULL_SNAPSHOT` | Whole authoritative current table | Snapshot-inferred | Current state | `OVERWRITE` | snapshot id | Yes | Snapshot-grain only |
| 2 | `WATERMARK_INCREMENTAL` | Rows after watermark | None normally | Current-state observations | `MERGE` | PK + watermark + tie-breaker | Yes | `OBSERVED_CHANGES` |
| 3 | `WATERMARK_LOOKBACK` | Recent overlap window intentionally re-read | None normally | Current-state observations | `MERGE` | PK + timestamp/version | Yes | `OBSERVED_CHANGES` |
| 4 | `WATERMARK_TOMBSTONE` | Changed rows + delete marker | Tombstone | Net/current | `MERGE` or bounded `APPEND` | PK + order + tombstone | Yes | Observed changes incl. captured deletes |
| 5 | `CDC_NET_CURRENT` | Final native change/state per key per window | Explicit | Net change | `MERGE` | CDC position + PK | Yes | `BATCH_GRAIN` |
| 6 | `CDC_NET_OBSERVATION` | Same net feed, retained per ingestion batch | Explicit | Net change | `APPEND` | batch id + PK | Yes | `BATCH_GRAIN` |
| 7 | `CDC_FULL` | Every ordered I/U/D row change | Explicit | Full change | `APPEND` | source position + event id | Yes | `FULL_EVENT` |
| 8 | `TRANSACTION_LOG_CDC` | Row changes from LSN/SCN/binlog/log position | Explicit | Usually full change | `APPEND` | log position + row sequence | Yes | `FULL_EVENT` |
| 9 | `DEBEZIUM_KAFKA` | Debezium events consumed from Kafka | Explicit | Full change | `APPEND` | topic + partition + offset | Yes | `FULL_EVENT` |
| 10 | `DELTA_CDF` | Delta CDF insert/delete/update pre/post rows | Explicit | Full change | `APPEND` | commit version + row event identity | Yes | `FULL_EVENT` for captured changes |
| 11 | `EVENT_SOURCE` | Immutable business/domain events | Source-defined | Full event | `APPEND` | event id or provider offset | Usually | Full event source; SCD2 is projection |
| 12 | `SNAPSHOT_DIFF` | Snapshot N vs N-1 diff | Snapshot-inferred | Net change | `APPEND` diff or `MERGE` current | snapshot id + PK | Yes | `SNAPSHOT_GRAIN` |
| 13 | `API_CURSOR_INCREMENTAL` | API records/events through cursor/window | Source-defined | Source-defined | Usually `MERGE`, `APPEND` for events | frozen window + cursor chain + PK/event id | Yes | `SOURCE_DEFINED` |
| 14 | `FILE_INCREMENTAL` | New/changed immutable/versioned files | Source-defined | File-content-defined | `APPEND` raw/events or `MERGE` current | URI + version/checksum | Yes | `SOURCE_DEFINED` |

This matrix is executable in `fabric_data_framework.capture.patterns` rather than being documentation only.

---

## 4. New-source decision tree

### Step 1 — Is the source a business event stream?

If records are immutable facts such as `OrderPlaced`, `PaymentCaptured`, `ShipmentDispatched`:

```text
EVENT_SOURCE
Bronze = APPEND immutable events
identity = event_id or provider partition/offset
```

Do not turn an event stream into fake relational CDC before Bronze unless the product explicitly requires that projection.

### Step 2 — Can the source provide every row-level change in deterministic order?

If yes, choose the matching provider/source family:

```text
generic ordered I/U/D     -> CDC_FULL
database transaction log  -> TRANSACTION_LOG_CDC
Debezium over Kafka        -> DEBEZIUM_KAFKA
Delta Change Data Feed     -> DELTA_CDF
```

Default architecture:

```text
Bronze APPEND change events
  -> current projection UPSERT/SCD1
  -> history projection SCD2 when needed
```

### Step 3 — Does native CDC return only net/final changes per key/window?

If current Bronze is enough:

```text
CDC_NET_CURRENT
Bronze MERGE
```

If audit/diagnostics need every ingestion observation:

```text
CDC_NET_OBSERVATION
Bronze APPEND observations
```

Neither pattern is full event history.

### Step 4 — Is there a reliable updated/version watermark?

If yes:

```text
strict reliable ordering            -> WATERMARK_INCREMENTAL
late commits/clock delay possible   -> WATERMARK_LOOKBACK
explicit soft-delete/tombstone      -> WATERMARK_TOMBSTONE
```

Prefer a bounded lookback when rereading a small overlap is cheaper than missing late rows.

### Step 5 — Can the source provide complete authoritative snapshots?

For current state:

```text
FULL_SNAPSHOT
FULL -> REPLACE
```

For delete inference or snapshot-grain history:

```text
SNAPSHOT_DIFF
SNAPSHOT -> SNAPSHOT_DIFF
```

### Step 6 — Is the source an API?

Use `API_CURSOR_INCREMENTAL` when a stable cursor/change window exists. Freeze the logical window before page 1 and prove cursor continuity/completeness. Delete/history fidelity comes from the API contract, not pagination itself.

### Step 7 — Is the source delivered as files?

Use `FILE_INCREMENTAL` for governed discovery/version evidence, then classify the file **content**:

```text
immutable transactions/events -> APPEND
current-state extract          -> MERGE/current-state semantics
complete snapshot              -> FULL_SNAPSHOT or SNAPSHOT_DIFF semantics
```

“File source” is a transport shape, not a history semantic.

---

## 5. Source-owner questionnaire

Every onboarding ticket should answer at least:

1. Is this current state, snapshot, change feed, transaction log or business event stream?
2. Can the source provide a complete authoritative snapshot?
3. Can rows be hard-deleted?
4. How are deletes exposed: none, soft-delete flag, tombstone, explicit event, snapshot absence?
5. What is the stable business/primary key?
6. Can that key change?
7. What is the ordering coordinate: timestamp, version, sequence, LSN, SCN, binlog, commit version, cursor, offset?
8. Can two rows share that coordinate? What tie-breaker proves deterministic order?
9. Can changes arrive late/out of order?
10. Are before image, after image or both available?
11. What identity makes retry/replay idempotent?
12. What is the CDC/CDF/cursor/file retention period?
13. Can an overlap range be reread safely?
14. Can cursor/offset/history expire?
15. Is a bootstrap snapshot available?
16. Can CDC be retained while bootstrap runs?
17. How are schema add/remove/rename/type changes communicated?
18. Does schema change affect historical replay?
19. Expected volume/change rate/file/page count?
20. Source concurrency/rate limits?
21. SLA/latency requirement?
22. Gateway/private-network requirement?
23. Which connector/profile is actually approved/supported in the target tenant?
24. What known source limitations must be written into the dataset review?

Unknown ordering/delete/recovery answers mean conservative classification. Do not infer stronger semantics from a product label such as “incremental”.

---

## 6. Source-controlled onboarding contract

`DatasetCaptureSelection` records the reviewable source truth:

```text
dataset_id
capture_pattern
bronze_write_mode
history_claim
delete_claim
rationale
known_limitations
```

Example:

```json
{
  "dataset_id": "crm.customer",
  "capture_pattern": "WATERMARK_LOOKBACK",
  "bronze_write_mode": "MERGE",
  "history_claim": "OBSERVED_CHANGES",
  "delete_claim": "NONE",
  "rationale": "CRM exposes updated_at but no hard-delete feed.",
  "known_limitations": [
    "Hard deletes are not visible.",
    "History represents captured observations only."
  ]
}
```

`validate_capture_selection()` rejects contradictory claims. Examples:

```text
WATERMARK_LOOKBACK + FULL_EVENT history -> FAIL
WATERMARK_LOOKBACK + EXPLICIT_EVENT delete visibility -> FAIL
CDC_FULL + Bronze MERGE while claiming full events -> FAIL
WATERMARK_LOOKBACK + overlap=0 -> FAIL
DEBEZIUM_KAFKA mapped to coarse FULL -> FAIL
```

Domain CI command:

```bash
fabric-framework capture-onboarding-validate \
  --config-dir config/datasets \
  --selections config/capture-selections.json \
  --require-all
```

`--require-all` makes any unclassified DatasetConfig a CI error.

The selection is currently a Git/CI companion contract. It is intentionally not a new relational control-plane table in this slice.

---

## 7. Executable examples in this repository

Copy from:

```text
docs/examples/capture-patterns/
```

Included examples:

```text
crm.customer
  WATERMARK_LOOKBACK
  Bronze MERGE
  SCD1
  Copy Activity capture + framework Spark apply

commerce.order_cdc
  DEBEZIUM_KAFKA
  Bronze APPEND events
  SCD2
  EXTERNAL_CDC/debezium_kafka_v1

lakehouse.customer_cdf
  DELTA_CDF
  Bronze APPEND changes
  SCD2
  SPARK/delta_cdf_v1

partner.customer_api
  API_CURSOR_INCREMENTAL
  Bronze MERGE
  SCD1
  API semantics remain SOURCE_DEFINED

vendor.account_files
  FILE_INCREMENTAL
  versioned complete snapshot files
  SNAPSHOT_DIFF
```

`tests/test_capture_pattern_examples.py` loads these files as real typed config and validates their capability/onboarding contracts. They are not pseudo-code.

---

## 8. Pattern details

### 8.1 `FULL_SNAPSHOT`

Use when every run can obtain a complete authoritative current-state object.

```text
Bronze: OVERWRITE current snapshot
required evidence: immutable snapshot id + completeness
current Silver: REPLACE or SCD1 projection
history: snapshot-grain only
```

A missing row is a delete only when the snapshot is proven complete. If history/delete inference is required across recurring snapshots, use the `SNAPSHOT_DIFF` semantic rather than pretending one snapshot contains row events.

### 8.2 `WATERMARK_INCREMENTAL`

Typical SQL/current-state table:

```text
customer_id
name
status
updated_at
source_version
```

Recommended source ordering:

```text
(updated_at, source_version?, tie_breaker...)
```

Bronze normally MERGEs current state. Hard deletes are invisible unless another signal exists. SCD2 is `OBSERVED_CHANGES` only.

### 8.3 `WATERMARK_LOOKBACK`

Use a positive overlap when source commits/timestamps may arrive late:

```yaml
watermark:
  column: modified_at
  tie_breaker: [order_id]
  overlap_window_seconds: 600
```

Repeated reads are expected. Idempotent UPSERT/SCD1/SCD2 and stale/equal-position handling make the overlap safe. State still advances only after target commit + reconciliation.

### 8.4 `WATERMARK_TOMBSTONE`

A soft-delete flag or explicit tombstone makes deletes observable:

```text
id=42, is_deleted=true, updated_at=..., version=17
```

Do not filter tombstones out during parsing/DQ. Normalize them into explicit delete semantics and include the delete marker in replay/order reasoning.

### 8.5 `CDC_NET_CURRENT`

Suppose a native feed sees:

```text
10:01 A -> B
10:04 B -> C
10:10 C -> D
```

but returns only D for the capture window. Use Bronze MERGE for current state. SCD2 may record D, but B/C are unrecoverable and history is `BATCH_GRAIN`.

### 8.6 `CDC_NET_OBSERVATION`

Same source fidelity, but retain each ingestion observation:

```text
batch b001, key 42, state D
batch b002, key 42, state E
```

Bronze APPEND is useful for audit/diagnostics but still does not make the source full-event CDC.

### 8.7 `CDC_FULL`

Every ordered I/U/D row mutation is available. Bronze must APPEND if full captured event history is claimed. Normalize source coordinates into unique canonical `CDCSourcePosition` values; do not use a position that is shared by multiple unsequenced row changes.

### 8.8 `TRANSACTION_LOG_CDC`

Examples:

```text
SQL Server LSN + row sequence
Oracle SCN + row sequence
MySQL binlog generation + position + row number
```

Provider adapters must convert these into deterministic integer tuples. Retention gaps fail closed; the framework must not jump over an expired unapplied log range.

### 8.9 `DEBEZIUM_KAFKA`

Built-in profile:

```text
engine: EXTERNAL_CDC
profile: debezium_kafka_v1
progress owner: EXTERNAL
canonical consumed order: topic + partition + offset
```

Certified reference behavior includes c/u/d normalization, tombstone handling, snapshot `op=r` fail-closed by default, explicit Kafka key and retention-aware resume from framework-applied progress rather than a possibly-ahead consumer-group cursor.

Real Kafka transport/commit remains integration work.

### 8.10 `DELTA_CDF`

Built-in profile:

```text
engine: SPARK
profile: delta_cdf_v1
progress owner: FRAMEWORK
capture strategy: CDC
```

Typed input:

```text
_change_type equivalent:
  insert
  delete
  update_preimage
  update_postimage

commit_version
commit_timestamp
row data
```

`DeltaCDFCDCAdapter` now:

- maps insert/delete to canonical CDC;
- pairs one update preimage/postimage for the same key+commit into one UPDATE;
- ignores exact duplicate input records;
- requires non-null key;
- rejects records above the frozen upper commit version;
- requires explicit completeness through upper;
- supports lower-version overlap replay;
- fails if same-key/commit mutation order is ambiguous.

Canonical checkpoint uses commit version plus a terminal row-sequence sentinel. Different keys in one commit receive deterministic key-sorted framework sequence; this is **processing order, not invented business temporal order**.

Bronze should APPEND CDF changes when full captured change history is required. Silver current state may use UPSERT/SCD1 and history may use SCD2.

Real Fabric Lakehouse CDF read/retention-gap execution is not yet proven. Current evidence is adapter/profile/reference only.

### 8.11 `EVENT_SOURCE`

Business events are immutable source facts:

```json
{"event_id":"e1","type":"OrderPlaced","order_id":1001}
{"event_id":"e2","type":"PaymentCaptured","order_id":1001}
{"event_id":"e3","type":"OrderCancelled","order_id":1001}
```

Bronze APPENDs events. SCD1/SCD2 can be downstream projections. `OrderCancelled` is not automatically a relational DELETE unless the projection contract says so.

### 8.12 `SNAPSHOT_DIFF`

Given complete snapshots:

```text
D1: 1=A, 2=B, 3=C
D2: 1=A, 2=B2, 4=D
```

Diff is:

```text
1 unchanged
2 update
3 delete
4 insert
```

Safety requires complete snapshots, unique/non-null key and delete guards. History is only snapshot-grain; changes between D1 and D2 are unknowable.

### 8.13 `API_CURSOR_INCREMENTAL`

Freeze a logical window before page 1:

```text
window id
lower/upper bound
predicate hash
initial cursor
```

Then prove:

```text
page numbering contiguous
request cursor == prior next cursor
no cursor cycles
terminal cursor when complete
page/record limits
sum(page rows) == declared rows
```

If API returns current rows, Bronze usually MERGEs. If it returns immutable change events, Bronze APPEND may be correct. Delete/history fidelity remains source-defined.

### 8.14 `FILE_INCREMENTAL`

Freeze a complete governed manifest:

```text
source snapshot/listing reference
URI
stable version token / checksum / etag
size
last_modified
readiness
```

Reject duplicate URI, conflicting versions, in-progress files, incomplete discovery and retry manifest drift.

Then classify file contents. A daily complete current snapshot should use snapshot semantics; immutable transaction files should APPEND events. File path alone is not stable replay identity when overwrite is possible.

---

## 9. Bronze rules

“Bronze must always append” and “Bronze must always merge” are both too simplistic.

Use:

```text
complete full snapshot -> OVERWRITE may be valid
watermark/current rows -> MERGE may be valid
full CDC/CDF/events    -> APPEND when event history is claimed
net CDC                -> MERGE current or APPEND observations
```

If audit/regulation requires immutable raw landing, retain that governed archive in addition to the normalized Bronze contract.

Preserve applicable lineage/order evidence such as dataset run, ingestion time, snapshot/file/window/cursor reference, source event/log/commit position, delete/change operation, provider correlation and schema identity.

---

## 10. SCD1 guide

SCD1 is a current-state projection. Good fits include watermark rows, tombstones, net/full CDC, CDF, APIs, file extracts and event streams projected to entity state.

Correctness requires:

```text
stable merge key
+ deterministic freshness/order
+ exact replay idempotency
+ stale-event policy
+ equal-position conflict policy
```

Changed unordered updates fail closed unless explicitly authorized.

---

## 11. SCD2 guide

Ask which history is required:

```text
Every captured row change
  -> prefer CDC_FULL / TRANSACTION_LOG_CDC / DEBEZIUM_KAFKA / DELTA_CDF

Snapshot-grain state history
  -> SNAPSHOT_DIFF

Observed incremental history
  -> WATERMARK_INCREMENTAL / WATERMARK_LOOKBACK / WATERMARK_TOMBSTONE

Net/batch observations
  -> CDC_NET_CURRENT / CDC_NET_OBSERVATION

Source-defined
  -> API_CURSOR_INCREMENTAL / FILE_INCREMENTAL
```

Never select SCD2 merely because the target wants history; first prove the capture can supply the required history fidelity.

---

## 12. Delete guide

```text
DeleteVisibility.NONE
  -> cannot discover hard deletes
  -> IGNORE, separate delete feed, periodic authoritative reconciliation, or stronger capture

SNAPSHOT_INFERRED
  -> complete snapshot required

TOMBSTONE
  -> preserve/normalize ordered delete marker

EXPLICIT_EVENT
  -> preserve operation + source position

SOURCE_DEFINED
  -> source/API/file/business contract decides
```

Absence from a partial extract is never sufficient delete evidence.

---

## 13. Retry/replay identity guide

| Source family | Minimum stable identity |
|---|---|
| Full snapshot | snapshot id + completeness |
| Watermark/lookback | PK + ordered timestamp/version/tie-breaker |
| Tombstone watermark | PK + source order + delete marker |
| Net CDC | source window/position + PK |
| Full CDC/log | unique source position + row sequence/event id |
| Debezium/Kafka | topic + partition + offset |
| Delta CDF | commit version + deterministic row event identity |
| Event source | event id or provider partition/offset |
| Snapshot diff | snapshot id + PK |
| API | frozen window + cursor chain + PK/event id |
| File | URI + stable version token/checksum + row identity when needed |

Never use only ingestion timestamp as replay identity.

---

## 14. Physical engine examples

### SQL watermark

```text
pattern: WATERMARK_LOOKBACK
capture: Copy Activity or Spark
progress: FRAMEWORK
apply: framework Spark UPSERT/SCD1/SCD2
```

### Fabric-native incremental/CDC

```text
native capture only under certified engine/profile
progress: FABRIC_NATIVE
handoff: CaptureReceipt
apply: independent, framework Spark by default
```

### Debezium/Kafka

```text
EXTERNAL_CDC / debezium_kafka_v1 / EXTERNAL progress
```

### Delta CDF

```text
SPARK / delta_cdf_v1 / FRAMEWORK progress
bounded commit-version read
-> canonical CDC
-> framework apply/reconciliation/checkpoint
```

### API

```text
provider/domain transport
-> frozen APICaptureWindow + page evidence
-> parser/normalizer
-> framework apply
```

### Files

```text
provider/domain discovery
-> FrozenFileManifest
-> parser
-> apply according to file-content semantics
```

---

## 15. Current implementation vs integration work

### Implemented/reference-certified

- all 14 capture-pattern definitions and semantic assessments;
- source-controlled `DatasetCaptureSelection`;
- `capture-onboarding-validate` CLI/CI gate;
- five checked-in executable onboarding examples;
- FULL/SNAPSHOT completeness and guarded apply;
- composite WATERMARK/overlap;
- canonical CDC/order/dedupe/checkpoint;
- CDC -> UPSERT/SCD1/SCD2;
- Debezium/Kafka adapter + reference safe resume;
- Delta CDF adapter + `SPARK/delta_cdf_v1` profile/registry;
- replay-stable API and file guardrails;
- APPEND/REPLACE/UPSERT/SCD1/SCD2/SNAPSHOT_DIFF;
- shared source-order/event-time taxonomy.

### Still integration work

- real Fabric Copy/Dataflow/SJD/Pipeline transports;
- real Kafka consumer seek/poll/commit;
- real Fabric Lakehouse Delta CDF read + retention-gap recovery proof;
- source-specific API transports/cursor semantics;
- source-specific file discovery/storage transports;
- additional database-native log CDC adapters;
- enterprise auth/network/gateway/capacity evidence.

The catalog defines **what must be true**. Provider adapters prove **how a technology maps to the canonical contract**. Real environment tests prove **that the configured service actually satisfies it**.

---

## 16. New-dataset review record

For every dataset, review at least:

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
Bronze write mode/content
Silver apply strategy
history fidelity claim
physical capture engine/profile
progress owner
known limitations
```

Example:

```yaml
dataset_id: crm.customer
capture_pattern: WATERMARK_LOOKBACK
change_fidelity: CURRENT_STATE
delete_visibility: NONE
source_order: [updated_at, row_version, customer_id]
retry_identity: [customer_id, updated_at, row_version]
lookback: 10m
bronze:
  write_mode: MERGE
silver:
  apply: SCD1
execution:
  capture_engine: FABRIC_COPY_ACTIVITY
  progress_owner: FRAMEWORK
  apply_engine: SPARK
known_limitations:
  - hard deletes are not visible
  - full source history is not available
```

---

## 17. Anti-patterns

Do not say:

```text
“We use SCD2, therefore we have full history.”
“The connector says incremental, therefore deletes are handled.”
“CDC always means full changes.”
“Kafka offset is automatically database transaction order.”
“A daily snapshot tells us when every row changed.”
“File path is stable identity.”
“API pagination is automatically a durable checkpoint.”
“Bronze must always MERGE.”
“Bronze must always APPEND.”
```

Each statement hides a source-contract assumption that must be explicit.

---

## 18. Practical defaults

```text
ordinary SQL current-state table + updated_at
  -> WATERMARK_LOOKBACK + Bronze MERGE + SCD1

same source, history requested but no CDC
  -> WATERMARK_LOOKBACK + SCD2
  -> claim OBSERVED_CHANGES only

hard deletes required, no CDC
  -> recurring complete SNAPSHOT_DIFF

native net CDC
  -> CDC_NET_CURRENT for current state
  -> CDC_NET_OBSERVATION if batch audit matters

full ordered CDC/log
  -> APPEND Bronze events + SCD1 current + SCD2 when history required

Debezium/Kafka
  -> DEBEZIUM_KAFKA

Delta table with CDF enabled and adequate retention
  -> DELTA_CDF / SPARK / delta_cdf_v1

business events
  -> EVENT_SOURCE

incremental API
  -> API_CURSOR_INCREMENTAL + frozen window/cursor evidence

incremental files
  -> FILE_INCREMENTAL + immutable manifest
  -> then classify content as event/current/snapshot
```

Choose the weakest operational mechanism that still truthfully satisfies the required business fidelity; do not pay CDC complexity for a current-state requirement, and do not use a weak watermark feed when full delete/history correctness is mandatory.

---

## 19. Code/document references

```text
src/fabric_data_framework/capture/patterns.py
src/fabric_data_framework/capture/onboarding.py
src/fabric_data_framework/capture/api.py
src/fabric_data_framework/capture/files.py
src/fabric_data_framework/capture/cdc.py
src/fabric_data_framework/capture/bootstrap_cdc.py
src/fabric_data_framework/adapters/cdc/debezium_kafka.py
src/fabric_data_framework/adapters/cdc/delta_cdf.py
src/fabric_data_framework/adapters/cdc/registry.py
src/fabric_data_framework/metadata/capabilities.py
src/fabric_data_framework/apply/
docs/examples/capture-patterns/
```

Official external references used for the Delta CDF design include Delta Lake Change Data Feed documentation and Microsoft Fabric Delta Change Data Feed documentation. Provider documentation is evidence about provider behavior; framework semantics remain defined by the contracts above.
