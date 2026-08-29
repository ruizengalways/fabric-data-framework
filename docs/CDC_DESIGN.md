# CDC Design — fabric-data-framework

Status: Canonical provider-neutral CDC correctness contract
Last updated: 2026-08-29

## 1. Purpose

CDC is a capture/change representation, not an apply strategy.

The framework consumes CDC from Fabric-native, database-native, Delta or external systems without allowing Debezium, SQL Server LSNs, Delta commit versions, binlog coordinates, Kafka offsets or Copy Job details to redefine target semantics.

Canonical separation:

```text
provider CDC/CDF envelope / native checkpoint
        |
        v
provider adapter / capability profile
        |
        v
canonical CDCEvent + CDCCheckpoint
        |
        v
bounded normalization / dedupe / order proof
        |
        +--> UPSERT
        +--> SCD1
        +--> SCD2
        |
        v
reconciliation
        |
        v
cdc_checkpoint commit
```

`CDC != SCD2` remains a hard architecture invariant.

The broader source-fidelity/onboarding taxonomy is defined in `CAPTURE_PATTERN_CATALOG.md`. In particular, `CDC_NET_*` and full-event CDC are different history contracts even though both map to coarse `CaptureStrategy.CDC`.

## 2. Canonical source position

Provider adapters normalize source coordinates into:

```text
CDCSourcePosition
  partition: string
  values: tuple[int, ...]
```

Examples conceptually include:

```text
SQL Server       -> (LSN components..., row sequence)
Kafka/Debezium   -> topic:partition + (offset,)
Delta CDF        -> table reference + (commit_version, deterministic row sequence)
MySQL binlog     -> (file generation, position, row sequence)
other provider   -> deterministic integer tuple
```

The semantic core does not compare opaque provider strings and does not guess ordering.

If one native coordinate can contain several row changes, the provider adapter must expose enough sequence information to make each canonical event position unique or fail closed when order cannot be proven.

## 3. Canonical event

`CDCEvent` contains:

```text
event_id
operation: INSERT | UPDATE | DELETE
key
position
before
after
event_time
transaction_id
metadata
```

Validation rules include non-null key, operation-consistent before/after shape, payload/key consistency, reserved-field protection and timezone-aware event time where supplied.

Provider metadata may be retained, but correctness depends on typed canonical fields rather than arbitrary metadata keys.

## 4. Bounded CDC window

A normalized batch is bounded by:

```text
lower_checkpoint  # inclusive committed position, optional on first load
upper_checkpoint  # frozen inclusive boundary
complete_through_upper = true
```

The provider/capture stage must explicitly prove completeness through the frozen upper boundary.

Normalization guarantees:

- event position `> upper` -> fail;
- upper checkpoint regression -> fail;
- dropping an existing partition -> fail;
- event position `<= lower` -> already committed overlap, ignore;
- exact duplicate event ID + exact content -> idempotent ignore;
- same event ID + different content -> fail;
- two different events at one canonical position -> fail;
- same business key appearing in multiple partitions in one bounded batch -> fail unless deterministic per-key order is proven;
- accepted events are sorted deterministically.

The certified core deliberately rejects ambiguous repartition/key-movement/order cases rather than synthesizing business order.

## 5. Current-state apply: CDC -> UPSERT / SCD1

`apply/cdc.py` applies normalized events sequentially to current-state targets.

Target rows touched by CDC retain framework CDC partition/position metadata. Certified behavior includes insert/update/delete/reinsert, stale suppression, equal-position conflict detection, unchanged-state position advancement and bootstrap-boundary protection.

UPSERT and SCD1 share this CDC correctness path; semantic naming remains distinct.

## 6. History apply: CDC -> SCD2

SCD2 does not conflate two clocks:

```text
CDC source position -> source event order
event_time          -> business validity interval
```

Two events with the same `event_time` may still be ordered by distinct CDC positions.

Current certified behavior includes insert, changed/unchanged update, delete, reinsert, closing-position evidence and equal-source-position conflict failure.

A newer source event whose event/valid time is earlier than the current version requires retroactive history rewrite. That behavior remains intentionally unsupported and raises `CDCSCD2LateArrivingError` rather than silently rewriting history.

## 7. Checkpoint state and concurrency

`cdc_checkpoint` is environment-local control-plane state:

```text
cdc_checkpoint
  dataset_id
  positions
  committed_dataset_run_id
  version
  created_at
  updated_at
```

Canonical source positions represent framework downstream semantic application progress. `version` is the optimistic-concurrency token, not an LSN/offset/commit version itself.

