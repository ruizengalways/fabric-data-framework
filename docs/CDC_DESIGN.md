# CDC Design — fabric-data-framework

Status: Canonical provider-neutral CDC correctness contract
Last updated: 2026-08-29

## 1. Purpose

CDC is a capture/change representation, not an apply strategy.

The framework consumes CDC from Fabric-native, database-native or external systems without allowing Debezium, SQL Server LSNs, binlog coordinates, Kafka offsets or Copy Job details to redefine target semantics.

Canonical separation:

```text
provider CDC envelope / native checkpoint
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
MySQL binlog     -> (file generation, position, row sequence)
other provider   -> deterministic integer tuple
```

The semantic core does not compare opaque provider strings and does not guess ordering.

If one native coordinate can contain several row changes, the provider adapter must expose enough sequence information to make each canonical row event position unique.

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

Validation rules:

- key must be present and non-null;
- INSERT/UPDATE require `after`;
- DELETE cannot contain an `after` image;
- payload key values cannot contradict the canonical event key;
- framework-reserved `_framework_cdc_*` fields cannot be injected by source payloads;
- event time, when supplied, must be timezone-aware.

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
- same business key appearing in multiple partitions in one bounded batch -> fail because deterministic per-key order is not proven;
- accepted events are sorted deterministically by partition, position, event ID.

The current certified model deliberately rejects ambiguous repartition/key-movement cases rather than synthesizing an order.

## 5. Current-state apply: CDC -> UPSERT / SCD1

`apply/cdc.py` applies normalized events sequentially to current-state targets.

Target rows touched by CDC retain:

```text
_framework_cdc_partition
_framework_cdc_position
```

Certified behavior:

- INSERT creates current state;
- UPDATE merges source fields into current state;
- DELETE can APPLY / IGNORE / ERROR by explicit policy;
- DELETE of an already-missing target is an idempotent no-op;
- stale event relative to target row position is ignored;
- equal position + equal state is a no-op;
- equal position + conflicting state fails closed;
- unchanged business payload at a newer position advances CDC position without counting a business update;
- source partition change for an already-positioned key fails closed.

Bootstrap rows that do not yet carry row-level CDC position are accepted only when a committed lower checkpoint proves the new event is strictly after the bootstrap boundary.

UPSERT and SCD1 share this CDC correctness path; the semantic naming remains distinct.

## 6. History apply: CDC -> SCD2

SCD2 does not conflate two clocks:

```text
CDC source position -> source event order
event_time          -> business validity interval
```

Two events with the same `event_time` may still be ordered by distinct CDC positions. The earlier history version may become a zero-duration interval.

Current certified behavior:

- INSERT opens a current history version;
- changed UPDATE closes current + opens new version;
- unchanged UPDATE advances CDC source position without generating false history;
- DELETE closes current version;
- reinsert after delete opens a new current version;
- closed versions record which CDC position closed them;
- equal source-position conflict fails closed;
- bootstrap SCD2 rows require the same committed lower-checkpoint proof before first CDC mutation.

Not yet certified:

- retroactive valid-time rewrite when a newer CDC position carries an `event_time` earlier than current `valid_from`.

That case raises `CDCSCD2LateArrivingError` rather than silently rewriting history.

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

Important distinction:

```text
canonical source positions = framework CDC semantic application progress
version                    = control-plane optimistic concurrency token
```

The version is not an LSN/offset.

Checkpoint commit requires:

- target mutation committed;
- required reconciliation passed;
- no checkpoint regression/partition drop;
- caller-supplied `expected_version` equals current version.

A stale writer cannot overwrite newer state.

For FABRIC_NATIVE or EXTERNAL capture progress ownership, provider checkpoint authority remains provider-owned and is retained in `CaptureReceipt.external_checkpoint_reference` / native evidence. `cdc_checkpoint` represents downstream framework semantic application progress; it must not be used to pretend the framework owns the native source cursor.

`cdc_checkpoint` is never promoted between DEV/UAT/PROD.

## 8. Snapshot/bootstrap -> CDC handoff

A safe initial load requires a source fence:

```text
CDC stream/buffer starts at S
        |
        | S <= B
        v
complete snapshot is consistent through B
        |
        v
publish/apply snapshot
        |
        v
consume buffered CDC
  <= B  -> ignore (already represented by snapshot)
  >  B  -> apply
```

`CDCBootstrapEvidence` requires complete snapshot evidence, stable snapshot ID, source epoch/incarnation identity, CDC stream-start checkpoint, snapshot-consistency checkpoint and proof that CDC is retained/buffered from stream start.

Current fail-closed constraints:

- stream start later than snapshot checkpoint -> possible gap -> fail;
- partition set changes during bootstrap -> fail;
- first CDC upper checkpoint regresses below snapshot checkpoint -> fail;
- incomplete or non-fenced snapshot -> fail.

This gives deterministic no-gap/no-double-apply behavior for the currently certified partition model.

## 9. Debezium on Kafka built-in provider profile

The first built-in CDC provider adapter is intentionally narrow and explicit:

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

For Debezium records already consumed from Kafka:

```text
topic + partition + offset
        |
        v
partition = "<topic>:<partition>"
values    = (offset,)
```

Database LSN/binlog/source coordinates are retained as provider metadata only. They are not promoted to the canonical row order because one database coordinate may correspond to multiple row changes and provider encodings vary.

