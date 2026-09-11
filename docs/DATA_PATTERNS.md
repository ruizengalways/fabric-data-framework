# Data patterns

This is the canonical onboarding guide for a new source/table. Start with source facts; choose Fabric execution technology only after the semantics are clear.

## 1. Collect these source facts first

Before configuring the framework, confirm:

1. What can the first load read: full snapshot or incremental only?
2. What do later loads deliver: full snapshot, updated rows, net changes, ordered changes, business events?
3. What identifies the business grain: entity key, event identity, or neither?
4. What proves order: timestamp, version, LSN, offset, sequence?
5. How are deletes exposed: hard delete, soft delete, tombstone, CDC delete event, or not at all?
6. Can updates arrive late or be back-dated?
7. Does the provider collapse intermediate changes?
8. Does the business need current state or history, and at what truthful grain?

Do not configure SCD2 before these facts are known.

## 2. Capture decision tree

```text
Do you read the whole current table/file each time?
  |
  +-- yes -> FULL SNAPSHOT
  |          |
  |          +-- current only -> Current Bronze
  |          +-- snapshot history -> Snapshot Bronze
  |          +-- infer changes -> Snapshot Diff
  |
  +-- no
       |
       +-- monotonic watermark / updated_at available?
       |     |
       |     +-- yes -> WATERMARK
       |              +-- late updates -> LOOKBACK
       |              +-- delete flag -> SOFT DELETE
       |
       +-- provider gives a change feed?
       |     |
       |     +-- final change per key/window -> NET CHANGES
       |     +-- ordered intermediate changes -> ALL/FULL CHANGES
       |
       +-- source is business events -> BUSINESS EVENTS
```

## 3. Common semantic combinations

| # | Pattern | Source facts | Delete visibility | Recommended Bronze | Truthful history ceiling | Common target |
|---|---|---|---|---|---|---|
| 1 | Full Snapshot -> Current | whole current table | inferable only by comparing snapshots | Current | current state | REPLACE / SCD1 |
| 2 | Full Snapshot -> Snapshot | whole snapshot per run | inferable between snapshots | Snapshot | snapshot grain | snapshot history / SCD2 |
| 3 | Watermark -> Current | rows after checkpoint | hard delete usually invisible | Current | observed updates | SCD1 / limited SCD2 |
| 4 | Watermark + Lookback -> Current | overlapping incremental window | hard delete usually invisible | Current | observed updates with safer late arrival | SCD1 / limited SCD2 |
| 5 | Watermark + Lookback -> Raw Append | overlapping observations | hard delete usually invisible | Raw append | observed-change grain | SCD2 / audit |
| 6 | Watermark + Soft Delete -> Current | updated rows + tombstone flag | soft delete visible | Current | observed updates + tombstones | SCD1 / SCD2 |
| 7 | Watermark + Lookback + Soft Delete -> Raw Append | overlap + tombstones | soft delete visible | Raw append | observed-change grain | SCD2 / audit |
| 8 | Net Changes -> Current | final change per key/provider window | provider-dependent | Current | provider window grain | SCD1 |
| 9 | Net Changes -> Append | net changes retained per batch | provider-dependent | Append changes | provider window grain | cautious SCD2 |
| 10 | All Changes -> Event | ordered change events | delete event visible when supplied | Event | captured event grain | SCD2 / event history |
| 11 | All Changes -> Current | complete source changes intentionally collapsed | delete processable | Current | intentionally reduced to current | SCD1 |
| 12 | Business Events -> Event | domain events | event-defined | Event | captured business-event grain | append / projections |
| 13 | Snapshot Diff -> Current | framework compares snapshots | disappearance inferable | Current | snapshot interval grain | SCD1 |
| 14 | Snapshot Diff -> Append Changes | inferred I/U/D retained | disappearance inferable | Append changes | snapshot interval grain | SCD2 / audit |
| 15 | Watermark + Lookback -> Change Log Append | application audit/change-history rows with stable event identity | event-defined / often not applicable | Raw append / Event | captured event grain | deduplicated APPEND |

Support for a semantic pattern does not mean every provider has retained live Fabric proof for that pattern. Evidence level is tracked separately in [`internal/CAPABILITIES.md`](internal/CAPABILITIES.md).

## 4. Bronze selection

### Current Bronze

Use when the durable requirement is latest state and observation history is not needed.

### Snapshot Bronze

Use when complete snapshots are the source truth and you need snapshot-grain history or snapshot diff.