Checkpoint commit requires target mutation committed, required reconciliation passed, no position regression/partition drop and a matching expected version.

For FABRIC_NATIVE or EXTERNAL capture, provider source progress remains provider-owned and is correlated separately. The framework checkpoint must not pretend to own a native cursor.

For framework-owned source readers such as `SPARK/delta_cdf_v1`, the bounded source coordinate and downstream application checkpoint can be framework-controlled, but the state still advances only after target/reconciliation success.

## 8. Snapshot/bootstrap -> CDC handoff

Safe bootstrap requires a retained CDC start/fence around a complete snapshot:

```text
retain CDC from S
S <= snapshot consistency boundary B
complete snapshot through B
apply/publish snapshot
CDC <= B -> overlap already represented
CDC >  B -> apply
```

Incomplete/future-start/repartition/regression cases fail closed.

## 9. Debezium on Kafka built-in provider profile

```text
execution engine: EXTERNAL_CDC
capability profile: debezium_kafka_v1
progress owner: EXTERNAL
apply engine: independent; framework/Spark by default
```

Implementation ownership:

```text
adapters/cdc/debezium_kafka.py
adapters/cdc/resume.py
adapters/cdc/registry.py
metadata/capabilities.py
```

### Canonical ordering

```text
topic + partition + offset
        |
        v
partition = "<topic>:<partition>"
values    = (offset,)
```

Database LSN/binlog coordinates are retained as provider metadata rather than guessed into a universal row order.

### Envelope policy

```text
Debezium op=c -> INSERT
Debezium op=u -> UPDATE
Debezium op=d -> DELETE
Kafka tombstone -> transport cleanup; ignore
```

Snapshot `op=r` is rejected by default to avoid double-applying bootstrap state. Explicit adapter policy is required to treat it as insert.

### Recovery

Safe resume is derived from the framework-applied checkpoint, not a possibly-ahead consumer-group cursor:

```text
next_required = committed_framework_offset + 1
```

Retention floor later than `next_required`, missing committed partitions or impossible requested bounds fail closed. The planner proves safe reread range but does not claim to manage a real Kafka consumer group.

## 10. Delta Change Data Feed built-in provider profile

Delta CDF is now a first-class provider/reference adapter rather than a CUSTOM-only source.

```text
execution engine: SPARK
capability profile: delta_cdf_v1
progress owner: FRAMEWORK
capture strategy: CDC
apply engine: independent; framework/Spark by default
```

Implementation ownership:

```text
adapters/cdc/delta_cdf.py
adapters/cdc/registry.py
metadata/capabilities.py
```

### Input contract

`DeltaCDFRecord` models:

```text
change_type
  insert
  delete
  update_preimage
  update_postimage

commit_version
commit_timestamp
data
```

Commit timestamp must be timezone-aware and is retained as event time/evidence. Commit version is the source ordering boundary used for checkpointing.

### UPDATE normalization

For one business key inside one commit:

```text
update_preimage + update_postimage
        |
        v
one canonical UPDATE
  before = preimage
  after  = postimage
```

Missing pairs or ambiguous record-type combinations fail closed.

### Within-commit ordering boundary

Delta CDF exposes commit ordering but does not provide a universal framework-independent row sequence for arbitrary multiple logical mutations of the same key inside one commit.

Therefore the adapter is deliberately conservative:

- different keys in one commit receive a deterministic key-sorted row sequence so framework processing/checkpoint positions are stable;
- metadata marks this as deterministic processing order, **not invented business temporal order**;
- more than one non-identical same-type row for the same key+commit fails;
- more than one logical mutation of the same key in one commit that cannot be uniquely reconstructed fails.

This prevents deterministic implementation order from being misrepresented as source temporal truth.

### Canonical position and checkpoint

Conceptually:

```text
partition = "delta-cdf:<table_reference>"
position  = (commit_version, deterministic_row_sequence)
```

A committed CDF version checkpoint represents the whole commit using a terminal sequence sentinel:

```text
(commit_version, MAX_COMMIT_ROW_SEQUENCE)
```

This allows intentional overlap reads: records at/below the lower committed version are normalized as already-applied overlap and ignored idempotently.

### Bounded read contract

`normalize_delta_cdf_batch()` requires:

- non-empty table reference;
- unique non-null business key columns;
- frozen upper commit version;
- explicit `complete_through_upper=true` evidence;
- optional lower committed version not greater than upper;
- no input row beyond the frozen upper version.