### Envelope policy

Certified mappings:

```text
Debezium op=c -> INSERT
Debezium op=u -> UPDATE
Debezium op=d -> DELETE
Kafka tombstone -> transport cleanup; ignore
```

Debezium snapshot read `op=r` is rejected by default. The framework already has an explicit snapshot/bootstrap handoff and silently accepting `r` could double-apply bootstrap state. `AS_INSERT` is available only as an explicit adapter policy when the caller intentionally owns that behavior.

The adapter requires an explicit Kafka record key. It does not guess the business key from `before`/`after` payloads.

### Provider registry

`CDCProviderAdapterRegistry` resolves by:

```text
(ExecutionEngine, capability_profile)
```

The default registry contains:

```text
(EXTERNAL_CDC, debezium_kafka_v1)
    -> DebeziumKafkaCDCAdapter
```

Unknown/duplicate registrations fail explicitly. The registry does not construct Kafka clients, credentials or arbitrary parser imports.

## 10. Debezium/Kafka recovery and retention-aware resume

Safe downstream recovery is based on the framework committed CDC application checkpoint, **not** the external consumer-group cursor.

Example failure mode:

```text
Kafka consumer/connector cursor = 500
framework Silver applied through = 420
```

Resuming from 500 would silently lose events 421..500. Therefore `plan_debezium_kafka_resume()` derives:

```text
next_required = committed_framework_offset + 1
```

and checks provider retention evidence:

```text
earliest_retained <= next_required <= requested_upper <= latest_available
```

Fail-closed rules include:

- retention floor later than `next_required` -> `DebeziumKafkaResumeGapError`;
- committed partition missing from provider evidence -> gap error;
- requested upper beyond provider latest -> fail;
- requested upper below committed offset -> fail;
- partition set changes after committed state -> fail by default;
- new partition requires explicit acknowledgement.

This planner proves a safe seek/reread range. It does **not** claim to commit or manage a real Kafka consumer group; real transport/client integration remains separate.

## 11. Physical progress ownership

There are two different questions:

```text
Who owns source/native capture progress?
Who owns framework downstream semantic application progress?
```

`ProgressOwner` answers the first question.

Examples:

```text
Copy Job / Fabric-native CDC
  native checkpoint authority -> FABRIC_NATIVE
  CaptureReceipt retains native run/checkpoint evidence
  framework CDC apply checkpoint tracks downstream semantic completion only

Debezium/Kafka
  source consumer/connector progress -> EXTERNAL
  framework safe resume starts from downstream apply checkpoint
  external cursor commit remains external/provider integration

Spark/framework source reader
  source capture progress -> FRAMEWORK
  canonical checkpoint may also be the authoritative source progress
```

The framework must never move a native/external source cursor merely because downstream apply succeeded unless that adapter/transport explicitly owns the corresponding commit protocol.

## 12. Recovery interaction

CDC participates in the same fail-closed recovery model:

```text
capture/window frozen
 -> normalize/apply
 -> target outcome
 -> reconcile
 -> cdc_checkpoint commit
```

If target outcome is unknown:

```text
COMMITTED     -> converge without duplicate write
NOT_COMMITTED -> retry may proceed
UNRESOLVED    -> stop
```

The CDC apply checkpoint is not advanced before this is resolved.

Provider-specific source-cursor coordination remains an adapter/transport concern. The Debezium/Kafka reference now proves retention-aware source reread planning but not live consumer-group commit behavior.

## 13. Current deterministic evidence

```text
ccf0fc8950efb1f4d338cadcaf83aac5fd49a7b9
Actions 33215409341
153 tests passed
canonical CDC + CDC -> UPSERT/SCD1

ed6c13d4fcabe165ef86be2e547d794e15e5375c
Actions 33215708004
159 tests passed
CDC -> SCD2

c41fbd00bb3d3c6bc71e20f958c4ec14106ac33c
Actions 33216133811
165 tests passed
durable checkpoint + optimistic concurrency

465a2c1e9ddf25b0ace2293f578c2c5bb3a653ae
Actions 33216281126
171 tests passed
snapshot/bootstrap -> CDC handoff

1087ab9231b9cb638a87bc2f78ef0c1b1fe32beb
Actions 33219601375
179 tests passed
Debezium/Kafka envelope adapter + retention-aware resume

ecdca38099a4f21c6f40701dc14889b464c20608
Actions 33219783325
183 tests passed
Debezium/Kafka capability profile + provider registry
```

These are REFERENCE/ADAPTER-CONTRACT/CI proofs. They are not evidence of a real Kafka broker, Debezium connector, database CDC service, Copy Job or Fabric workspace execution.

## 14. Remaining CDC work

Required before CDC can be called broadly production-integrated:

1. real Kafka/Debezium transport and consumer-group correlation/commit evidence;
2. additional provider mappings only for explicitly supported source products;
3. provider transaction-boundary handling where atomic multi-row treatment is required;
4. partition/rebalance/source-epoch operational policies beyond the current fail-closed model;
5. poison-event quarantine/replay integration;
6. retroactive SCD2 history correction policy if product scope chooses to support it;
7. persistent production control-plane repository and transaction tests;
8. at least one approved DEV end-to-end CDC execution.

## 15. Extension boundary

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