### Raw append / Event Bronze

Use when the source provides meaningful observations/events and audit, replay or history requires retaining them.

Do not raw-append repeated scans and then claim every row is a business change. Bronze meaning must match the source meaning.

## 5. SCD1 vs SCD2

### SCD1

Use when latest state is sufficient or source history fidelity is too weak to justify detailed history.

### SCD2

Use when as-of history is required **and** source/capture evidence can prove the change boundaries being recorded.

Invariant:

```text
SCD2 is a target representation.
It is not a source-history generator.
```

SCD2 key contract:

- `business_key` is the canonical entity identity used for current-row lookup, history grouping and the one-current-row invariant;
- the shared `LoadPolicy.merge_key` field is retained for the current metadata shape, but for SCD2 it must be exactly equal to `business_key`;
- divergent SCD2 `business_key` / `merge_key` values are rejected fail-closed rather than accepting a configuration whose `merge_key` would be operationally ignored.

A daily snapshot can support snapshot-grain SCD2. It cannot prove unobserved intra-day transitions unless stronger source evidence exists.

## 6. Watermark safety

For a query such as:

```sql
WHERE updated_at > :last_watermark
```

verify:

- every relevant update changes `updated_at`;
- precision is sufficient;
- rows sharing a timestamp have deterministic tie-breaking;
- late/back-dated updates are understood;
- commit/timestamp ordering cannot create a gap;
- delete visibility is separately defined.

For late arrival, use a bounded overlap when appropriate:

```text
checkpoint = 10:00
lookback   = 2h
next read  = [08:00, frozen upper bound]
```

Then deduplicate using stable key + ordering evidence.

Lookback protects boundary/late observations. It does not make hard deletes visible.

## 7. Full baseline -> incremental handoff

A common pattern is first full load, then watermark/CDC. The handoff must prove:

```text
baseline complete
+ boundary consistent
+ post-boundary changes remain visible
+ deterministic ordering
```

If the source cannot prove those conditions, do not claim a no-gap bootstrap.

## 8. Delete semantics

### Hard delete with watermark reads

If deleted rows disappear and the incremental query only reads existing rows:

```text
delete visibility = none
```

The framework does not guess deletes. Add an explicit signal such as:

```text
soft delete flag
CDC delete event
tombstone feed
periodic full snapshot diff
source audit/change table
```

### Soft delete

A flag such as `is_deleted=1` is useful only if the tombstone remains visible long enough for the capture process to observe it.

## 9. Net CDC vs full CDC

If one key changes:

```text
A -> B -> C
```

and the provider returns only `A -> C`, history fidelity is provider-window grain. `B` cannot be reconstructed.

If the provider returns ordered `A -> B` and `B -> C` with reliable LSN/offset/sequence, those captured transitions may be retained as event-grain history.

## 10. Application change log / audit history -> deduplicated APPEND

A table can describe changes without being a database CDC feed. Common examples are Jira issue change history, application audit tables, workflow history and operational event logs.

Typical source shape:

```text
issue_id   changed_at              field       old_value   new_value
JIRA-100   2026-09-08 10:00:01     status      Open        In Progress
JIRA-100   2026-09-08 10:05:11     assignee    A           B
JIRA-101   2026-09-08 10:07:22     status      Open        Closed
```

The source table may have no declared database primary key. That does **not** prevent safe append processing. The important question is whether one business event can be given a stable, source-controlled identity.

Keep these concepts separate:

```text
Entity key
  identifies the business entity, for example issue_id

Event identity
  identifies one immutable change event, for example history_id
  or a justified composite identity

Incremental cursor
  identifies what to read next, for example changed_at
```

These three values do not have to be the same column.

### Recommended pattern

When the table is incrementally readable by a timestamp or similar cursor and duplicate observations are possible:

```text
Application change-history table
        |
        | WATERMARK + bounded LOOKBACK/overlap
        v
Raw append / Event Bronze
        |
        | normalize + DQ
        v
APPEND identity guard
        |
        | exact duplicate observation -> collapse/no-op
        | same identity + same payload -> idempotent replay
        | same identity + different payload -> FAIL CLOSED
        v
Silver change-history table
```

This is usually:

```text
CaptureStrategy = WATERMARK
ApplyStrategy   = APPEND
```

It is **not** automatically `CDC + SCD2` merely because the rows describe changes.

### Why overlap is useful

A timestamp cursor often has shared timestamps, late commits or delayed visibility. Instead of trying to make the source read exactly-once, deliberately re-read a bounded range:

```text
committed checkpoint = 10:30
lookback              = 10 minutes
next read begins      = 10:20
```

This produces at-least-once source observation. Safe Silver publication then depends on an idempotent event identity:

```text
at-least-once capture
+
stable APPEND identity
=
reliable append-once Silver semantics
```

### Choosing `append_identity`

Best case: the source exposes a true immutable event identifier:

```text
append_identity = (history_id,)
```

or, when one history record contains multiple field changes:

```text
append_identity = (history_id, field_name)
```

If there is no declared PK but a composite set of source fields uniquely identifies one event, use that composite explicitly:

```text
append_identity = (
    issue_id,
    changed_at,
    field_name,
    old_value,
    new_value,
    actor_id,
)
```

The framework `APPEND` contract requires a non-empty `append_identity`; exact duplicates may be collapsed, but reuse of the same identity with a different business payload is a semantic conflict and must fail closed.

### Bronze vs Silver meaning

Do not deduplicate Bronze merely because Silver is deduplicated.

If overlapping reads observe:

```text
A
B
C
B
C
D
```

Raw/Event Bronze may legitimately retain:

```text
A
B
C
B
C
D
```

because those are the source observations actually captured.

Silver may contain:

```text
A
B
C
D
```

because those are the unique business events under the declared `append_identity`.

Therefore:

```text
Bronze = source observation truth
Silver = deduplicated business-event truth
```

### No stable event identity

If two legitimate source events can have exactly the same values for every candidate identity field, the framework cannot infer that they are distinct.

A whole-row/content hash may be used only when the business contract explicitly accepts:

```text
identical payload observations are the same business event
```

Otherwise deduplication would destroy source fidelity. Do not claim event-level completeness that the source cannot prove.

A missing database primary key is therefore not the blocker. The real blocker is the absence of a defensible stable event identity.

### Example `LoadPolicy`

Conceptually:

```python
LoadPolicy(
    capture_strategy=CaptureStrategy.WATERMARK,
    apply_strategy=ApplyStrategy.APPEND,
    watermark=WatermarkConfig(
        column="changed_at",
        overlap_window_seconds=600,
    ),
    append_identity=(
        "issue_id",
        "changed_at",
        "field_name",
        "old_value",
        "new_value",
    ),
    event_time_column="changed_at",
)
```

Before choosing that composite identity, verify with source/domain owners that two distinct valid events cannot legitimately share all of those values. Prefer a source-native immutable history/event ID whenever one exists.

## 11. Examples

### CRM customer

```text
PK             = customer_id
updated_at     = reliable
late arrival   = up to 30m
soft delete    = is_deleted
history needed = yes
```

Typical choice:

```text
WATERMARK + LOOKBACK + SOFT DELETE
-> Raw Append Bronze
-> SCD2
```

### Nightly complete ERP file

Current only:

```text
FULL SNAPSHOT -> Current Bronze -> REPLACE/SCD1
```

Snapshot-grain history:

```text
FULL SNAPSHOT -> Snapshot Bronze -> Snapshot Diff -> SCD2/audit
```

### Provider CDC returning net changes only

```text
NET CHANGES -> Current Bronze
```

or retain the batch-grain net changes, but do not label them complete event history.

### Payment events

```text
PaymentAuthorized
PaymentCaptured
PaymentRefunded
```

Treat these as business events:

```text
BUSINESS EVENTS -> Event Bronze -> append/event-derived models
```

A current payment projection can be derived downstream.

### Jira issue change history

If Jira/application history is exposed as a normal table with `changed_at` but not as a transaction-log CDC feed:

```text
WATERMARK + LOOKBACK
-> Raw/Event Bronze
-> APPEND identity dedup
-> Silver issue_change_history
```

Prefer a source-native `history_id` when available. Otherwise use a justified composite event identity and document the source-fidelity limitation if identical valid events cannot be distinguished.

## 12. Project onboarding sequence

In the implementation/domain repo:

```text
1. collect source facts
2. choose semantic pattern
3. create DatasetConfig
4. declare Bronze/apply/DQ/reconciliation semantics
5. run semantic onboarding/static validation
6. configure DEV logical/physical binding
7. add a bounded project adapter only if the provider needs one
8. deploy DEV
9. run real environment validation
```

Useful CLI entry point:

```bash
fabric-framework capture-semantic-onboarding-validate --help
```

Never lower the semantic description merely to make validation pass. The framework should expose overclaim, not hide it.
