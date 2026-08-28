# CDC Design — fabric-data-framework

Status: Canonical provider-neutral CDC correctness contract
Last updated: 2026-08-29

## 1. Purpose

CDC is a capture/change representation, not an apply strategy.

The framework must be able to consume CDC from Fabric-native, database-native or external systems without allowing Debezium, SQL Server LSNs, binlog coordinates, Kafka offsets or Copy Job details to redefine target semantics.

Canonical separation:

```text
provider CDC envelope / native checkpoint
        |
        v
provider adapter
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
        +--> future APPEND/custom semantic
        |
        v
reconciliation
        |
        v
cdc_checkpoint commit
```

`CDC != SCD2` remains a hard architecture invariant.

## 2. Canonical source position

Provider adapters must normalize source coordinates into:

```text
CDCSourcePosition
  partition: string
  values: tuple[int, ...]
```

Examples conceptually include:

```text
SQL Server       -> (LSN components..., row sequence)
Kafka/Debezium   -> partition + (offset, row/transaction sequence)
MySQL binlog     -> (file generation, position, row sequence)
other provider   -> deterministic integer tuple
```

The semantic core does not compare opaque strings and does not guess ordering.

If one native coordinate can contain several row changes, the adapter must include enough sequence information to make each canonical row event position unique.

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

Provider metadata may be retained, but correctness must depend on typed canonical fields rather than arbitrary metadata keys.

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

SCD2 must not conflate two clocks:

```text
CDC source position -> source event order
event_time          -> business validity interval
```

Therefore two events with the same `event_time` may still be ordered by distinct CDC positions. The earlier history version may become a zero-duration interval.

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
canonical source positions = semantic CDC apply progress
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

A safe initial load requires a source fence. The current provider-neutral contract is:

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

`CDCBootstrapEvidence` requires:

- complete snapshot;
- stable snapshot ID;
- source epoch/incarnation identity;
- CDC stream-start checkpoint;
- snapshot-consistency checkpoint;
- proof that snapshot is consistent through that checkpoint;
- proof CDC is retained/buffered from stream start.

Current fail-closed constraints:

- stream start later than snapshot checkpoint -> possible gap -> fail;
- partition set changes during bootstrap -> fail;
- first CDC upper checkpoint regresses below snapshot checkpoint -> fail;
- incomplete or non-fenced snapshot -> fail.

This gives deterministic no-gap/no-double-apply behavior for the currently certified partition model.

## 9. Physical progress ownership

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
  external checkpoint reference retained in CaptureReceipt
  framework CDC apply checkpoint tracks downstream semantic completion only

Spark/framework source reader
  source capture progress -> FRAMEWORK
  canonical checkpoint may also be the authoritative source progress
```

The framework must never move a native/external source cursor merely because downstream apply succeeded unless that adapter explicitly owns the corresponding commit protocol.

## 10. Recovery interaction

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

The CDC checkpoint is not advanced before this is resolved.

Future provider adapters must also prove how native/external capture offsets are resumed/committed after downstream failures.

## 11. Current deterministic evidence

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
```

These are REFERENCE/CI proofs. They are not evidence of a real Debezium, database CDC, Copy Job or Fabric workspace execution.

## 12. Remaining CDC work

Required before CDC can be called broadly production-integrated:

1. provider envelope adapters and capability profiles for selected supported sources;
2. real Fabric/native/external transport/correlation evidence;
3. provider-specific offset commit/resume semantics after downstream failure;
4. transaction-boundary handling where a provider needs atomic multi-row transaction treatment;
5. partition/rebalance/source-epoch operational policies beyond the current fail-closed model;
6. poison-event quarantine/replay integration;
7. retroactive SCD2 history correction policy, if product scope chooses to support it;
8. persistent production control-plane repository and transaction tests;
9. at least one approved DEV end-to-end CDC execution.

## 13. Extension boundary

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