Exact duplicate provider rows are ignored idempotently. Conflicting/ambiguous same-key/commit records fail closed.

### Retention/recovery boundary

The adapter/profile defines the checkpoint contract but does not yet call a real Fabric Lakehouse reader. A future transport must prove the requested version range still exists. If retention has removed the next unapplied version, recovery must surface an explicit gap; it must not jump to a newer CDF version.

### Evidence level

Current Delta CDF status is:

```text
canonical adapter          ADAPTER CONTRACT
commit checkpoint semantics REFERENCE
capability/profile registry REFERENCE
real Fabric Lakehouse CDF   NOT YET PROVEN
```

## 11. Provider registry

`CDCProviderAdapterRegistry` resolves by:

```text
(ExecutionEngine, capability_profile)
```

Default built-in mappings now include:

```text
(EXTERNAL_CDC, debezium_kafka_v1)
    -> DebeziumKafkaCDCAdapter

(SPARK, delta_cdf_v1)
    -> DeltaCDFCDCAdapter
```

Unknown/duplicate registrations fail explicitly. The registry does not construct provider clients, credentials or arbitrary parser imports.

## 12. Physical progress ownership

There are two different questions:

```text
Who owns source/native capture progress?
Who owns framework downstream semantic application progress?
```

Examples:

```text
Copy Job / Fabric-native CDC
  native checkpoint authority -> FABRIC_NATIVE
  CaptureReceipt retains native correlation
  framework apply checkpoint tracks downstream semantic completion

Debezium/Kafka
  source consumer/connector progress -> EXTERNAL
  safe reread starts from framework downstream apply checkpoint
  external cursor commit remains provider integration

Delta CDF via Spark
  bounded CDF commit-version reader -> FRAMEWORK
  checkpoint advances only after target/reconciliation success
```

The framework must never move a native/external source cursor merely because downstream apply succeeded unless the corresponding adapter/transport explicitly owns that commit protocol.

## 13. Recovery interaction

CDC participates in the same fail-closed recovery model:

```text
capture/window/version range frozen
 -> normalize/apply
 -> target outcome
 -> reconcile
 -> cdc_checkpoint commit
```

Unknown target outcome is resolved as COMMITTED / NOT_COMMITTED / UNRESOLVED before retry/state movement.

## 14. Current deterministic evidence

Earlier CDC sequence:

```text
ccf0fc8950efb1f4d338cadcaf83aac5fd49a7b9
Actions 33215409341
canonical CDC + CDC -> UPSERT/SCD1

ed6c13d4fcabe165ef86be2e547d794e15e5375c
Actions 33215708004
CDC -> SCD2

c41fbd00bb3d3c6bc71e20f958c4ec14106ac33c
Actions 33216133811
durable downstream checkpoint

465a2c1e9ddf25b0ace2293f578c2c5bb3a653ae
Actions 33216281126
snapshot/bootstrap -> CDC

1087ab9231b9cb638a87bc2f78ef0c1b1fe32beb
Actions 33219601375
Debezium/Kafka adapter + safe resume
```

Current provider/onboarding extension:

```text
78018b90c3dfb7f7ff2297aa173e9e8dfaee40e6
Actions 33237905150
310 tests passed
Delta CDF adapter/profile + capture pattern catalog/onboarding examples
```

These are REFERENCE/ADAPTER-CONTRACT/CI proofs, not evidence of real Kafka, Debezium, Delta CDF or Fabric workspace execution.

## 15. Remaining CDC work

1. real Kafka/Debezium transport and consumer-group correlation/commit evidence;
2. real Fabric Lakehouse Delta CDF bounded-read and retention-gap recovery evidence;
3. additional provider mappings only for explicitly supported source products;
4. provider transaction-boundary handling where atomic multi-row treatment is required;
5. partition/rebalance/source-epoch operational policies beyond the current fail-closed model;
6. poison-event quarantine/replay integration;
7. retroactive SCD2 history correction only if product scope chooses to support it;
8. persistent production control-plane repository and transaction tests;
9. approved DEV end-to-end CDC/CDF executions.

## 16. Extension boundary

Provider-specific parsing belongs in a controlled adapter/extension boundary, not the semantic core.

```text
built-in supported provider adapter
  OR
registered logical extension name
        |
        v
CDCEvent / CDCCheckpoint
        |
        v
all reusable framework guarantees
```

A strange source format may customize parsing/position normalization while still using the same CDC ordering, apply, reconciliation, recovery and state machinery.
